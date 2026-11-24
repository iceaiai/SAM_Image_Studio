import csv
import math
from types import SimpleNamespace

import cv2
import numpy as np
import pytest
from matplotlib.colors import to_hex
from PySide6.QtCore import QPointF, QTimer, Qt
from PySide6.QtGui import QPaintDevice
from PySide6.QtWidgets import QApplication, QDialog, QDialogButtonBox, QInputDialog, QPushButton

from samstudio import __version__, savepoints
from samstudio.dialogs import InferenceOptionsDialog, MaskColorsDialog
from samstudio.domain import Calibration, Document, History, ImageFrame, ProjectStore
from samstudio.exports import hex_rgb, render_mask_pixels
from samstudio.filaments import FilamentLink
from samstudio.help_viewer import UserManualDialog
from samstudio.inference import InferenceEngine
from samstudio.palette import MetricColorScheme, metric_palette
from samstudio.plot_groups import PlotGroupDialog
from samstudio.processing import shape_mask
from samstudio.processing_ui import ProcessingDialog
from samstudio.scale_bar_ui import ScaleBarDialog, scale_bar_layout
from samstudio.statistics import export_statistics, measurement_records
from samstudio.target_size import TargetSizeRange
from samstudio.transforms import rotate_document


def image(tmp_path, name="image", calibration=None):
    return Document(ImageFrame(str(tmp_path / f"{name}.tif"), np.zeros((90, 130), np.uint8),
                               calibration=calibration or Calibration()))


def attach(window, document, tmp_path):
    key = document.frame.key
    store = ProjectStore(tmp_path / "annotations")
    window.documents[key] = document
    window.stores[key] = store
    window.histories[key] = History(document, lambda: store.save(document))
    window._rebuild_file_tree()
    window.select_document(key)
    return store


def rectangle(document, x, y, w, h, color=None):
    mask = np.zeros(document.frame.shape, bool)
    mask[y:y+h, x:x+w] = True
    obj = document.add_object("mask", mask=mask)
    if color is not None:
        obj.color = color
    return obj


def accept_rendered_dialog(open_dialog, dialog_class, configure):
    def interact():
        dialog = QApplication.activeModalWidget()
        assert isinstance(dialog, QDialog)
        try:
            assert isinstance(dialog, dialog_class)
            configure(dialog)
            assert QPaintDevice.width(dialog) > 0
            assert not dialog.grab().isNull()
            dialog.findChild(QDialogButtonBox).button(QDialogButtonBox.StandardButton.Ok).click()
            assert dialog.result() == QDialog.DialogCode.Accepted
        finally:
            if dialog.isVisible():
                dialog.reject()

    QTimer.singleShot(0, interact)
    open_dialog()


def test_help_menu_and_denoise_button_open_versioned_manual(window, qtbot):
    menu = window.help_menu
    assert menu.menuAction() in window.menuBar().actions()
    assert [action.text() for action in menu.actions()] == ["User Manual"]
    menu.actions()[0].trigger()
    manual = window.findChild(UserManualDialog)
    qtbot.waitUntil(manual.isVisible)
    assert __version__ in manual.windowTitle()
    assert manual.browser.toPlainText().startswith(f"SAM Image Studio {__version__} User Manual")
    assert manual.browser.verticalScrollBar().value() == 0
    manual.close()

    dialog = ProcessingDialog(["DCT sparsity"], window)
    qtbot.addWidget(dialog)
    dialog.show()
    qtbot.mouseClick(dialog.denoising_help, Qt.MouseButton.LeftButton)
    chapter = dialog.findChild(UserManualDialog)
    qtbot.waitUntil(lambda: chapter.browser.verticalScrollBar().value() > 0)
    top = chapter.browser.cursorForPosition(chapter.browser.viewport().rect().topLeft())
    assert "Denoising parameters" in top.block().text() or "Denoising parameters" in top.block().next().text()
    assert "Workflow and physical interpretation" in chapter.browser.toPlainText()
    chapter.close()


def test_target_size_uses_area_basis_and_optional_manual_pixel_sizes(window, qtbot):
    calibrated = Calibration(.2, .3, "nm", "test", True, basis=[[.2, .1], [0, .3]])
    assert TargetSizeRange(unit="nm", minimum=.6).pixel_bounds(calibrated) == pytest.approx((10, None))
    diameter = math.sqrt(4 * 6 / math.pi) / 1000
    bounds = TargetSizeRange("diameter", "µm", maximum=diameter,
                             pixel_size_x=.2, pixel_size_y=.3).pixel_bounds(Calibration())
    assert bounds[0] is None and bounds[1] == pytest.approx(100)
    assert TargetSizeRange(unit="mm").pixel_bounds(Calibration()) is None
    with pytest.raises(ValueError, match="calibration"):
        TargetSizeRange(unit="mm", maximum=5).pixel_bounds(Calibration())
    with pytest.raises(ValueError, match="Minimum"):
        TargetSizeRange(minimum=6, maximum=5).pixel_bounds(calibrated)

    dialog = InferenceOptionsDialog(window.options, window, calibration=Calibration())
    qtbot.addWidget(dialog)
    controls = dialog.target_size
    controls.unit.setCurrentIndex(controls.unit.findData("nm"))
    controls.maximum.setText(".36")
    with pytest.raises(ValueError, match="calibration"):
        controls.value()
    controls.override.setChecked(True)
    controls.pixel_x.setText(".2")
    controls.pixel_y.setText(".3")
    settings = controls.value()
    assert settings.minimum is None
    assert settings.pixel_bounds(Calibration())[1] == pytest.approx(6)


def test_options_opens_and_accepts_target_size_controls(window, tmp_path):
    attach(window, image(tmp_path), tmp_path)

    def select_diameter(dialog):
        controls = dialog.target_size
        assert QPaintDevice.width(controls) > 0
        controls.metric_combo.setCurrentIndex(controls.metric_combo.findData("diameter"))
        assert controls.unit.currentText() == "px"
        controls.maximum.setText("24")

    accept_rendered_dialog(window.options_button.click, InferenceOptionsDialog, select_diameter)
    assert window.target_size == TargetSizeRange(metric="diameter", maximum=24)
    assert not window.errors


@pytest.mark.parametrize(
    ("tool", "calibration", "readout"),
    [
        ("measure_line", Calibration(), "20 px"),
        ("measure_line", Calibration(.5, 2, "nm", "test", True), "20 px · 32.558 nm"),
        ("measure_curve", Calibration(.5, 2, "nm", "test", True, basis=[[0, -2], [.5, 0]]), "28 px · 38 nm"),
    ],
)
def test_distance_tools_trace_and_measure_in_image_coordinates(window, qtbot, tmp_path, tool, calibration, readout):
    doc = image(tmp_path, calibration=calibration)
    attach(window, doc, tmp_path)
    window.mode.setCurrentText("Segment")
    doc.draft["points"] = [[40, 40, 1]]
    before = doc.state()
    canvas = window.canvas
    canvas.scale = 4
    canvas.offset = QPointF(24, 24)
    canvas.update()
    qtbot.wait(10)
    image_before = canvas.grab().toImage()
    qtbot.mouseClick(window.toolbar.widgetForAction(window.tool_actions[tool]), Qt.MouseButton.LeftButton)
    assert canvas.tool == tool
    start, corner, end = [canvas.to_widget(point).toPoint() for point in ((10, 10), (22, 10), (22, 26))]
    qtbot.mousePress(canvas, Qt.MouseButton.LeftButton, pos=start)
    qtbot.mouseMove(canvas, pos=corner)
    qtbot.mouseMove(canvas, pos=end)
    assert canvas.distance_readout() == readout
    qtbot.mouseRelease(canvas, Qt.MouseButton.LeftButton, pos=end)
    assert canvas.distance_readout() == readout
    assert canvas.grab().toImage() != image_before
    assert not canvas.preview_masks and doc.state() == before

    canvas.fit_image()
    assert canvas.distance_readout() == readout
    qtbot.keyClick(canvas, Qt.Key.Key_Escape)
    assert not canvas.distance_readout()
    assert doc.state() == before
    window.cancel_button.click()
    assert not doc.draft["points"]
    assert not window.errors


def test_distance_measurement_clears_on_image_switch(window, qtbot, tmp_path):
    first = image(tmp_path, name="first")
    second = image(tmp_path, name="second")
    attach(window, second, tmp_path)
    attach(window, first, tmp_path)
    window.mode.setCurrentText("Edit")
    canvas = window.canvas
    window.tool_actions["measure_line"].trigger()
    start, end = [canvas.to_widget(point).toPoint() for point in ((20, 20), (50, 20))]
    qtbot.mousePress(canvas, Qt.MouseButton.LeftButton, pos=start)
    qtbot.mouseRelease(canvas, Qt.MouseButton.LeftButton, pos=end)
    assert canvas.distance_readout().endswith(" px")
    window.select_document(second.frame.key)
    assert not canvas.distance_readout()


@pytest.mark.parametrize("scope", ["roi", "prompt", "single"])
def test_size_range_controls_preview_and_preserves_candidate_score(window, qtbot, tmp_path, monkeypatch, scope):
    doc = image(tmp_path)
    doc.ensure_group("Particles")
    attach(window, doc, tmp_path)
    roi = {"kind": "rectangle", "points": [[10, 10], [15, 15]]}
    clipped = shape_mask(roi["kind"], roi["points"], doc.frame.shape)
    large = np.zeros(doc.frame.shape, bool)
    large[8:20, 8:20] = True
    tiny = np.zeros_like(large)
    tiny[11, 11] = True
    outputs = [large, tiny]
    calls = []

    def infer(*args, **options):
        calls.append(options)
        return [mask.copy() for mask in outputs]

    def exemplars(engine, rgb, points, examples, protected, progress, cancel, text, options):
        return infer(**options)

    window.engine = SimpleNamespace(ready=True, device="cpu",
                                    spec=SimpleNamespace(family="SAM1", label="Test SAM"),
                                    last_proposal_scores=[.94, .37], infer=infer)
    monkeypatch.setattr(window, "_example_inference", exemplars)
    window.mode.setCurrentText("Segment")
    window.canvas.set_tool("rectangle")
    window.scope.setCurrentIndex(window.scope.findData(scope))
    window.auto_checkbox.setChecked(False)
    window.preview_timer.stop()
    doc.draft["roi"] = roi
    # In ROI the larger candidate matches after clipping. In Whole Image only
    # the smaller candidate matches. The native single-object route ignores it.
    maximum = int(clipped.sum()) if scope == "roi" else 1
    window.target_size = TargetSizeRange(minimum=maximum, maximum=maximum)
    if scope == "single":
        outputs[:] = [large]
    window.run_inference()
    qtbot.waitUntil(lambda: not window.busy)
    assert calls
    assert ("area_range" in calls[0]) == (scope != "single")
    assert len(window.canvas.preview_masks) == 1
    expected = clipped if scope == "roi" else tiny if scope == "prompt" else large
    np.testing.assert_array_equal(window.canvas.preview_masks[0], expected)
    window.accept_preview()
    assert doc.objects[0].provenance["confidence_score"] == (.37 if scope == "prompt" else .94)
    assert ("target_size" in doc.objects[0].provenance) == (scope != "single")


def test_grid_size_filter_keeps_searching_past_oversized_candidates(monkeypatch):
    engine = InferenceEngine()
    engine.predictor = object()
    large = np.zeros((16, 16), bool)
    large[1:7, 1:7] = True
    small = np.zeros_like(large)
    small[4:6, 12:14] = True
    proposals = iter([(large, .99), (small, .8)])
    monkeypatch.setattr(engine, "predict", lambda *args: next(proposals))
    [mask] = engine.infer(np.zeros((16, 16, 3), np.uint8), whole=True, grid=2,
                          max_objects=1, min_area=1, area_range=(None, 4))
    np.testing.assert_array_equal(mask, small)
    assert engine.last_proposal_scores == [.8]


def test_scale_bar_previews_edits_and_removes_with_undo(window, tmp_path, monkeypatch):
    doc = image(tmp_path, calibration=Calibration(.5, 2, "nm", "test", True))
    store = attach(window, doc, tmp_path)
    entry_pixels = window.canvas.grab().toImage()

    def add_bar(dialog):
        assert callable(dialog.font)
        dialog.length.setText("500")
        assert not dialog.controls.button(QDialogButtonBox.StandardButton.Ok).isEnabled()
        assert window.canvas.previewing_scale_bar and window.canvas.scale_bar_preview is None
        dialog.length.setText("20")
        dialog.line_width.setValue(4)
        dialog.font_size.setValue(12)
        dialog.position.setCurrentIndex(dialog.position.findData("top-left"))
        assert window.canvas.previewing_scale_bar and window.canvas.scale_bar_preview == dialog.value
        assert doc.scale_bar is None
        assert window.canvas.grab().toImage() != entry_pixels
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(ScaleBarDialog, "exec", add_bar)
    window.scale_bar_action.trigger()
    old = doc.scale_bar
    assert old.length_in_pixels(doc.calibration) == 40
    _, _, _, line_start, line_end = scale_bar_layout(old, doc.calibration, doc.frame.shape)
    assert line_end.x() - line_start.x() == 40 and line_start.y() < doc.frame.shape[0] / 2
    assert not window.canvas.previewing_scale_bar

    def adjust(dialog, result):
        dialog.length.setText("30")
        assert window.canvas.scale_bar_preview.length == 30 and doc.scale_bar == old
        return result

    monkeypatch.setattr(ScaleBarDialog, "exec", lambda d: adjust(d, QDialog.DialogCode.Rejected))
    window.scale_bar_action.trigger()
    assert doc.scale_bar == old
    monkeypatch.setattr(ScaleBarDialog, "exec", lambda d: adjust(d, QDialog.DialogCode.Accepted))
    window.scale_bar_action.trigger()
    assert doc.scale_bar.length == 30
    restored = Document(doc.frame)
    assert store.load(restored)[0] and restored.scale_bar == doc.scale_bar
    window.remove_scale_bar_action.trigger()
    assert doc.scale_bar is None
    window.undo_action.trigger()
    assert doc.scale_bar.length == 30
    np.testing.assert_array_equal(doc.frame.raw, np.zeros(doc.frame.shape, np.uint8))


def test_delete_vertex_and_delete_objects_are_independent(window, qtbot, tmp_path):
    doc = image(tmp_path)
    doc.ensure_group("Features")
    points = [[20, 20], [40, 20], [50, 30], [40, 40], [20, 40]]
    obj = doc.add_object("polygon", points, shape_mask("polygon", points, doc.frame.shape))
    attach(window, doc, tmp_path)
    window.mode.setCurrentText("Edit")
    window.canvas.set_selected({obj.id})
    window._canvas_selected({obj.id})
    qtbot.keyClick(window.canvas, Qt.Key.Key_Delete)
    assert len(doc.objects) == 1 and len(doc.objects[0].points) == 5
    qtbot.mouseClick(window.canvas, Qt.MouseButton.LeftButton, pos=window.canvas.to_widget(points[1]).toPoint())
    window.delete_vertex_action.trigger()
    assert len(doc.objects) == 1 and len(doc.objects[0].points) == 4
    window.delete_action.trigger()
    assert not doc.objects


def test_curved_centerline_and_varying_visible_widths(tmp_path):
    doc = image(tmp_path)
    group = doc.ensure_group("Fibers")
    doc.set_filament_group(group.id, True)
    curved = np.zeros(doc.frame.shape, np.uint8)
    cv2.ellipse(curved, (45, 45), (28, 28), 0, 0, 180, 1, 1)
    doc.add_object("mask", mask=curved)
    variable = np.zeros(doc.frame.shape, bool)
    variable[20:23, 64:86] = True
    variable[18:25, 86:114] = True
    doc.add_object("mask", mask=variable)
    (arc, stripe), excluded = measurement_records(doc)
    assert not excluded and arc["filament_visible_length_px"] > 1.25 * 56
    assert arc["filament_total_length_px"] == arc["filament_visible_length_px"]
    assert stripe["filament_width_min_px"] < stripe["filament_width_mean_px"] < stripe["filament_width_max_px"]
    assert stripe["filament_width_variance_px"] == pytest.approx(stripe["filament_width_std_px"] ** 2)
    assert stripe["filament_width_std_px"] > 0 and stripe["filament_gap_length_px"] == 0


def test_filament_gui_links_facing_ends_and_counts_one_object(window, qtbot, tmp_path, monkeypatch):
    doc = image(tmp_path, calibration=Calibration(.5, 2, "nm", "test", True))
    group = doc.ensure_group("Fibers")
    a = rectangle(doc, 15, 35, 20, 1, "#238a8d")
    b = rectangle(doc, 45, 35, 20, 1, "#cd4772")
    store = attach(window, doc, tmp_path)
    window.mode.setCurrentText("Edit")
    monkeypatch.setattr(QInputDialog, "getItem", lambda *args: ("Fibers", True))
    window.mark_filament_action.trigger()
    assert group.filament
    window.canvas.set_selected({a.id, b.id})
    window._canvas_selected({a.id, b.id})
    window.connect_filament_action.trigger()
    assert window.canvas.filament_picks.keys() == {a.id, b.id}
    end_a = max(window.canvas.filament_picks[a.id], key=lambda end: end[1][0])[1]
    end_b = min(window.canvas.filament_picks[b.id], key=lambda end: end[1][0])[1]
    for end in (end_a, end_b):
        qtbot.mouseClick(window.canvas, Qt.MouseButton.LeftButton, pos=window.canvas.to_widget(end).toPoint())
    assert len(doc.filament_links) == len(window.canvas.filament_bridges) == 1
    [record], _ = measurement_records(doc, {b.id}, unit="nm")
    assert record["fragment_ids"] == (a.id, b.id) and record["particle_count_px"] == 1
    assert record["filament_visible_length_px"] == 40
    assert record["filament_gap_length_px"] == 10
    assert record["filament_total_length_physical"] == 25
    assert record["filament_width_min_physical"] == record["filament_width_max_physical"] == 2
    assert record["filament_width_variance_physical"] == 0
    assert window.canvas.object_colors[a.id] == window.canvas.object_colors[b.id]
    path = tmp_path / "filaments.csv"
    export_statistics([record], path, ["filament_width_variance", "filament_gap_length"])
    with path.open() as stream:
        [row] = list(csv.DictReader(stream))
    assert row["fragment_ids"] == f"{a.id}; {b.id}" and row["filament_gap_length_physical"] == "5.0"

    snapshot = savepoints.capture(doc)
    restored = Document(doc.frame)
    assert store.load(restored)[0] and len(restored.filament_links) == 1
    rotate_document(restored, 90, "rectangle")
    [rotated], _ = measurement_records(restored)
    assert rotated["filament_gap_length_physical"] == pytest.approx(5.)
    doc.unlink_filaments([a.id])
    savepoints.restore(doc, snapshot)
    assert len(doc.filament_links) == 1
    window.disconnect_filament_action.trigger()
    assert len(measurement_records(doc)[0]) == 2 and not doc.filament_links
    window.undo_action.trigger()
    assert len(doc.filament_links) == 1


def test_filament_rejects_invalid_chains_and_prunes_deleted_fragments(tmp_path):
    doc = image(tmp_path)
    group = doc.ensure_group("Fibers")
    doc.set_filament_group(group.id, True)
    a, b, c = [rectangle(doc, x, 25, 10, 1) for x in (10, 30, 50)]
    doc.connect_filament(FilamentLink(a.id, b.id, (19.5, 25), (29.5, 25)))
    with pytest.raises(ValueError, match="Each end"):
        doc.connect_filament(FilamentLink(b.id, c.id, (29.5, 25), (49.5, 25)))
    doc.connect_filament(FilamentLink(b.id, c.id, (39.5, 25), (49.5, 25)))
    with pytest.raises(ValueError, match="loop"):
        doc.connect_filament(FilamentLink(c.id, a.id, (59.5, 25), (9.5, 25)))
    doc.delete_objects({b.id})
    assert not doc.filament_links
    assert len(measurement_records(doc)[0]) == 2


def test_pre_feature_project_uses_default_measurement_settings(tmp_path):
    doc = image(tmp_path)
    doc.ensure_group("Particles")
    obj = rectangle(doc, 1, 1, 4, 4)
    state = doc.state()
    state["schema_version"] = 5
    for key in ("scale_bar", "filament_links", "metric_color_scheme"):
        del state[key]
    del state["groups"][0]["filament"]
    restored = Document(doc.frame)
    restored.restore(state)
    assert restored.scale_bar is None and restored.metric_color_scheme is None and not restored.filament_links
    assert not restored.groups[0].filament
    np.testing.assert_array_equal(restored.objects[0].mask, obj.mask)


def test_metric_color_count_exceeds_20_and_persists_per_image(window, qtbot, tmp_path):
    doc = image(tmp_path)
    doc.ensure_group("Particles")
    for value in range(1, 32):
        rectangle(doc, 0, value, value, 1)
    store = attach(window, doc, tmp_path)

    def choose(dialog):
        dialog.mode.setCurrentIndex(dialog.mode.findData("metric"))
        assert QPaintDevice.width(dialog.metric_color) > 0
        assert dialog.metric_color.count.value() == 20
        dialog.metric_color.count.setValue(31)

    accept_rendered_dialog(window.mask_colors_action.trigger, MaskColorsDialog, choose)
    assert len(set(window.canvas.object_colors.values())) == 31
    restored = Document(doc.frame)
    assert store.load(restored)[0] and restored.metric_color_scheme == MetricColorScheme(count=31)
    physical = metric_palette([doc], MetricColorScheme("perimeter", unit="nm"))
    assert not physical.colors

    window.plot_statistics()
    plot = window.stats_dialogs[0]
    qtbot.waitUntil(plot.isVisible)
    color_settings = next(button for button in plot.findChildren(QPushButton) if button.text() == "Mask color settings…")
    accept_rendered_dialog(color_settings.click, MaskColorsDialog,
                           lambda dialog: dialog.metric_color.count.setValue(24))
    assert doc.metric_color_scheme.count == 24 and plot.plot_type.currentData() == "points"
    plot.close()


def test_named_plot_group_scopes_colors_and_plot_points(window, qtbot, tmp_path):
    a, b, outside = [image(tmp_path, name) for name in ("a", "b", "outside")]
    for doc in (a, b, outside):
        doc.ensure_group("Particles")
        attach(window, doc, tmp_path)
    ids = {}
    for doc, size in ((a, 4), (b, 4), (outside, 80)):
        ids[doc.frame.key] = rectangle(doc, 2, 2, size, size).id
    larger = rectangle(b, 18, 2, 8, 8)
    window._refresh()
    for index in (0, 1):
        window.files_tree.topLevelItem(index).setSelected(True)

    def create(dialog):
        dialog.name.setText("Treatment")
        assert QPaintDevice.width(dialog.metric_color) > 0
        assert dialog.metric_color.count.value() == 20

    create_button = next(button for button in window.files_dock.widget().findChildren(QPushButton)
                         if button.text() == "Create…")
    accept_rendered_dialog(create_button.click, PlotGroupDialog, create)
    assert set(window.plot_groups["Treatment"].frames) == {a.frame.key, b.frame.key}
    assert window.active_plot_group == "Treatment"

    def edit(dialog):
        assert QPaintDevice.width(dialog.metric_color) > 0
        dialog.metric_color.count.setValue(28)

    accept_rendered_dialog(window.edit_plot_group_button.click, PlotGroupDialog, edit)
    assert window.plot_groups["Treatment"].scheme.count == 28
    outside_id = ids[outside.frame.key]
    assert window.canvas.object_colors[outside_id] == outside.objects[0].color
    window.select_document(b.frame.key)
    b_colors = dict(window.canvas.object_colors)
    assert b_colors[ids[b.frame.key]] != b_colors[larger.id]
    assert b_colors[ids[b.frame.key]] == window._mask_colors(a)[ids[a.frame.key]]
    exported = render_mask_pixels(b, b.objects, "object_color", object_colors=b_colors)
    assert tuple(exported[3, 3, :3]) == hex_rgb(b_colors[ids[b.frame.key]])

    window.plot_statistics()
    plot = window.stats_dialogs[0]
    qtbot.waitUntil(plot.isVisible)
    plot.unit.setCurrentText("Pixels")
    assert plot.plot_group_name == "Treatment" and plot.plot_type.currentData() == "points"
    [axis] = plot.figure.axes
    [scatter] = axis.collections
    assert list(scatter.get_offsets()[:, 0]) == [16., 16., 64.]
    assert list(map(to_hex, scatter.get_facecolors())) == [b_colors[ids[b.frame.key]]] * 2 + [b_colors[larger.id]]
    assert {record["image"] for record in plot.records} == {a.frame.source_path, b.frame.source_path}
    assert [record["mask_color"] for record in plot.records] == list(map(to_hex, scatter.get_facecolors()))
    color_settings = next(button for button in plot.findChildren(QPushButton) if button.text() == "Mask color settings…")
    accept_rendered_dialog(color_settings.click, PlotGroupDialog,
                           lambda dialog: dialog.metric_color.count.setValue(32))
    assert window.plot_groups["Treatment"].scheme.count == 32
    b_colors = dict(window.canvas.object_colors)
    for index in range(1, 11):
        plot.metrics_list.item(index).setCheckState(Qt.CheckState.Checked)
    assert len(plot.selected_metrics()) == 9
    assert outside_id not in {record["object_id"] for record in plot.records}

    window.set_active_plot_group(None)
    assert plot.plot_group_name is None
    plot.scope.setCurrentIndex(plot.scope.findData("plot:Treatment"))
    assert window.active_plot_group == "Treatment" and window.canvas.object_colors == b_colors
    assert "Treatment" in window.settings.value("plot_groups")

    plot.scope.setCurrentIndex(plot.scope.findData("selected"))
    accept_rendered_dialog(color_settings.click, PlotGroupDialog, lambda dialog: dialog.name.setText("Control"))
    assert plot.plot_group_name == "Control"
    assert window.plot_groups["Control"].frames == window.plot_groups["Treatment"].frames
    plot.close()
