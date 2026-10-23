# Local plugins and custom processing

Use **Plugin → Install local plugin folder…** to install a folder containing
`plugin.json` and Python code. **Manage / reload plugins…** enables, disables,
reloads, or removes installed plugins. Plugin dependencies must already be
available in the active environment; registration does not install them.

Image processors run through the same selected-target, Preview/Apply, and
Undo workflow. A valid result preserves image dimensions, dtype, finite values,
and alpha/outside-target pixels. GUI actions and background image processors
have different threading responsibilities.

The included `examples/plugins/unet_denoiser/` demonstrates tiled TorchScript
inference with overlap blending. It is an interface example; no trained
denoising weights are bundled. User-trained normalization and model quality
must be checked separately.

Choose **Plugin → For Developer (PDF)** or the
[developer guide](../developer/index.md) for the API, complete U-Net example,
model contract, and executable validation instructions.
