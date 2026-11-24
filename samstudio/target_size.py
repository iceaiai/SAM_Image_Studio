"""Convert optional segmentation size bounds to clipped mask pixel counts."""
from dataclasses import dataclass
import math

from .domain import Calibration, LENGTH_UNITS

PHYSICAL_UNITS = ("pm", "Å", "nm", "µm", "mm", "m")


@dataclass(frozen=True)
class TargetSizeRange:
    metric: str = "area"
    unit: str = "px"
    minimum: float | None = None
    maximum: float | None = None
    pixel_size_x: float | None = None
    pixel_size_y: float | None = None
    pixel_unit: str = "nm"

    @property
    def enabled(self):
        return self.minimum is not None or self.maximum is not None

    def pixel_bounds(self, calibration):
        if not self.enabled:
            return None
        if self.metric not in ("area", "diameter") or self.unit not in ("px", *LENGTH_UNITS):
            raise ValueError("Choose a supported size measurement and unit.")
        values = (self.minimum, self.maximum)
        if any(n is not None and (not math.isfinite(n) or n < 0) for n in values):
            raise ValueError("Size limits must be finite and nonnegative.")
        if None not in values and self.minimum > self.maximum:
            raise ValueError("Minimum size cannot exceed maximum size.")
        pixel_area = 1.
        if self.unit != "px":
            if self.pixel_size_x is not None or self.pixel_size_y is not None:
                calibration = Calibration(self.pixel_size_x, self.pixel_size_y,
                                          self.pixel_unit, "Segmentation override", True)
            if not calibration or not calibration.valid:
                raise ValueError("Physical size limits need image calibration or positive X and Y pixel sizes.")
            pixel_area = calibration.area(1, self.unit)
        if not math.isfinite(pixel_area) or pixel_area <= 0:
            raise ValueError("The pixel area cannot be represented in the selected unit.")

        def to_pixels(value):
            area = value if self.metric == "area" else (value * (math.pi / 4)) * value
            pixels = area / pixel_area
            if not math.isfinite(pixels):
                raise ValueError("The target size is too large for the selected pixel size.")
            return pixels

        return tuple(to_pixels(value) if value is not None else None for value in values)


def within_size(pixel_count, area_range):
    if area_range is None:
        return True
    lower, upper = area_range
    return ((lower is None or pixel_count >= lower or math.isclose(pixel_count, lower, rel_tol=1e-12))
            and (upper is None or pixel_count <= upper or math.isclose(pixel_count, upper, rel_tol=1e-12)))
