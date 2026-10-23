<p class="studio-eyebrow">Microscopy · Segmentation · Image restoration</p>

# SAM Image Studio

<p class="studio-intro">Annotate microscopy images, find particles with Segment
Anything, restore image pixels, and turn reviewed masks into calibrated
measurements. A desktop workflow with editable projects and reversible changes.</p>

```{button-ref} installation
:color: primary
:shadow:

Install SAM Image Studio
```

```{button-ref} segmentation/sam31
:color: secondary
:outline:

SAM3.1 text & shape prompts
```

## Learn in this order

::::{grid} 1 1 3 3
:gutter: 3

:::{grid-item-card} 1. Installation
:link: installation
:link-type: doc

Set up a dedicated Anaconda GPU environment, choose the right checkpoint,
or install the CPU application. Learn how to update without uninstalling.
:::

:::{grid-item-card} 2. Image workflows
:link: features/index
:link-type: doc

Explore annotation, segmentation, cleaning, denoising, retained crops,
calibration, statistics, and export, with a practical example for each.
:::

:::{grid-item-card} 3. Documentation
:link: documentation/index
:link-type: doc

Find the purpose of every core menu, toolbar control, mode, and workspace
panel. Keep the full manuals and parameter reference close at hand.
:::
::::

```{image} _static/studio-demo.png
:alt: SAM Image Studio with the synthetic particle demo, manually supplied reference masks and Objects, Groups and Image files panels
:class: studio-screen
:width: 100%
```

*Synthetic demo with manually supplied reference masks; this illustrates the
workspace and is not a SAM3.1 inference result.*

## Illustrated workflow guides

Follow the interface from the workspace and menus to the relevant controls.

- [Data cleaning](features/cleaning.md): choose a target, compare fill methods,
  preview, apply and restore original pixels.
- [Three prompted Seg scopes](segmentation/scopes.md): ROI only, whole-image
  examples and a single native object; automatic grid is explained separately.
- [Compressed sensing](features/compressed-sensing.md): dialog order, DCT/TV
  parameter suggestions and computed synthetic comparisons.
- [SAM3 ONNX](segmentation/sam3-onnx.md): public text weights without HF login,
  aliases and exact application ROI clipping.

## A practical guide to SAM3.1

Start with **`black dots`**, run a preview, and accept only the masks you want.
Add positive and negative shape examples to describe a visual concept, use a
region to constrain the output, and give useful prompts memorable aliases.
The guides explain what the application adds and what the underlying model
actually receives.

::::{grid} 1 1 2 2
:gutter: 3

:::{grid-item-card} Text, shapes, and live previews
:link: segmentation/sam31
:link-type: doc

Step-by-step SAM3.1 recipes, combined prompts, point behavior, checkpoint
selection, acceptance, and troubleshooting.
:::

:::{grid-item-card} Detection, segmentation, and model families
:link: segmentation/model-families
:link-type: doc

Understand native SAM1/2 masks, Grounding DINO → SAM2 text detection,
SAM3/3.1 concept segmentation, and whole-image exemplar retrieval.
:::
::::

## What the application adds

SAM Image Studio wraps the models in a microscopy workflow: exact ROI output
limits, inverse-region selection, project-level text aliases, multiple positive
and negative examples, review-before-accept, protected annotations, native
autosave, calibrated measurements, and reversible processing. Read the
[application additions guide](segmentation/application-tools.md) to understand
their scope and limitations.

Version **1.4.3**, based on the v1.4 application line. The optional SAM3/3.1
backend requires NVIDIA CUDA, a dedicated Linux/WSL2 Conda environment, and
approved compatible weights. CPU supports SAM1, SAM2/2.1 and public SAM3 ONNX text segmentation. This website
documents implementation and recorded checks; it does not claim new CUDA
benchmarks or microscopy detection accuracy.

```{toctree}
:maxdepth: 2
:hidden:

Installation <installation>
features/index
Documentation <documentation/index>
developer/index
```
