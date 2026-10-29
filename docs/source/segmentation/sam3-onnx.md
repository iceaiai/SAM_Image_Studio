# SAM3 ONNX: public text segmentation

Choose this backend for SAM3 text segmentation without a Hugging Face login.
It uses the public X-AnyLabeling v3.0.0 ViT-H export through an independently
implemented ONNX Runtime adapter. It does not contain copied GPL application
code. Model artifacts keep their upstream SAM terms; public availability is
not an authentication bypass or a change to the license.

## Install and select

The standard CPU/GPU installers install the matching ONNX runtime automatically.
For an existing **dedicated** environment that only needs the runtime repair:

```sh
python scripts/install_onnx_runtime.py --device cpu
```

Use `--device cuda` only in a dedicated non-base Conda GPU environment with
the CUDA 12.x/cuDNN 9 stack. The legacy Torch CUDA 11.8 plan installs CPU ONNX
while retaining native SAM1/2 CUDA support. The
helper replaces the conflicting CPU/GPU ONNX distribution when necessary;
these distributions share a Python module and should not both be installed.

1. Open an image and choose/create a Group.
2. Choose **Load model… → SAM3 ONNX → ViT-H · text prompts**.
3. Choose CPU or the configured NVIDIA CUDA device.
4. Leave the model path blank for first download, or **Browse ONNX model folder…**.
5. Wait for verification and loaded model status.

The six model/sidecar files total about **3.53 GiB**, plus a small CLIP tokenizer.
Downloads use public GitHub Release URLs and pinned SHA-256 values. Later loads
reuse verified files; interrupted downloads resume. Local folders need all six
files. For offline use, also place `bpe_simple_vocab_16e6.txt.gz` in the folder,
or retain the app's verified tokenizer cache from an earlier download.

## Text, aliases and ROI

Set **Segment → Prompt project, whole image**. Enter `black dots`, click
**Run text segmentation**, inspect the preview and **Accept masks**. For the
bundled synthetic bright particles use `white dots` instead.

Use **Prompt aliases…** for project phrases such as `nanoparticles → black dots`.
The text tooltip shows the effective phrase. For an ROI, choose an area tool,
select **Inside ROI only**, draw the region and run text again. The app clips
output to the exact region; the encoder still uses whole-image context.

```{image} ../_static/sam3-onnx-demo.png
:alt: Genuine SAM3 ONNX CPU preview using the bundled synthetic bright-particle image, a text alias and left-half ROI
:width: 100%
```

*Genuine CPU inference with the public export, not native SAM3.1 and not a GPU
benchmark. The synthetic example produced 10 whole-image masks; an alias and
left-half ROI run accepted 5 masks, with no output outside the ROI. Counts do
not establish general detection accuracy.*

The image embedding is cached until pixels change; text features are cached
for reused phrases. First-request time therefore differs from a cached prompt
update. Each request still decodes masks and applies application filters.

## When computation finishes with no masks

The status bar now retains **Preview: N masks**. Its tooltip distinguishes raw
model proposals from score/area/scope/protection filtering. For an unchanged
shipped threshold, selecting ONNX starts at **0.50**; an explicitly customized
score remains yours. Check **Options…**, the active ROI and accepted/protected
annotations before deciding that rendering failed.

Real CPU tests on the [supplied examples](../features/examples.md):

| Input / phrase | Raw model proposals | Interpretation |
| --- | --- | --- |
| EMD / `black dots` | 52; 51 meet score 0.70 | GUI at 0.50 displayed 52 previews. |
| STEM / `particles` | 0 | No model proposals to display, even with lower application score. |
| STEM / `white dots` | 16 | GUI displayed 16; scores approximately 0.824–0.965. |
| STEM / `white circles` or `spheres` | 16 each | Wording describes visible bright round objects. |

The app does not silently replace your phrase. Try a short literal visual
phrase, then inspect the result. Turn **View / infer from processed image** off
to test the original data. New images default to original input, and toggling
preserves processing until you explicitly choose **Forget processed image…**.
These tests verify execution/display; without ground-truth masks they do not
measure segmentation error or guarantee detection for other images.

## Capabilities and limits

| Supported | Unavailable in this export |
| --- | --- |
| Text prompts, model scores, original-size masks | Native point/shape-only prompts |
| App aliases, score/area filtering, review/accept | Native positive/negative shape concepts |
| Exact ROI/inverse limits and accepted-object protection | Single-object interactive path and automatic grid |

The UI disables unsupported scope/polarity choices. Clear old point/example
prompts before running this text-only backend. Effective text must fit the
export's 32-token context (30 text tokens plus start/end); shorten long phrases
or aliases if the app reports a context-limit error. There is no zero-token
fallback. Original-image dimensions are preserved in returned masks.

For native geometric examples and combined text+shapes, follow the optional
[SAM3.1 installation](../installation-gpu.md) and
[SAM3.1 prompt guide](sam31.md). A public SAM3 ONNX graph is not native SAM3.1
and cannot be used as `sam3.1_multiplex.pt`.

## Check execution without Qt

From the repository root in the installed environment:

```sh
python scripts/smoke_sam3_onnx.py --image examples/synthetic_particles.ome.tif --model-dir /path/to/sam3-onnx --text 'white dots' --device cpu --report /tmp/sam3-onnx-report.json
```

On Windows use a quoted Windows folder/report path. Omit `--model-dir` to
use/download the app cache. CUDA requests require a real CUDA provider; a
missing GPU provider or session fallback raises an error instead of reporting
CPU as GPU. CPU is validated in this cloud; Windows/CUDA paths require testing
on your target machine.

## Files and provenance

The supported release contains `sam3_image_encoder.onnx`,
`sam3_language_encoder.onnx`, `sam3_decoder.onnx` and their three `.onnx.data`
sidecars. Do not rename a random export to these names: the hashes and graph
contracts are specific to this release. The official CLIP BPE tokenizer is
included with MIT attribution; its vocabulary downloads separately and is
also verified. See [sources and licenses](../provenance.md).
