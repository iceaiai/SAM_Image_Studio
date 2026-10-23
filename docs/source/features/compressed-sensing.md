# Compressed sensing: controls and suggested parameters

Compressed sensing here is a **sampled reconstruction experiment** based on the
supplied notebook. It is different from denoising a complete acquired image.
The DCT and iterative-TV methods share the same dialog and sampling controls.
This implementation simulates missing positions from a complete input; it does
not import a detector acquisition sampling pattern.

```{image} ../_static/workflows/compressed-sensing-overview.png
:alt: Synthetic reference, noisy input, ten-percent sampled data and actual DCT and TV reconstruction outputs
:width: 100%
```

*Actual app algorithms, synthetic 192 × 256 data, seed 7, 40 iterations, native
grid. The notebook's optional 256-pixel resolution cap was not applied in this
figure. Output appearance is not a claim about microscopy reconstruction quality.*

## 1. Processing → Denoise… → choose a method

Choose **DCT sparsity** or **TV iterative (notebook)**. Despite the menu name,
their **Task** control selects either ordinary denoising or sampled reconstruction.
The **?** beside each parameter shows its meaning, units, bounds and suggested
starting range in the right-hand panel.

```{image} ../_static/workflows/compressed-sensing-dialog.png
:alt: Actual DCT dialog after the notebook reconstruction preset, showing task, iterations, fidelity, sampling, initialization and sparsity controls
:width: 100%
```

## 2. Task and preset: decide which experiment to run

| Input/question | Task | Start here |
| --- | --- | --- |
| Complete noisy SEM/TEM image | `denoise` | 40 iterations, relaxed fidelity 0.20, native grid (`max_side=0`) |
| What can be reconstructed from simulated missing positions? | `reconstruct` | Random sample 0.10, seed 7, nearest initialization, 40 L2 iterations |
| Reproduce the notebook-sized trial | Notebook reconstruction preset button | Same reconstruction settings with max side 256; DCT 0.08 or TV step 0.08 |

**Restore defaults** resets the current method, including Task. Changing the
method or reopening the dialog also resets parameters. The preset deliberately
switches Task to reconstruct; do not use it as a universal denoising preset.

For full-image denoising, every pixel is observed but fidelity is relaxed.
For reconstruction, fidelity is applied at the sampled positions. With L2
and 100% sampling, hard consistency restores every input value each iteration:
it returns the input and therefore cannot denoise it.

## 3. Shared controls, in dialog order

| Control / internal key | Default | Suggested comparison and interpretation |
| --- | --- | --- |
| Task / `task` | denoise | Choose according to the table above before changing other parameters. |
| Iterations / `iterations` | 40 | Compare 20, 40 and 100 with everything else fixed. More iterations do not guarantee better weak-feature preservation. |
| Data loss / `data_loss` | l2 | Start with L2; compare Huber when large residuals matter. L1 uses a constant-magnitude residual update. |
| Fidelity step / `fidelity_step` | 0.20 | Denoise only. Compare 0.10–0.40. Higher pulls more strongly toward noisy input; lower gives the prior more influence. |
| Huber delta / `huber_delta` | 0.05 | Used by L1 and Huber; compare 0.01–0.10 on normalized intensities. Disabled for L2. |
| Sample fraction / `sample_fraction` | 0.10 | Reconstruct only. Fraction of observed positions, not a denoising strength. Compare 0.05, 0.10, 0.20 using controlled masks/seeds. |
| Sampling method / `sampling_method` | random | Random positions without replacement, or regular grid. Grid counts are approximate; RGB uses one shared sampling mask. |
| Random seed / `random_seed` | 7 | Keep fixed within a parameter comparison; use multiple independent seeds to assess robustness. |
| Initialization / `initialization` | nearest | Compare nearest and zeros only after fixing the sampling mask. Denoise always starts from the full observed input. |
| Max side / `max_side` | 0 | 0 uses native resolution. 256 reproduces notebook-sized processing, then interpolates back; it can lose fine detail. |

Integer input intensities are normalized using their dtype range, not a display
brightness stretch. Floating-point images already in [0,1] keep that scale;
other float ranges are normalized by their data range. Parameter strengths
therefore need not match visually similar screenshots from differently scaled data.

## 4. Method-specific controls

### DCT sparsity: retain a fraction of coefficients

**Sparsity fraction** defaults to **0.08**. Compare **0.04–0.20** first.
A smaller value retains fewer full-image 2D DCT coefficients; it can suppress
noise, but may remove small/faint objects and introduce ringing near edges.
Larger values retain more detail and more noise. Threshold ties can retain
slightly more coefficients than the requested fraction. This is global
per-channel DCT, not block JPEG compression or a learned dictionary.

### TV iterative (notebook): choose an iteration step

**TV step** defaults to **0.01 for denoise**; compare **0.005–0.02**.
The notebook reconstruction preset uses **0.08**. Larger steps can oscillate
or distort edges. This is a gradient/divergence update step, **not** the
regularization weight in the separate **TV restoration** (Chambolle) method.

**Gradient epsilon** defaults to **0.000001**, added inside
`sqrt(gx² + gy² + epsilon)`. Keep it fixed for a first comparison; it stabilizes
the gradient magnitude near flat regions rather than setting the sample fraction.

```{image} ../_static/workflows/compressed-sensing-parameters.png
:alt: Fixed-noise synthetic comparison of DCT retained fractions four, eight and twenty percent, and TV steps 0.005, 0.01 and 0.02
:width: 100%
```

*Computed denoising examples with all pixels observed, 40 iterations, fidelity
0.20 and a fixed display scale. Compare the same weak boundaries and background;
no setting is declared optimal from this synthetic illustration.*

## 5. Target, source, Preview and Apply

After choosing parameters:

1. Select **Process selected region / object masks only** if a region or selected
   masks should receive the change; otherwise the target is the whole image.
2. Select **Use original uncleaned pixels (current orientation)** when you want
   the acquired source instead of current derived pixels.
3. Click **Preview**, compare original and result, then **Apply** or **Cancel**.
4. Inspect small-object edges, weak contrast, texture and artificial ringing.
   Keep the seed, input state, normalization and full parameter set with results.

Apply changes only the target; algorithms can use surrounding/full-image context.
Protected retained crops and pending removed regions are excluded. Cancel leaves
image pixels unchanged. Native projects retain processing records for recovery.

## 6. How to judge a parameter choice

Use a representative crop and change one parameter at a time. With synthetic
reference data you can measure error against the known reference. With a real
image, a smoother result alone does not prove that specimen information was
preserved. Review independent annotations, edge profiles and downstream
measurements. Prefer native resolution for scientific comparisons.

For all allowable bounds and other methods, see the
[complete parameter reference](../denoising.md). The
[notebook page](../notebook.md) explains the unchanged original upload and its
external teaching-image dependencies. Figures can be reproduced with
`python docs/tools/generate_workflow_figures.py` from the repository root.
