# Compressed sensing notebook

The original **3PM_Compressed_Sensing.ipynb** is retained unchanged in
`uploads/`. Download it from the [downloads page](downloads.md).

This teaching notebook compares nearest-neighbor, sparse DCT, and iterative TV
reconstruction, L2/L1/Huber data updates, reconstruction scores, and an
uncertainty-guided scalar measurement loop. The app's
`samstudio/compressed_sensing.py` adapts the DCT/TV update concepts for image
processing; the notebook itself is not an application installer or plugin.

## Run the original notebook

The supplied notebook targets **Google Colab** with Python 3.12 metadata:

1. Upload/open `uploads/3PM_Compressed_Sensing.ipynb` in Colab.
2. Run its setup cell, which clones the upstream
   `gduscher/MLSTEM2026` workshop and installs `ipympl`.
3. Restart the Colab session as directed, then run the remaining cells in order.

It reads `smokey.jpeg`, `ayreshall.jpeg`, and `checkerneyland.jpeg` from
`MLSTEM2026/Day 2/compressed_sensing/`. Those image assets are external to this
repository and are not included in the CPU ZIP. The notebook's Colab badge
points to the original workshop, not this repository's preserved copy.

The notebook imports `google.colab` widget support, so an unchanged local
Jupyter run is not portable. For a local adaptation, work on a copy, provide
the workshop image files, install NumPy/SciPy/Pillow/Matplotlib/ipympl/Jupyter,
and replace the Colab-only widget initialization. Local execution is not part
of the Sphinx build or the desktop installation self-test.

## Reconstruction is different from denoising

The notebook simulates missing measurements on a known complete image. The
app's `reconstruct` task follows that sampled-data update, while `denoise`
uses all pixels and a relaxed `fidelity_step`. With full sampling and hard L2
consistency, reconstruction returns the input; that is not evidence of
effective denoising.

`sample_fraction`, `sampling_method`, `random_seed`, and `initialization` are
reconstruction controls. `tv_step` is an iteration step and is different from
the regularization weight used by Chambolle TV restoration. See the
[denoising parameter guide](denoising.md) for defaults and validation limits.

Notebook uncertainty scores are acquisition heuristics rather than calibrated
probabilities. No reconstruction score alone establishes scientific feature
preservation in microscopy data.
