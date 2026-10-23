# The four modes

| Mode | What drawing means | Typical next step |
| --- | --- | --- |
| Manual | Create a point or closed-shape annotation in the active group | Select/edit it or export reviewed annotations |
| Segment | Supply point/shape/text prompts or run a grid; generate disposable model masks | Review → Accept masks |
| Clean | Define a pixel removal/fill region or brush target | Preview a fill → Apply, or restore a cleaning record |
| Edit | Change existing geometry, rotate images, scale masks, or assign morphology | Apply a reviewed edit and retain savepoints |

## Switching modes

Pending input is resolved before switching. **Yes** adds eligible pending
shapes/masks, **No** discards them, and **Cancel** stays in the current mode.
An incomplete polygon cannot be added. An active non-prompt-editable task must
finish before the mode changes. A superseded editable prompt request is
canceled and its old preview is cleared.

Entering Segment selects the point tool; reselect an area tool to use
**Single object** or **Inside ROI only**. Entering Clean selects Rectangle;
Manual/Edit start with selection. Mode changes therefore affect both the
meaning of input and the initially active tool.

## One rectangle, three different meanings

- **Manual:** a completed rectangle is an annotation.
- **Segment + whole image:** it is a positive/negative exemplar describing an
  object type; results may appear elsewhere in the image.
- **Segment + Inside ROI only:** it is an allowed output region, with native
  object/text inference selected according to the other prompt controls.
- **Clean:** it defines a pixel-editing target.

The application does not interpret an example box as an ROI merely because it
is rectangular. Choose the scope explicitly. See
[ROI and aliases](../segmentation/application-tools.md).
