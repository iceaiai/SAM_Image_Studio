import numpy as np
import pytest
from PySide6.QtCore import QPointF, QTimer, Qt
from PySide6.QtWidgets import QApplication, QDialog, QDialogButtonBox, QFileDialog, QInputDialog, QMenu, QPushButton
from samstudio.imageio import LoadResult
from samstudio.dialogs import RefinementDialog,SaveMasksDialog,ImageExportDialog
from samstudio.processing import push_mask_segment, shape_mask


def mount(window,document):
    window._opened(LoadResult([document.frame]))
    window.document.restore(document.state());window._persist(window.document);window._refresh()
    return window.document


@pytest.mark.parametrize("method",["neighbors","patches"])
def test_gui_cleaning_fill_apply_and_exact_undo(window,document,qtbot,monkeypatch,method):
    doc=mount(window,document);raw=doc.frame.raw.copy()
    doc.draft["roi"]={"kind":"rectangle","points":[[65,50],[95,80]]}
    window.remove_area();removed=doc.working.copy();assert doc.removed.any()
    if method=="patches":
        active=doc.active_group;group=doc.ensure_group("Reference texture")
        for corners in ([[2,70],[20,90]],[[110,10],[135,40]]):
            doc.add_object("rectangle",corners,shape_mask("rectangle",corners,doc.frame.shape),{"method":"manual"})
        doc.background_group_id=group.id;doc.active_group=active
    monkeypatch.setattr(QDialog,"exec",lambda self:QDialog.DialogCode.Accepted)
    window.fill_removed(method);qtbot.waitUntil(lambda:not window.busy,timeout=20000)
    assert not window.errors and not doc.removed.any()
    target=doc.modified;assert np.array_equal(doc.working[~target],raw[~target])
    assert doc.working.dtype==raw.dtype
    window.undo();assert doc.removed.any() and np.array_equal(doc.working,removed)


@pytest.mark.parametrize("method",["holes","smooth"])
def test_gui_refinement_preview_apply_recalculates_and_undo(window,document,qtbot,monkeypatch,method):
    doc=mount(window,document);window.canvas.set_selected([doc.objects[0].id]);window._refresh()
    original=doc.objects[0].mask.copy();ident=doc.objects[0].id
    def accept(dialog):
        dialog.calculate()
        assert dialog.results
        return QDialog.DialogCode.Accepted
    monkeypatch.setattr(RefinementDialog,"exec",accept)
    window.refine_masks(method)
    assert doc.objects[0].id==ident and doc.objects[0].provenance["last_refinement"]
    assert not np.array_equal(doc.objects[0].mask,original)
    window.undo();assert np.array_equal(doc.objects[0].mask,original)


def test_disconnected_mask_pieces_can_be_removed_by_click_and_refinement(window, document, qtbot):
    document.objects.clear()
    main = np.zeros(document.frame.shape, bool)
    main[52:100, 40:63] = True
    line = np.zeros_like(main)
    line[31, 25:32] = True
    triangle = shape_mask("polygon", [[72, 18], [94, 18], [78, 29]], main.shape)
    mask = main | line | triangle
    ident = document.add_object("mask", mask=mask.copy()).id
    neighbor = np.zeros_like(main)
    neighbor[20:24, 76:83] = True
    other = document.add_object("mask", mask=neighbor.copy()).id
    doc = mount(window, document)
    window.mode.setCurrentText("Edit")
    canvas = window.canvas
    canvas.scale = 3
    canvas.offset = QPointF(16, 16)

    def remove_from_popup():
        menu = QApplication.activePopupWidget()
        assert isinstance(menu, QMenu)
        try:
            action = next(action for action in menu.actions() if action.text() == "Remove this disconnected part")
            action.trigger()
        finally:
            menu.close()

    QTimer.singleShot(0, remove_from_popup)
    qtbot.mouseClick(canvas, Qt.MouseButton.RightButton, pos=canvas.to_widget((28.5, 31.5)).toPoint())
    assert doc.objects[0].id == ident
    np.testing.assert_array_equal(doc.objects[0].mask, main | triangle)
    window.undo()
    np.testing.assert_array_equal(doc.objects[0].mask, mask)

    window.tool_actions["mask_part"].trigger()
    part_position = canvas.to_widget((28.5, 31.5)).toPoint()
    qtbot.keyClick(canvas, Qt.Key.Key_Delete)
    np.testing.assert_array_equal(doc.objects[0].mask, mask)
    qtbot.mouseClick(canvas, Qt.MouseButton.LeftButton, pos=part_position)
    assert canvas.selected_mask_part() == (ident, 28, 31) and not canvas.grab().isNull()
    qtbot.keyClick(canvas, Qt.Key.Key_Escape)
    assert canvas.selected_mask_part() is None
    qtbot.mouseClick(canvas, Qt.MouseButton.LeftButton, pos=part_position)
    assert canvas.selected_mask_part() == (ident, 28, 31)
    qtbot.keyClick(canvas, Qt.Key.Key_Delete)
    assert [obj.id for obj in doc.objects] == [ident, other]
    np.testing.assert_array_equal(doc.objects[0].mask, main | triangle)
    window.undo()
    window.tool_actions["select"].trigger()
    np.testing.assert_array_equal(doc.objects[0].mask, mask)

    def refine(included, largest, expected):
        window.canvas.set_selected(included)
        window._refresh()

        def apply():
            dialog = QApplication.activeModalWidget()
            assert isinstance(dialog, QDialog)
            try:
                assert isinstance(dialog, RefinementDialog)
                if not largest:
                    dialog.part_policy.setCurrentIndex(dialog.part_policy.findData("minimum"))
                    dialog.value.setValue(8)
                preview = next(button for button in dialog.findChildren(QPushButton) if button.text() == "Preview")
                preview.click()
                np.testing.assert_array_equal(dialog.results[ident], expected)
                assert not dialog.grab().isNull()
                dialog.controls.button(QDialogButtonBox.StandardButton.Ok).click()
            finally:
                if dialog.isVisible():
                    dialog.reject()

        QTimer.singleShot(0, apply)
        window.refine_parts_action.trigger()
        assert [obj.id for obj in doc.objects] == [ident, other]
        np.testing.assert_array_equal(doc.objects[0].mask, expected)
        np.testing.assert_array_equal(doc.objects[1].mask, neighbor)

    refine({ident}, False, main | triangle)
    window.undo()
    refine({ident, other}, True, main)
    assert doc.objects[0].contours is None and not window.errors


def test_vertex_deletion_has_a_ten_vertex_limit_and_one_undo(window, document, qtbot):
    document.objects.clear()
    angles = np.linspace(0, 2 * np.pi, 18, endpoint=False)
    points = (np.column_stack((np.cos(angles), np.sin(angles))) * 26 + [56, 50]).tolist()
    original = shape_mask("polygon", points, document.frame.shape)
    ident = document.add_object("polygon", points, original).id
    doc = mount(window, document)
    window.mode.setCurrentText("Edit")
    canvas = window.canvas
    canvas.set_selected({ident})
    window._refresh()
    window.vertex_count.setValue(100)
    assert window.vertex_count.value() == 10
    window.vertex_radius.setValue(100)
    qtbot.mouseClick(canvas, Qt.MouseButton.LeftButton, pos=canvas.to_widget(points[0]).toPoint())
    before = len(window.histories[doc.frame.key].undo_stack)
    qtbot.keyClick(canvas, Qt.Key.Key_Delete)
    assert len(doc.objects[0].points) == 8 and doc.objects[0].id == ident
    assert len(window.histories[doc.frame.key].undo_stack) == before + 1
    qtbot.keyClick(canvas, Qt.Key.Key_Delete)
    assert len(doc.objects[0].points) == 3
    qtbot.keyClick(canvas, Qt.Key.Key_Delete)
    assert len(doc.objects[0].points) == 3 and len(window.histories[doc.frame.key].undo_stack) == before + 2
    window.undo()
    window.undo()
    np.testing.assert_array_equal(doc.objects[0].mask, original)
    assert doc.objects[0].points == points and not window.errors


def test_mask_pusher_edits_only_the_swept_ring_and_is_undoable(window, document, qtbot):
    document.objects.clear()
    original = np.zeros(document.frame.shape, bool)
    original[32:81, 35:89] = True
    ident = document.add_object("mask", mask=original.copy()).id
    untouched = np.zeros_like(original)
    untouched[56:66, 20:29] = True
    document.add_object("mask", mask=untouched.copy())
    doc = mount(window, document)
    canvas = window.canvas
    window.mode.setCurrentText("Edit")
    canvas.set_selected({ident})
    window._refresh()
    tool = window.tool_actions["mask_pusher"]
    button = window.drawing_toolbars[1].widgetForAction(tool)
    qtbot.mouseClick(button, Qt.MouseButton.LeftButton)
    assert canvas.tool == "mask_pusher"
    qtbot.waitUntil(lambda: window.pusher_radius.isVisible() and not window.vertex_radius.isVisible())
    window.pusher_radius.setValue(8)
    canvas.scale = 2
    canvas.offset = QPointF(12, 16)
    raw = doc.frame.raw.copy()

    def drag(button, start, finish):
        p0, p1 = [canvas.to_widget(point).toPoint() for point in (start, finish)]
        before = doc.objects[0].mask.copy()
        qtbot.mousePress(canvas, button, pos=p0)
        qtbot.mouseMove(canvas, pos=p1)
        assert canvas._pusher_stroke.preview is not None and not canvas.grab().isNull()
        np.testing.assert_array_equal(doc.objects[0].mask, before)
        qtbot.mouseRelease(canvas, button, pos=p1)
        changed = doc.objects[0].mask ^ before
        y, x = np.ogrid[:before.shape[0], :before.shape[1]]
        dx, dy = np.subtract(finish, start)
        x, y = x + .5 - start[0], y + .5 - start[1]
        t = np.clip((x * dx + y * dy) / (dx * dx + dy * dy), 0, 1)
        swept = (x - t * dx) ** 2 + (y - t * dy) ** 2 <= 8 ** 2 + 1e-10
        assert changed.any() and not changed[~swept].any()
        np.testing.assert_array_equal(doc.objects[1].mask, untouched)
        np.testing.assert_array_equal(doc.frame.raw, raw)

    drag(Qt.MouseButton.LeftButton, (33, 50), (24, 58))
    left_added = doc.objects[0].mask.copy()
    assert left_added.sum() > original.sum() and not (original & ~left_added).any()
    drag(Qt.MouseButton.LeftButton, (88, 51), (98, 61))
    added = doc.objects[0].mask.copy()
    assert (added[:, 89:] & ~left_added[:, 89:]).any()
    np.testing.assert_array_equal(added[:, :70], left_added[:, :70])
    drag(Qt.MouseButton.RightButton, (35, 46), (45, 46))
    carved = doc.objects[0].mask
    assert carved.sum() < added.sum() and not (carved & ~added).any()
    assert doc.objects[0].id == ident and doc.objects[0].contours is None
    window.undo()
    np.testing.assert_array_equal(doc.objects[0].mask, added)
    window.undo()
    np.testing.assert_array_equal(doc.objects[0].mask, left_added)
    window.undo()
    np.testing.assert_array_equal(doc.objects[0].mask, original)

    path = [canvas.to_widget(point).toPoint() for point in ((35, 50), (8, 50), (8, 10), (55, 10), (55, 35))]
    qtbot.mousePress(canvas, Qt.MouseButton.LeftButton, pos=path[0])
    for point in path[1:]:
        qtbot.mouseMove(canvas, pos=point)
    qtbot.mouseRelease(canvas, Qt.MouseButton.LeftButton, pos=path[-1])
    edited = doc.objects[0].mask
    additions = edited & ~original
    removals = original & ~edited
    assert additions[42:58, :35].any() and removals[32:40, 48:62].any()
    assert not additions[:, :18].any() and not additions[:32].any()
    window.undo()
    np.testing.assert_array_equal(doc.objects[0].mask, original)

    location = canvas.to_widget((37, 52)).toPoint()
    before = doc.state()
    qtbot.mousePress(canvas, Qt.MouseButton.RightButton, pos=location)
    qtbot.keyClick(canvas, Qt.Key.Key_Escape)
    qtbot.mouseRelease(canvas, Qt.MouseButton.RightButton, pos=location)
    assert canvas.tool == "select" and not tool.isChecked()
    assert canvas._pusher_stroke is None and doc.state() == before
    tool.trigger()
    qtbot.mouseClick(canvas, Qt.MouseButton.LeftButton, pos=canvas.to_widget((120, 90)).toPoint())
    assert doc.state() == before
    window.pusher_radius.setValue(300)
    qtbot.mouseClick(canvas, Qt.MouseButton.RightButton, pos=location)
    assert doc.state() == before and "erase the entire" in window.statusBar().currentMessage()
    window._commit("Lock mask", lambda: setattr(doc.objects[0], "locked", True))
    assert not tool.isEnabled() and canvas.tool == "select" and not window.errors


@pytest.mark.parametrize("vertical", [False, True], ids=["horizontal", "vertical"])
def test_mask_pusher_moves_inward_on_a_reverse_drag(window, document, qtbot, vertical):
    document.objects.clear()
    original = np.zeros(document.frame.shape, bool)
    original[35:89, 35:89] = True
    object_id = document.add_object("mask", mask=original.copy()).id
    doc = mount(window, document)
    window.mode.setCurrentText("Edit")
    canvas = window.canvas
    canvas.set_selected({object_id})
    window._refresh()
    window.tool_actions["mask_pusher"].trigger()
    window.pusher_radius.setValue(8)
    canvas.scale = 2
    canvas.offset = QPointF(12, 16)

    def position(x, y):
        return canvas.to_widget((y, x) if vertical else (x, y)).toPoint()

    left = Qt.MouseButton.LeftButton
    start, end = position(84, 56), position(99, 56)
    before = doc.state()
    qtbot.mouseClick(canvas, left, pos=start)
    assert doc.state() == before

    # Reverse while holding the button, then release the restored preview.
    qtbot.mousePress(canvas, left, pos=start)
    for x in range(85, 100):
        qtbot.mouseMove(canvas, pos=position(x, 56))
    pushed = canvas._pusher_stroke.mask.copy()
    assert (pushed & ~original).any() and not (original & ~pushed).any()
    np.testing.assert_array_equal(doc.objects[0].mask, original)
    qtbot.mouseMove(canvas, pos=start)
    assert canvas._pusher_stroke.preview is None
    qtbot.mouseRelease(canvas, left, pos=start)
    assert doc.state() == before and not window.histories[doc.frame.key].undo_stack

    # A single coalesced move applies the same deformation on release.
    qtbot.mousePress(canvas, left, pos=start)
    qtbot.mouseRelease(canvas, left, pos=end)
    np.testing.assert_array_equal(doc.objects[0].mask, pushed)

    # Start a new stroke on the outside of the edited edge and push it inward.
    qtbot.mousePress(canvas, left, pos=end)
    qtbot.mouseMove(canvas, pos=start)
    assert canvas._pusher_stroke.preview is not None
    qtbot.mouseRelease(canvas, left, pos=start)
    inward = doc.objects[0].mask
    assert (pushed & ~inward).any() and not (inward & ~pushed).any()

    # The opposite edge also moves inward when approached from outside.
    qtbot.mousePress(canvas, left, pos=position(26, 56))
    qtbot.mouseRelease(canvas, left, pos=position(44, 56))
    opposite = doc.objects[0].mask
    assert (inward & ~opposite).any() and not (opposite & ~inward).any()
    axis_region = np.s_[65:, :] if vertical else np.s_[:, 65:]
    np.testing.assert_array_equal(inward[axis_region], opposite[axis_region])
    assert len(window.histories[doc.frame.key].undo_stack) == 3
    assert not window.errors


def test_delete_vertex_and_tool_changes_leave_mask_pusher(window, document, qtbot):
    document.objects.clear()
    points = [[35, 48], [49, 33], [68, 36], [85, 50], [76, 70], [62, 85], [42, 82], [30, 68]]
    mask = shape_mask("polygon", points, document.frame.shape)
    object_id = document.add_object("polygon", points, mask).id
    doc = mount(window, document)
    window.mode.setCurrentText("Edit")
    canvas = window.canvas
    canvas.set_selected({object_id})
    window._refresh()
    pusher = window.tool_actions["mask_pusher"]
    delete_vertex = window.drawing_toolbars[1].widgetForAction(window.delete_vertex_action)
    vertex = canvas.to_widget(points[0]).toPoint()
    left = Qt.MouseButton.LeftButton
    before = doc.state()

    qtbot.mouseClick(canvas, left, pos=vertex)
    pusher.trigger()
    qtbot.mouseMove(canvas, pos=vertex)
    assert canvas._cursor is not None
    qtbot.mouseClick(delete_vertex, left)
    assert canvas.tool == "select" and window.tool_actions["select"].isChecked() and not pusher.isChecked()
    assert canvas._cursor is None and canvas._pusher_stroke is None and doc.state() == before
    qtbot.waitUntil(lambda: window.vertex_radius.isVisible() and not window.pusher_radius.isVisible())

    qtbot.mouseClick(canvas, left, pos=vertex)
    qtbot.mouseClick(delete_vertex, left)
    assert len(doc.objects[0].points) == len(points) - 1 and doc.objects[0].id == object_id
    before = doc.state()

    pusher.trigger()
    start, end = [canvas.to_widget(point).toPoint() for point in ((80, 50), (97, 50))]
    qtbot.mousePress(canvas, left, pos=start)
    qtbot.mouseMove(canvas, pos=end)
    assert canvas._pusher_stroke.preview is not None
    window.tool_actions["measure_line"].trigger()
    qtbot.mouseRelease(canvas, left, pos=end)
    assert canvas.tool == "measure_line" and canvas._cursor is None and not pusher.isChecked()
    assert canvas._pusher_stroke is None and doc.state() == before

    pusher.trigger()
    qtbot.keyClick(canvas, Qt.Key.Key_Escape)
    assert canvas.tool == "select" and window.tool_actions["select"].isChecked() and not pusher.isChecked()
    assert canvas._cursor is None and doc.state() == before and not window.errors


def test_mask_pusher_preserves_a_thin_mask_across_processing_tiles():
    source = np.zeros((128, 160), bool)
    source[12:122, 66:69] = True
    path = [(x, 66) for x in range(60, 83)]
    edited = source.copy()
    offsets = {}
    for start, end in zip(path, path[1:]):
        push_mask_segment(edited, source, offsets, start, end, 12)

    assert edited[12:122].any(axis=1).all()
    assert (edited & ~source).any() and (source & ~edited).any()
    tiled = np.zeros((540, 560), bool)
    region = np.s_[188:316, 189:349]
    tiled[region] = source
    result = tiled.copy()
    push_mask_segment(result, tiled, {}, (60 + 189, 66 + 188), (82 + 189, 66 + 188), 12)
    expected = tiled.copy()
    expected[region] = edited
    np.testing.assert_array_equal(result, expected)


def test_gui_save_export_commands_create_files(window,document,tmp_path,monkeypatch):
    mount(window,document)
    monkeypatch.setattr(QFileDialog,"getExistingDirectory",lambda *a,**k:str(tmp_path/"output"))
    monkeypatch.setattr(SaveMasksDialog,"exec",lambda self:QDialog.DialogCode.Accepted)
    window.save_mask_dialog()
    assert list((tmp_path/"output").glob("*.bmp"))
    window.save_mask_dialog(True);assert list((tmp_path/"output").glob("*.png"))
    monkeypatch.setattr(QInputDialog,"getItem",lambda *a,**k:("Current image",True))
    monkeypatch.setattr(ImageExportDialog,"exec",lambda self:QDialog.DialogCode.Accepted)
    window.export_dataset("coco")
    assert (tmp_path/"output"/"annotations.coco.json").exists() and not window.errors
