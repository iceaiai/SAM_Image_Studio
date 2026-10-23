# SAM Image Studio

SAM Image Studio 1.4.2 is a Python desktop application for microscopy annotation,
Segment Anything (SAM) segmentation, calibrated measurements, reversible image
processing, and local plugins. CPU operation supports SAM1 and SAM2/2.1;
NVIDIA GPU operation uses a dedicated Conda environment. SAM3 and SAM3.1 are
optional GPU backends with separate checkpoint access requirements.

Start with the installation guide and quickstart. The complete user, developer,
and denoising manuals are included below, followed by a reference generated
directly from the application source.

```{toctree}
:maxdepth: 2
:caption: Getting started

installation
quickstart
```

```{toctree}
:maxdepth: 2
:caption: Manuals and development

user-manual
denoising
developer-manual
architecture
development
notebook
```

```{toctree}
:maxdepth: 2
:caption: Reference

api
troubleshooting
downloads
provenance
```

The manuals describe application behavior. The bundled release test reports are
historical evidence, with their own platform and hardware limits; they do not
establish that CUDA inference works on a new machine.
