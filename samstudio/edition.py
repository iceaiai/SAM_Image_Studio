"""Offline CPU edition detection and local-only model resolution."""
import json
import os
from pathlib import Path

PROFILE=Path(__file__).resolve().parent/'resources/offline_profile.json'

def offline_profile():
    return json.loads(PROFILE.read_text()) if PROFILE.is_file() else None

def offline_root():
    override=os.environ.get('SAM_STUDIO_OFFLINE_ROOT')
    if override:return Path(override)
    for parent in Path(__file__).resolve().parents:
        if (parent/'offline-cache/manifest.json').is_file():return parent
    raise RuntimeError('The prepared offline-cache folder was not found. Launch from the complete prepared offline bundle.')

def local_model(spec):
    profile=offline_profile()
    if not profile:return None
    allowed=profile['models']
    if not any((s['family'],s['variant'])==(spec.family,spec.variant) for s in allowed):raise ValueError('This model is not included in the offline CPU edition.')
    root=offline_root();manifest=json.loads((root/'offline-cache/manifest.json').read_text())
    match=next((m for m in manifest['models'] if m['filename']==spec.filename),None)
    if not match:raise ValueError('The model is missing from the prepared offline manifest.')
    path=root/'offline-cache/models'/spec.filename
    from .inference import file_digest
    if not path.is_file() or file_digest(path)!=match['sha256']:raise ValueError('Offline model is missing/corrupt; rerun preparation online before transferring the complete folder.')
    return path
