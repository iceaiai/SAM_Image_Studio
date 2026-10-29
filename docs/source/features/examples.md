# Example microscopy images

After downloading/extracting the application, open **File → Open images…** and
choose files in `examples/user_samples/`. Both supplied originals are included
unchanged. The [example folder on GitHub](https://github.com/iceaiai/SAM_Image_Studio/tree/main/examples/user_samples)
contains the source files and their provenance notes.

| Example | Source data | Calibration | Useful first trial |
| --- | --- | --- | --- |
| `0058-Ceta_190_kx_1615.emd` | 1,024 × 1,024, signed int16 | EMD metadata: 0.314412251423185 nm/pixel in X/Y | SAM3 ONNX `black dots`; dark Otsu + watershed |
| `STEM_image.tif` | 2,048 × 2,048, uint8 | No trustworthy physical scale found; calibrate before physical measurements | SAM3 ONNX `white dots`; bright Otsu + watershed |

## Real ONNX previews

```{image} ../_static/workflows/v144-emd-onnx.png
:alt: Actual EMD SAM3 ONNX CPU preview with black dots, 52 provisional masks
:width: 100%
```

```{image} ../_static/workflows/v144-stem-onnx.png
:alt: Actual STEM SAM3 ONNX CPU preview with white dots, 16 provisional masks
:width: 100%
```

These are genuine CPU model outputs. On this STEM input, `particles` returned
zero; literal visible descriptions (`white dots`, `white circles`, `spheres`)
returned 16 each. Results depend on wording, scores and scope; counts are not
accuracy measurements. The accepted left-half STEM ROI test produced 10 objects,
all contained by that ROI, and reopened them from the native project.

For a no-model alternative, compare the [watershed presets](../segmentation/watershed.md).
For low-range signed microscopy data, use the [noise examples](processing.md#noise-strength-in-image-data-units)
to compare derived pixels on a common intensity scale.
