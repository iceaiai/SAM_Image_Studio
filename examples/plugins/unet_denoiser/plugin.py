"""API v1 example: a user-trained TorchScript U-Net, tiled with overlap blending."""

from pathlib import Path
import numpy as np


def denoise(context):
    import torch

    context.check_cancelled()
    p = context.parameters
    path = Path(p["checkpoint"]).expanduser()
    if not path.is_file():
        raise ValueError("Choose your trained TorchScript checkpoint file.")
    if context.image.ndim != 2:
        raise ValueError("This example expects a grayscale TEM/SEM image.")
    device = p.get("device", "cpu")
    if device.startswith("cuda"):
        import os

        if not os.environ.get("CONDA_PREFIX"):
            raise ValueError("GPU plugins must run inside Conda.")
        if not torch.cuda.is_available():
            raise ValueError("CUDA is unavailable.")
    model = torch.jit.load(str(path), map_location=device).eval()
    a = context.image
    low, high = (
        (0.0, float(np.iinfo(a.dtype).max))
        if a.dtype.kind == "u"
        else (float(a.min()), float(a.max()))
    )
    span = high - low or 1.0
    unit = (a.astype(np.float32) - low) / span
    tile = int(p["tile_size"])
    overlap = int(p["overlap"])
    if tile < 16 or tile % 4 or not 0 <= overlap < tile // 2:
        raise ValueError(
            "tile_size must be divisible by 4 and overlap must be less than half a tile."
        )
    stride = tile - overlap
    h, w = a.shape
    ph = max(tile, ((h - tile + stride - 1) // stride) * stride + tile)
    pw = max(tile, ((w - tile + stride - 1) // stride) * stride + tile)
    padded = np.pad(
        unit, ((0, ph - h), (0, pw - w)), mode="reflect" if min(h, w) > 1 else "edge"
    )
    output = np.zeros_like(padded, dtype=np.float64)
    weights = np.zeros_like(output)
    blend = np.maximum(np.outer(np.hanning(tile), np.hanning(tile)), 1e-3)
    tiles = [
        (y, x)
        for y in range(0, ph - tile + 1, stride)
        for x in range(0, pw - tile + 1, stride)
    ]
    with torch.inference_mode():
        for i, (y, x) in enumerate(tiles):
            context.check_cancelled()
            context.progress(f"U-Net tile {i+1}/{len(tiles)}")
            tensor = torch.from_numpy(padded[y : y + tile, x : x + tile].copy())[
                None, None
            ].to(device)
            result = model(tensor)
            if result.shape != tensor.shape:
                raise ValueError("The model must return [1,1,tile,tile].")
            value = result[0, 0].detach().float().cpu().numpy()
            if not np.isfinite(value).all():
                raise ValueError("The model returned nonfinite pixels.")
            output[y : y + tile, x : x + tile] += value * blend
            weights[y : y + tile, x : x + tile] += blend
    restored = np.clip(output[:h, :w] / weights[:h, :w], 0, 1) * span + low
    if a.dtype.kind in "iu":
        restored = np.rint(restored)
    return restored.astype(a.dtype)


def register(api):
    api.add_image_processor(
        "U-Net denoise",
        denoise,
        {
            "checkpoint": {"default": ""},
            "device": {"default": "cpu"},
            "tile_size": {"default": 256, "min": 16, "max": 2048, "step": 4},
            "overlap": {"default": 32, "min": 0, "max": 512, "step": 1},
        },
    )
