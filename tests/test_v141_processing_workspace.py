import json,threading
from pathlib import Path
import numpy as np
import pytest
from samstudio.domain import Document,History,unpack_array
from samstudio.image_processing import METHODS,parameters,process_pixels,retain_crop,paste_crop,processing_target,apply_processing

def mount(window,doc):
    from samstudio.domain import ProjectStore
    key=doc.frame.key;window.documents[key]=doc;window.stores[key]=ProjectStore(Path(doc.frame.source_path).parent/'SAM_Annotations');window.histories[key]=History(doc,lambda:window._persist(doc));window._rebuild_file_tree();window.select_document(key);return doc


def test_v14_annotation_workflow_is_retained(window, document):
    import inspect
    from samstudio.exports import export_coco
    mount(window, document)
    assert not hasattr(window, 'coco_editor') and not hasattr(document, 'coco_template')
    assert not hasattr(document.objects[0], 'coco_id')
    assert 'normalize_number_of_object' not in inspect.signature(export_coco).parameters
    assert window.groups_dock.isVisible()
    state = document.state(); state['schema_version'] = 4; state.pop('detached_crops')
    restored = Document(document.frame); restored.restore(state)
    assert restored.objects[0].to_dict() == document.objects[0].to_dict()
    assert restored.detached_crops == []


def test_remove_workspace_images_keeps_source_and_native_annotations(window, document):
    mount(window, document)
    source = Path(document.frame.source_path); before = source.read_bytes()
    native = window.stores[document.frame.key].path(document)
    window.remove_workspace_images({document.frame.key})
    assert not window.documents and native.exists() and source.read_bytes() == before
    assert not list(source.parent.glob('*.samstudio.coco.json'))
    assert not window.settings.value('last_files', [])


def test_removing_another_image_keeps_current_selection(window, document, tmp_path):
    from samstudio.domain import ImageFrame
    mount(window, document)
    other = Document(ImageFrame(str(tmp_path/'other.tif'), document.frame.raw.copy()))
    mount(window, other); window.select_document(document.frame.key)
    window.remove_workspace_images({other.frame.key})
    assert window.document is document and window.current_key == document.frame.key


@pytest.mark.parametrize('accept', [True, False])
def test_processing_gui_preview_apply_or_cancel(window, document, qtbot, monkeypatch, accept):
    from PySide6.QtWidgets import QDialog, QLabel
    from samstudio.processing_ui import ProcessingDialog
    from samstudio.dialogs import ImagePreviewDialog
    mount(window, document); before = document.state(); shown = []
    monkeypatch.setattr(ProcessingDialog, 'exec', lambda self: QDialog.DialogCode.Accepted)
    def preview(dialog):
        assert dialog.windowTitle() == 'Preview Gaussian smooth'
        assert any(label.pixmap() is not None and not label.pixmap().isNull() for label in dialog.findChildren(QLabel))
        shown.append(True)
        return QDialog.DialogCode.Accepted if accept else QDialog.DialogCode.Rejected
    monkeypatch.setattr(ImagePreviewDialog, 'exec', preview)
    window.process_image_dialog(['Gaussian smooth'])
    qtbot.waitUntil(lambda: not window.busy, timeout=5000)
    assert shown and not window.errors
    if accept:
        assert document.working is not None
        window.undo(); assert document.state()['objects'] == before['objects'] and document.working is None
    else:
        assert document.state() == before


def test_plugin_gui_worker_preview_and_apply(window, document, qtbot, monkeypatch):
    from PySide6.QtWidgets import QDialog
    from samstudio.processing_ui import ProcessingDialog
    from samstudio.dialogs import ImagePreviewDialog
    mount(window, document); shown = []
    monkeypatch.setattr(ProcessingDialog, 'exec', lambda self: QDialog.DialogCode.Accepted)
    def preview(dialog):
        assert dialog.windowTitle() == 'Plugin: Half intensity'
        shown.append(True); return QDialog.DialogCode.Accepted
    monkeypatch.setattr(ImagePreviewDialog, 'exec', preview)
    window._run_plugin_processor('test.preview', 'Half intensity', {'parameters': {}, 'function': lambda ctx: ctx.image // 2})
    qtbot.waitUntil(lambda: not window.busy, timeout=5000)
    assert shown and not window.errors and np.array_equal(document.working, document.frame.raw // 2)

@pytest.mark.parametrize('answer',['Yes','No'])
def test_startup_restore_asks_before_opening(window,monkeypatch,answer):
    from PySide6.QtWidgets import QMessageBox
    calls=[];monkeypatch.setattr(QMessageBox,'question',lambda *a,**k:getattr(QMessageBox.StandardButton,answer));window.open_paths=lambda paths:calls.extend(paths)
    window._offer_session_restore(['a.png']);assert calls==(['a.png'] if answer=='Yes' else [])
    if answer=='No':assert not window.settings.value('last_files',[])


@pytest.mark.parametrize('method',[m for m in METHODS if m not in ('Noise2Void','N2V2')])
@pytest.mark.parametrize('dtype',[np.uint16,np.float32])
def test_processing_methods_preserve_dtype_outside_region_and_restore(method,dtype):
    rng=np.random.default_rng(9);raw=rng.uniform(0,1,(40,48));raw=(raw*65535).astype(dtype) if dtype==np.uint16 else raw.astype(dtype)
    target=np.zeros(raw.shape,bool);target[5:35,6:42]=True
    values={'dictionary_iterations':2,'coding_iterations':4,'training_patches':64,'dictionary_atoms':8} if method=='Sparse dictionary learning' else {}
    result=process_pixels(raw,method,values,target=target)
    assert result.dtype==raw.dtype and result.shape==raw.shape and np.isfinite(result).all()
    assert np.array_equal(result[~target],raw[~target])


def test_noise_seed_reproducible_and_rgba_alpha_preserved():
    raw=np.full((20,30,4),120,np.uint8);raw[...,3]=np.arange(30)
    a=process_pixels(raw,'Gaussian noise',{'sigma':.1,'seed':5});b=process_pixels(raw,'Gaussian noise',{'sigma':.1,'seed':5})
    assert np.array_equal(a,b) and np.array_equal(a[...,3],raw[...,3]) and not np.array_equal(a[...,:3],raw[...,:3])


@pytest.mark.parametrize('method,p',[('Gaussian smooth',{'kernel_size':4}),('Median denoise',{'kernel_size':2}),('TV restoration',{'weight':float('nan')}),('Poisson noise',{'peak_counts':0})])
def test_invalid_processing_parameters_rejected(method,p):
    with pytest.raises(ValueError):parameters(method,p)


def test_crop_real_background_padding_protection_paste_and_recovery(document):
    doc=document;mask=np.zeros(doc.frame.shape,bool);mask[20:40,30:50]=True;mask[20:25,30:35]=False
    crop=retain_crop(doc,mask,'sample',True,3);x,y,w,h=crop['bbox'];assert [x,y,w,h]==[27,17,26,26]
    assert np.array_equal(unpack_array(crop['pixels']),doc.frame.raw[y:y+h,x:x+w])
    target=processing_target(doc);assert not target[y:y+h,x:x+w].any()
    modified=doc.frame.raw.copy();modified[target]=0;apply_processing(doc,modified,target,'Test rest',{})
    crop['protected']=False;target2=np.ones(doc.frame.shape,bool);modified[:]=0;apply_processing(doc,modified,target2,'Test all',{})
    paste_crop(doc,crop['id']);assert np.array_equal(doc.working[y:y+h,x:x+w],doc.frame.raw[y:y+h,x:x+w])
    state=doc.state();restored=Document(doc.frame);restored.restore(state);assert restored.detached_crops[0]['name']=='sample' and np.array_equal(restored.working,doc.working)


def test_processing_apply_undo_exact(document):
    before=document.state();history=History(document);target=processing_target(document);result=process_pixels(document.frame.raw,'Gaussian smooth',target=target)
    history.apply('Smooth',lambda:apply_processing(document,result,target,'Gaussian smooth',{}));assert document.working is not None
    history.undo();assert document.working is None and document.state()['objects']==before['objects']


def test_processing_dialog_resets_defaults_on_reopen(window):
    from samstudio.processing_ui import ProcessingDialog
    first=ProcessingDialog(['Gaussian smooth'],window);first.controls['kernel_size'].setValue(9)
    second=ProcessingDialog(['Gaussian smooth'],window);assert second.controls['kernel_size'].value()==5
    first.deleteLater();second.deleteLater()


def test_native_pdf_help_has_real_rendered_page(window,qtbot):
    from PySide6.QtCore import QSize
    dialog=window.open_pdf_help();assert dialog is not None and dialog.document.pageCount()>10
    image=dialog.document.render(0,QSize(600,800));assert not image.isNull()
    array=np.frombuffer(image.bits(),np.uint8,count=image.sizeInBytes()).reshape(image.height(),image.bytesPerLine())
    assert np.count_nonzero(array[:,:image.width()*4].reshape(image.height(),image.width(),4)[...,:3]<150)>1000
    dialog.close()


def test_pasted_crop_remains_exportable_after_rotation_and_recovery(document):
    from samstudio.transforms import rotate_document
    mask=np.zeros(document.frame.shape,bool);mask[70:110,110:150]=True
    crop=retain_crop(document,mask,'retain',True,3);pixels=unpack_array(crop['pixels']).copy();paste_crop(document,crop['id'])
    rotate_document(document,90,'rectangle')
    restored=Document(document.frame);restored.source_raw=document.source_raw;restored.restore(document.state())
    assert np.array_equal(unpack_array(restored.detached_crops[0]['pixels']),pixels)
    with pytest.raises(ValueError,match='coordinates'):paste_crop(restored,crop['id'])


