"""Persistent scale-bar style and source-pixel length calculation."""
from dataclasses import dataclass
import math

import numpy as np

from .domain import LENGTH_UNITS

SCALE_BAR_POSITIONS = {
    "top-left": "Top left",
    "top-right": "Top right",
    "bottom-left": "Bottom left",
    "bottom-right": "Bottom right",
}


@dataclass(frozen=True)
class ScaleBar:
    length: float
    unit: str
    line_width: int = 3
    font_family: str = "Sans Serif"
    font_size: int = 14
    position: str = "bottom-right"

    def __post_init__(self):
        if (not isinstance(self.length, (int, float)) or isinstance(self.length, bool)
                or not math.isfinite(self.length) or self.length <= 0):
            raise ValueError("Scale bar length must be positive and finite.")
        if self.unit not in ("px", *LENGTH_UNITS):
            raise ValueError("Unknown scale bar unit.")
        if type(self.line_width) is not int or not 1 <= self.line_width <= 200:
            raise ValueError("Scale bar line width must be between 1 and 200 pixels.")
        if type(self.font_size) is not int or not 1 <= self.font_size <= 500:
            raise ValueError("Scale bar font size must be between 1 and 500 pixels.")
        if not isinstance(self.font_family, str) or not self.font_family.strip():
            raise ValueError("Choose a scale bar font.")
        if self.position not in SCALE_BAR_POSITIONS:
            raise ValueError("Choose a scale bar position.")

    def length_in_pixels(self, calibration):
        if self.unit == "px":
            return self.length
        if not calibration.valid:
            raise ValueError("A physical scale bar needs image calibration. Edit image calibration or use px.")
        pixel_size = np.linalg.norm(calibration.matrix(self.unit)[:, 0])
        return float(self.length / pixel_size)
