"""Explicit, persistent aliases and optional Grounding DINO → SAM2 prompts."""
from __future__ import annotations

import re
import numpy as np

GROUNDING_MODEL = "IDEA-Research/grounding-dino-tiny"
GROUNDING_REVISION = "a2bb814dd30d776dcf7e30523b00659f4f141c71"


def validate_aliases(aliases):
    if not isinstance(aliases, dict) or len(aliases) > 1000:
        raise ValueError("Aliases must be a table of at most 1000 phrases.")
    result = {}
    for alias, target in aliases.items():
        if not isinstance(alias, str) or not isinstance(target, str):
            raise ValueError("Alias and effective prompt must be text.")
        key, value = alias.strip().casefold(), target.strip()
        if not key or not value or len(key) > 500 or len(value) > 500:
            raise ValueError("Alias and effective prompt must contain 1–500 characters.")
        if key in result:
            raise ValueError("Aliases must be unique (case insensitive).")
        result[key] = value
    # Aliases may target another alias, but cycles are never silently accepted.
    for key in result:
        seen = set()
        while key in result:
            if key in seen:
                raise ValueError("Prompt aliases contain a cycle.")
            seen.add(key)
            key = result[key].casefold()
    return result


def resolve_prompt(text, aliases):
    aliases = validate_aliases(aliases)
    text = text.strip()
    # Resolve each complete phrase separated by a period or semicolon; no
    # substring replacement (e.g. 'dot' must not change 'dotted line').
    phrases = [p.strip() for p in re.split(r"[.;]", text) if p.strip()]
    resolved = []
    for phrase in phrases:
        while phrase.casefold() in aliases:
            phrase = aliases[phrase.casefold()]
        resolved.append(phrase)
    return ". ".join(resolved)


class TextGrounder:
    def __init__(self):
        self.model = self.processor = None
        self.device = None

    def detect(self, rgb, text, device="cpu", threshold=.25, progress=None, cancel=None):
        from .inference import check_cancel
        import torch
        from PIL import Image
        try:
            from transformers import AutoProcessor, AutoModelForZeroShotObjectDetection
        except ImportError as error:
            raise RuntimeError("Install text support with: python -m pip install -r requirements-text.txt") from error
        check_cancel(cancel)
        if self.model is None or self.device != device:
            if progress:
                progress("Loading Grounding DINO Tiny (first use downloads public model weights)…")
            processor = AutoProcessor.from_pretrained(GROUNDING_MODEL, revision=GROUNDING_REVISION)
            model = AutoModelForZeroShotObjectDetection.from_pretrained(GROUNDING_MODEL, revision=GROUNDING_REVISION).to(device).eval()
            check_cancel(cancel)
            self.processor, self.model, self.device = processor, model, device
        if progress:
            progress("Locating text concepts with Grounding DINO…")
        caption = text.strip().lower().rstrip(".") + "."
        inputs = self.processor(images=Image.fromarray(np.asarray(rgb, np.uint8)), text=caption, return_tensors="pt").to(device)
        with torch.inference_mode():
            outputs = self.model(**inputs)
        check_cancel(cancel)
        result = self.processor.post_process_grounded_object_detection(
            outputs, inputs.input_ids, box_threshold=float(threshold), text_threshold=.25,
            target_sizes=[rgb.shape[:2]])[0]
        boxes = result["boxes"].detach().cpu().numpy()
        scores = result["scores"].detach().cpu().numpy()
        return boxes, scores
