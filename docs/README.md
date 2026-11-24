# Documentation map

- **Live website:** https://iceaiai.github.io/SAM_Image_Studio/
- `source/`: current Sphinx pages, illustrated workflows and API generation.
- `tools/`: reproducible synthetic scientific figures and website browser checks.
- `requirements.txt`: isolated Sphinx dependencies; no Qt or Torch required to build.
- `RELEASE_NOTES.md`: changes to the current application.
- [User Manual source](../samstudio/resources/user_manual.md): shared by the desktop
  app and Sphinx, including the denoising chapter.
- `FOR_DEVELOPER.md`, PDFs and `screenshots/`: original v1.4.2 developer and
  reference materials.
- `archive/`: original installation and test reports.
- `validation/`: historical release evidence and explicitly scoped current reports.
- `_build/`: locally generated website, ignored by Git.

The current installation guide supersedes old file paths in archived manuals.
CPU helper files now live in `packaging/`; GPU setup is centralized in `GPU/`.
The five separately supplied original artifacts are preserved under `uploads/`.
