# Version 1.4.4 validation — 2026-10-29

## Application and real data

Full CPU regression: **484 passed, 35 skipped**, 45.55 seconds. Skips require
external SAM1/SAM2/LaMa checkpoints or original omitted microscopy test assets;
they are not counted as successful model inference. New tests cover signal-noise
units/fidelity/alpha, watershed ROI and touching particles, processed-input state,
forget/Undo, rotation reset/project recovery, panel selection and LaMa compositing
with a mocked graph. No new real LaMa checkpoint validation is claimed.

The two supplied public files were read through real EMD/TIFF readers. EMD is
1,024² int16 with metadata calibration 0.314412251423185 nm/pixel; TIFF is 2,048²
uint8 with no reliable physical scale. Original uploads are unchanged.

Real SAM3 ONNX CPU inference used the six verified public export files. EMD
`black dots`: 52 raw proposals (51 >= 0.70), GUI at 0.50: 52 preview masks.
STEM `particles`: zero raw proposals; `white dots`, `white circles` and `spheres`:
16 each. GUI displayed 16 for `white dots`, accepted 10 within a left-half ROI,
and reopened the saved native project with no mask pixels outside that ROI.
Persistent counts and per-image original-input defaults were checked in Qt.
No ground-truth accuracy/error or GPU speed measurements are claimed.

Real watershed examples: EMD dark/sigma2/min-area300/seed-distance35: 51;
STEM bright/sigma2/min-area1000/seed-distance100: 16. Other defaults unchanged.
Noise examples share the acquired image intensity scale.

## Installation and offline scope

- Forced Linux x86-64 managed runtime bootstrap extracted the SHA-verified
  CPython 3.12.15 distribution and ran it successfully.
- Windows PSF Python 3.12.10 NuGet was downloaded, SHA-verified and inspected for
  venv/ensurepip; it was not executed on Windows.
- Windows CPU dependency metadata resolved 122 packages without NVIDIA packages.
  This is not native Windows acceptance testing.
- The offline preparer downloaded/resolved/built 126 Linux CPU wheels. A fresh
  environment installed the complete hashed set with `--no-index --no-deps`,
  with network proxies deliberately unusable, passed `pip check` and every CPU
  installation self-test (including Torch/torchvision native ops and Qt).
- Full preparation then failed on the cloud-blocked official Meta checkpoint
  host. The configured Debian snapshot mirror was separately blocked, preventing
  verification of the clean-target OS-package cache. No READY marker was issued.
  Full three-checkpoint/OS-package offline preparation is therefore unverified.
- The restricted edition's catalog/CPU/network guards and cache-integrity checks
  were tested. It does not advertise SAM3, text inference or online model fallback.

This cloud has no NVIDIA GPU. Native SAM3/3.1 CUDA, Windows GUI/install execution,
and real LaMa inference remain outside this validation. The strict Sphinx build and desktop/mobile browser checks passed (81 pages,
8,953 local references, no broken local links/anchors, no missing local resources
or browser JavaScript errors). Normal/offline source archive checks follow publication.
