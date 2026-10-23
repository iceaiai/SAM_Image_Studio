# Application additions: scope, aliases, and review

These are features added by **SAM Image Studio** around the underlying models.
They are workflow/engineering additions; they are not claims that the SAM
models were retrained or that a new segmentation architecture was invented.

## Four segmentation scopes

| Scope | Intended behavior | Typical use |
| --- | --- | --- |
| Prompt project, whole image | Search for the described concept across the current image using examples and/or text | Find many similar particles from a few examples |
| Single object (native SAM) | Prompt/refine one object using the native mask path when text is empty | Correct an individual particle with an area tool |
| Inside ROI only | Constrain allowed mask pixels to a drawn/selected region | Keep text-segmented particles inside a particular sample area |
| Automatic grid, unannotated only | Place native point prompts on a grid over unprotected areas, ignoring text | Propose candidates without a semantic phrase |

Point has no area and cannot define a useful ROI. **Point** therefore hides and
disables Single object and Inside ROI only in the GUI. Choose an area tool
before selecting them. Nonempty text selects the text path even when a
single-object scope is displayed; clear text for a native one-object trial.

## ROI and inverse-region limits

An area can serve two different purposes: **describe an example object** in
whole-image mode, or **define allowed output pixels** in ROI mode. Choosing
the scope determines how a newly drawn shape is stored/used.

For an ordinary ROI, select an area tool, choose **Inside ROI only**, draw a
region, add text if you want text-driven candidates, and run. Predictions are
clipped to the actual region mask. The model can still see whole-image context;
this is an output constraint, not necessarily cropped inference.

For the complement of selected objects:

1. Select one or several area objects on the canvas or in **Objects**.
2. Use **Invert region**. The shared exact region becomes the complement of
   their mask union.
3. In Segment, enter a text prompt or run an appropriate preview/grid. The
   application clips returned masks to this exact allowed region.
4. In Manual/Edit, **Create object from region** makes an exact annotation;
   in Clean, **Remove selected image area** uses it as a pixel target.

An exact/inverted region is retained as a mask and can constrain even a grid's
final output. Accepted/hidden/locked foreground masks remain protected.
An empty region is rejected visibly. Ordinary ROI mode alone should not be
assumed to constrain Automatic grid; use an exact region for that case.

## Text prompt aliases

Open **Prompt aliases…** or **Models → Text prompt aliases…** and add mappings:

| Alias you type | Effective prompt |
| --- | --- |
| nanoparticle | black dots |
| powder | black dots |
| particles | nanoparticle |

The last row demonstrates chaining: `particles` resolves to `black dots`.
Aliases belong to the current document/project and are retained in native
saves. The text-field tooltip shows the effective prompt.

Rules implemented by this release:

- Matching is case-insensitive and uses complete phrases, not substrings.
- Periods and semicolons separate phrases. Resolved phrases are joined with
  `. ` before they reach the backend.
- Chains are supported; cycles, conflicting case-insensitive duplicates,
  and empty names/targets are rejected.
- Mapping `dot` does not rewrite `dotted line`.
- Accepted-mask provenance stores typed and effective text, allowing review
  of what the model actually received.

An alias changes words sent to the same detector/model. It does not teach a new
class, fine-tune weights, or guarantee a better nanoparticle detector.

## Multiple exemplars and live previews

Positive/negative point and shape examples can accumulate before acceptance.
SAM1/2 use application retrieval; SAM3/3.1 use their native concept interfaces.
**Live prompt preview** schedules updates as input changes. Newer input
invalidates stale results, so an older worker cannot commit the wrong preview.
**Run preview** gives explicit control when live updates are disabled.

## Protected annotations and explicit refinement

New proposals exclude protected foreground masks, including accepted objects
that are hidden or locked. A preview is disposable; **Accept masks** commits
eligible proposals and **Cancel / clear** discards pending work. For replacing
one unlocked accepted object, use **Refine selected object explicitly**.

The app also records model, device, scope/prompt information, and available
confidence scores. Normal Undo/Redo and native autosave coordinate accepted
changes. Review the acquired pixels and retain native projects for recovery.

## Beyond segmentation

Microscopy-specific calibration, Excel lookup, exact COCO mask export,
reversible cleaning, retained real-background crops, mask-scale savepoints,
project recovery, 20-color LUTs, and local plugins extend the model workflow.
They are described individually under [Image workflows](../features/index.md).
