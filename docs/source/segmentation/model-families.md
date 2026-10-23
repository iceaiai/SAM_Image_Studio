# Detection and segmentation across SAM families

## Detection answers "where?"; segmentation answers "which pixels?"

A detector proposes target locations, often boxes and scores. A segmenter
predicts a pixel mask from image features and prompts. SAM Image Studio combines
these differently for each family; the presence of a text box does not make
every underlying SAM version a native text detector.

| Family | Point/shape mask prediction | Text-driven target finding | Whole-image similar-object search | Runtime in this release |
| --- | --- | --- | --- | --- |
| SAM1 | Native point/box-prompt segmentation | Not available | Application candidate generation and exemplar retrieval | CPU or Conda CUDA |
| SAM2 / SAM2.1 | Native point/box-prompt segmentation | External Grounding DINO Tiny detects boxes, then SAM2 segments them | Application exemplar retrieval; text can supply candidate boxes | CPU or Conda CUDA |
| SAM3 | Native interactive mask path | Native image concept prompting | Native image concept/geometric prompts, prepared by the app | Optional Linux/WSL2 Conda CUDA |
| SAM3.1 | Official multiplex predictor adapted to a single image | Native multiplex text/concept request | Multiple concept boxes sent together in a single prompt request | Optional Linux/WSL2 Conda CUDA; own weights |

## SAM1: object prompts, grid candidates, and retrieval

For one object, a point or area-derived box prompts the native predictor.
The model returns a mask and quality score. It does not directly understand
`black dots` in this application; SAM1 hides the text controls.

For **Prompt project, whole image**, the app builds candidate masks using
grid prompts and positive exemplars, supplements small-object candidates using
template-correlation seeds, pools SAM features, and compares appearance/shape
descriptors with positive and negative examples. Filters remove unsuitable,
protected, too-small, or duplicate proposals. This is an application retrieval
heuristic; it is not native semantic concept propagation or a trained
nanoparticle classifier.

## SAM2/2.1: the text detection → mask pipeline

With a text prompt, the app resolves aliases and sends the phrase/image to the
pinned **Grounding DINO Tiny** detector. Its text-conditioned boxes are passed
to the selected SAM2/2.1 predictor, which supplies the pixel masks. The app then
applies region/protection/area/duplicate filtering and presents a preview.

```text
Typed phrase → project alias resolution → Grounding DINO boxes
             → SAM2/2.1 masks → application filters → review → accept
```

The detector and SAM checkpoints are separate downloads. A box detection is
not yet a particle mask. Prompts that work for photographs may transfer poorly
to TEM/SEM. A threshold cannot repair a concept the detector does not locate.
Point/shape whole-image exemplar search uses the application's retrieval layer
described above.

## SAM3: native image concepts

The app's SAM3 processor sets an image, applies an optional native text prompt,
and adds positive/negative geometric prompts. Shape/point exemplars first
produce an instance mask whose bounding box becomes the concept example.
The native image processor uses normalized **center-X, center-Y, width, height**
boxes. This coordinate contract is different from the SAM3.1 adapter.

## SAM3.1: native multiplex concepts on one frame

The app loads `sam3.1_multiplex.pt` through
`build_sam3_multiplex_video_predictor`, with compilation, FA3, and warm-up
disabled. Each request creates a lossless PNG frame, starts a native session,
sends a frame-0 `add_prompt`, copies masks/scores, and closes the session.
This is a single-image adaptation, not a GUI video tracking workflow.

```text
Text and/or positive/negative examples → one native SAM3.1 concept request
                                      → masks/scores → app filters → preview
```

All concept boxes are passed **together** in normalized top-left
**X, Y, width, height** format. Area shapes become enclosing boxes; their exact
contours are not sent as arbitrary polygon prompts. Each point exemplar first
identifies a native instance, then its box describes the positive/negative
concept. The [SAM3.1 guide](sam31.md) explains the visible workflow and its scope.

## Automatic grid is a separate operation

**Automatic grid, unannotated only** places native positive point prompts on a
grid over unprotected pixels. It ignores the text field. The grid is not a
second invocation of text detection and does not use the active text alias.
The displayed count reports actual filtered proposals; zero is a result to
inspect, not proof of a successful particle detector.

## Review the outputs

The model's score is not a calibrated scientific probability. Check split/merged
instances, faint particles, contamination, overlap, and image edges. Measure
pixel and instance agreement against independently reviewed annotations for
your own data. No new GPU benchmark or general microscopy accuracy claim is
made by these descriptions.

Implementation reference: `inference.py`, `exemplars.py`, `text_prompts.py`,
`sam31_backend.py`, and `processing.filter_proposals()` in the
[source-generated API](../api.md).
