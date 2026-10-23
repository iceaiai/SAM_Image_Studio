# Version 1.4.3 validation

These are current checkout checks, separate from the preserved v1.4.2 reports.
The machine runs Linux/Python 3.12 and has **no NVIDIA GPU**.

| Check | Result | What it establishes |
| --- | --- | --- |
| Full pytest suite | **460 passed, 35 skipped**, 0 failures/errors | Core editing, cleaning, exports, GUI, restoration (including small real N2V training), installer planning, model contracts and ONNX integration |
| CPU installation self-test | Passed | Imports, Torch/Torchvision native operations, exact COCO/native recovery and Qt window construction |
| Dependency check | Passed | `python -m pip check` found no broken requirements |
| Linux dependency detection | No missing Qt libraries in this instance | Actual detection path; missing-library installation logic is additionally tested with mocked apt commands |
| CPU launcher after file moves | `bash packaging/start_gui.sh --version` → 1.4.3 | Helper resolves the repository root correctly |
| GPU entry points | Both new and compatibility paths reported no GPU | No fake CUDA readiness claim |
| Genuine public SAM3 ONNX CLI | 10 masks, `white dots`, CPU provider in all graphs | Real encoder/language/decoder inference, original-size masks and filtering on the bundled image |
| Genuine Qt ONNX workflow | 10 whole-image masks; 5 accepted in left-half ROI; alias resolved; native project reopened | Model dialog/load worker, text run, exact ROI clipping, acceptance, provenance and persistence |
| Strict Sphinx HTML build | Passed with warnings as errors | Site and static API generation |
| Browser/local references | 75 HTML pages, 8,056 local references; navigation, new-page images, search and mobile checks passed | No broken local links/anchors/resources or browser JS errors in checked pages |
| Original artifacts | All five SHA-256 checks passed | Supplied ZIP, PDFs and notebook are unchanged |
| Wheel build | 1.4.3 wheel built successfully | Current application modules and help resources package successfully |

35 skipped cases need unavailable genuine SAM1/2/LaMa assets or external
microscopy reader fixtures. They are not counted as passed. The public ONNX
model is exercised separately with real weights; miniature ONNX graphs in
unit tests validate contracts only, not SAM accuracy.

The native SAM3 shared-feature repair, SAM3.1 box/session contracts, selected
object prompting, dynamic text labels and token redaction have regression
coverage. **Native SAM3/3.1 GPU weights, GPU ONNX, Windows, and a fresh WSL
system-library installation were not executed here.** No new GPU speed or
microscopy accuracy result is claimed.

The CLI run recorded 39.638 s for its first request (load/integrity checks
11.821 s), while the fresh Qt run recorded 28.971 s including its GUI worker.
These ran under variable CPU load and are execution evidence, not controlled
performance comparisons. Model initialization and first-image encoding are
separate from cached prompt updates. Exact providers, mask scores and scopes
are stored in the JSON records beside this file.

Reproduce in the installed environment from the repository root:

```sh
QT_QPA_PLATFORM=offscreen python -m pytest -q
python -m samstudio.selftest --device cpu
python scripts/smoke_sam3_onnx.py --image examples/synthetic_particles.ome.tif --model-dir /path/to/verified/export --text 'white dots' --device cpu
python scripts/smoke_sam3_onnx_gui.py --model-dir /path/to/verified/export
```

The GUI smoke uses a fresh temporary project/profile on every run; otherwise
previously accepted masks correctly suppress new proposals and would change
counts. No private uploaded image or Hugging Face token is included in these
published records or figures.
