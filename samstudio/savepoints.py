"""Geometry savepoints. Temporary collections never enter project/autosave state."""
from __future__ import annotations
import copy
import hashlib
import json
from pathlib import Path
import uuid
import numpy as np
from PIL import Image
from .domain import Annotation, Group, atomic_write


def coordinate_signature(document):
    return hashlib.sha256(json.dumps([document.frame.key,document.frame.shape,document.rotation],sort_keys=True).encode()).hexdigest()


def capture(document, name='original'):
    if not name.strip():
        raise ValueError('Enter a savepoint name.')
    return {'schema':'samstudio-mask-savepoint-1','id':str(uuid.uuid4()),'name':name.strip(),
            'source_key':document.frame.key,'coordinates':coordinate_signature(document),
            'shape':list(document.frame.shape),'groups':[vars(g).copy() for g in document.groups],
            'objects':[o.to_dict() for o in document.objects if o.role=='object']}


def restore(document, snapshot):
    if snapshot.get('schema')!='samstudio-mask-savepoint-1' or snapshot.get('source_key')!=document.frame.key or snapshot.get('coordinates')!=coordinate_signature(document):
        raise ValueError('This savepoint belongs to a different image or rotation. Undo the rotation before restoring it.')
    saved=[Annotation.from_dict(o,document.frame.shape) for o in snapshot['objects']]
    if any(o.locked for o in document.objects if o.role=='object'):
        raise ValueError('Unlock objects before restoring a savepoint.')
    cleaning=[o for o in document.objects if o.role=='cleaning']
    if {o.id for o in cleaning}&{o.id for o in saved}:
        raise ValueError('A saved annotation is now a cleaning region. Restore that region first.')
    groups=[Group(**g) for g in snapshot['groups']]
    by_id={g.id:g for g in document.groups}
    for g in groups:
        if g.id not in by_id:
            document.groups.append(g);by_id[g.id]=g
    if any(o.group_id not in by_id for o in saved):
        raise ValueError('A saved group is missing.')
    document.objects=saved+cleaning
    document.next_object_number=max(document.next_object_number,len(document.objects)+1)


def write_local(snapshot, directory):
    directory=Path(directory)
    # Each savepoint owns a new directory; no previous original is overwritten.
    slug=''.join(c if c.isalnum() or c in '-_.' else '_' for c in snapshot['name'])[:70] or 'savepoint'
    target=directory/(slug+'_'+snapshot['id'][:8]);target.mkdir(parents=True,exist_ok=False)
    (target/'masks').mkdir()
    for obj in snapshot['objects']:
        item=Annotation.from_dict(obj,tuple(snapshot['shape']))
        if item.mask is not None:
            Image.fromarray(item.mask.astype(np.uint8)*255).save(target/'masks'/(item.id+'.png'))
    atomic_write(target/'snapshot.json',json.dumps(snapshot,allow_nan=False,indent=2).encode())
    return target


def read_local(path):
    path=Path(path)
    snapshot=json.loads((path/'snapshot.json' if path.is_dir() else path).read_text('utf-8'))
    if snapshot.get('schema')!='samstudio-mask-savepoint-1':
        raise ValueError('Choose a SAM Image Studio mask savepoint.')
    return snapshot
