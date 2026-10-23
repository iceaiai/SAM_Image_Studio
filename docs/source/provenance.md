# Sources, versions, and licenses

This documentation is based on the supplied SAM Image Studio **1.4.2** CPU
archive, its application source and editable manuals, the three separately
uploaded PDF manuals, and the compressed-sensing teaching notebook.
The PDFs identify an English edition dated October 22, 2026.

The original uploads are retained unchanged under `uploads/`.
`uploads/SHA256SUMS` records their SHA-256 digests. Source code, installers,
tests, bundled wheels, packaged PDFs, and historical validation files were
extracted from the ZIP. The repository README and Sphinx/CI configuration are
new repository documentation; application algorithms and dependency lockfiles
are unchanged.

`FILE_MANIFEST_SHA256.json` is the **original release archive manifest**. Its
paths refer to files in that archive, including the original README, not to
the newly authored repository README or other documentation additions. Verify
it against the ZIP's `SAM_Image_Studio/` contents. It is not a manifest of the
current Git checkout.

Historical reports in `TEST_REPORT.md` and `validation/` retain their original
scope and claims. A Sphinx build validates documentation generation. It does
not rerun those application tests or prove model accuracy, CUDA compatibility,
or native Windows execution. See the development page for current validation
commands and the missing external-asset manifest limitation.

The application source includes an MIT {download}`license <../../LICENSE>`.
Third-party model/dependency licenses and notices are separate; see
`third_party/NOTICE.md` and the supplied SAM licenses. BM3D/bm4d have upstream
academic/non-commercial terms. Review the applicable terms for each backend
and checkpoint. The app license does not automatically relicense the supplied
notebook, workshop assets, model weights, or third-party packages.
