"""Official SAM3.1 multiplex predictor, used as a lossless single-frame session.

This adapter deliberately does not substitute SAM3 image weights for SAM3.1.
Video predictor boxes use normalized top-left XYWH (not center XYWH).
"""
from contextlib import contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory
import numpy as np
from PIL import Image
from .processing import bounding_box, shape_mask
from .domain import unpack_mask


class Sam31Backend:
    def __init__(self, native, device):
        self.native, self.device = native, device

    @contextmanager
    def session(self, rgb, cancel=None):
        from .inference import check_cancel
        import torch
        check_cancel(cancel)
        with torch.cuda.device(self.device), torch.inference_mode(), TemporaryDirectory(prefix='samstudio31_') as folder:
            path = Path(folder)/'image.png'
            Image.fromarray(np.asarray(rgb, np.uint8)).save(path)
            session_id = None
            try:
                session_id = self.native.handle_request({'type':'start_session', 'resource_path':str(path),
                    'offload_video_to_cpu':True})['session_id']
                check_cancel(cancel)
                yield session_id
            finally:
                if session_id is not None:
                    self.native.handle_request({'type':'close_session', 'session_id':session_id, 'run_gc_collect':False})

    def request(self, rgb, payload, cancel=None):
        from .inference import check_cancel
        with self.session(rgb, cancel) as sid:
            response = self.native.handle_request(dict(payload, type='add_prompt', session_id=sid, frame_index=0))
            check_cancel(cancel)
            output = response.get('outputs')
            if output is None:
                raise ValueError('SAM3.1 returned no output; reduce prompt count or check object capacity.')
            masks = np.asarray(output['out_binary_masks'], bool)
            scores = np.asarray(output['out_probs'], float).reshape(-1)
            if masks.size == 0:
                return [], []
            if masks.ndim != 3 or masks.shape[1:] != rgb.shape[:2] or len(scores) != len(masks) or not np.isfinite(scores).all():
                raise ValueError('SAM3.1 returned invalid mask dimensions or scores.')
            return list(masks), scores.tolist()

    def predict(self, rgb, points=None, box=None, cancel=None):
        h, w = rgb.shape[:2]
        if points:
            payload = {'points':[[float(np.clip(x/w,0,1)),float(np.clip(y/h,0,1))] for x,y,_ in points],
                       'point_labels':[int(p[2]) for p in points], 'obj_id':1, 'rel_coordinates':True}
        elif box is not None:
            x,y,x2,y2 = box
            payload = {'bounding_boxes':[[x/w,y/h,(x2-x)/w,(y2-y)/h]], 'bounding_box_labels':[1], 'clear_old_boxes':True}
        else:
            raise ValueError('Add a positive point or an area prompt.')
        masks, scores = self.request(rgb, payload, cancel)
        if not masks:
            raise ValueError('SAM3.1 found no object for this prompt.')
        best = int(np.argmax(scores))
        return masks[best], scores[best]

    def concepts(self, rgb, points=None, examples=None, text='', cancel=None):
        h,w = rgb.shape[:2]; boxes, labels = [], []
        for x,y,label in points or []:
            # Point exemplars first define an instance; its box then defines the
            # concept. Negative points describe a negative instance similarly.
            mask,_ = self.predict(rgb, [[x,y,1]], cancel=cancel)
            bx,by,bw,bh = bounding_box(mask)
            boxes.append([bx/w,by/h,bw/w,bh/h]); labels.append(int(label))
        for example in examples or []:
            region = unpack_mask(example['mask'], (h,w)) if example['kind']=='mask' else shape_mask(example['kind'],example['points'],(h,w))
            x,y,bw,bh = bounding_box(region)
            if not bw or not bh:
                raise ValueError('An example shape is empty.')
            boxes.append([x/w,y/h,bw/w,bh/h]); labels.append(int(example.get('label',1)))
        if not any(labels) and not text.strip():
            raise ValueError('Add a positive example or a text prompt.')
        payload = {'text':text.strip() or None, 'bounding_boxes':boxes or None,
                   'bounding_box_labels':labels or None, 'clear_old_boxes':True}
        # All positive/negative concept boxes must be sent together. Repeated
        # semantic add_prompt requests reset the native multiplex state.
        return self.request(rgb, payload, cancel)
