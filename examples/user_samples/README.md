# User-supplied example images

These two original files were supplied for inclusion as examples:

| File | Reader / suggested first trial |
| --- | --- |
| `0058-Ceta_190_kx_1615.emd` | 1024 × 1024 signed-int16 TEM; spatial calibration is read from metadata. Try SAM3 ONNX `black dots`, or dark-foreground Otsu + watershed. |
| `STEM_image.tif` | 2048 × 2048 uint8 bright-particle STEM. Try `white dots` / `white circles` / `spheres`; generic `particles` can return zero with this export. Try bright-foreground Otsu + watershed. No physical calibration is inferred from appearance. |

Open through File → Open images… and select these files. Originals are retained;
noise, cleaning and other image processing affect derived pixels. No independent
reviewed segmentation ground truth is included. The real inference counts in
validation records describe these inputs and prompts, not universal accuracy.

The application code license does not automatically relicense the supplied image data.
