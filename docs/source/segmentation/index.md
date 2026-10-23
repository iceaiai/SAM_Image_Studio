# Segment objects with SAM

First decide **what describes the target** and **where masks may appear**.
Text/shape/point prompts describe the target. Scope and exact regions control
the output. A disposable preview becomes an annotation only after **Accept masks**.

| Goal | Start here |
| --- | --- |
| Learn SAM1/2/3 detection and segmentation differences | [Model families](model-families.md) |
| Find dark particles using `black dots` | [SAM3.1 text prompt recipe](sam31.md#text-prompt-recipe-black-dots) |
| Find similar particles from positive/negative shapes | [SAM3.1 shape prompt recipe](sam31.md#shape-prompt-recipe) |
| Restrict results to an ROI or an inverse region | [Scope and application tools](application-tools.md) |
| Give effective phrases memorable aliases | [Project aliases](application-tools.md#text-prompt-aliases) |
| Interpret the workflow controls | [Modes](../documentation/modes.md) and [toolbar](../documentation/controls.md) |

```{toctree}
:maxdepth: 2

model-families
sam31
application-tools
```
