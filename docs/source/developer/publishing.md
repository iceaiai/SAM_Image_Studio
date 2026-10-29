# Website build and GitHub Pages

The public project website is **<https://iceaiai.github.io/SAM_Image_Studio/>**.
It is a static Sphinx site, not an online instance of the desktop application.
Only the explicitly supplied public examples and their derived figures are
included; model credentials and interactive GPU sessions are never served.

## Build locally

From the source repository, install `docs/requirements.txt` in the documentation
environment and run:

```sh
.docs-venv/bin/python -m sphinx -W --keep-going -b html docs/source docs/_build/html
```

Sphinx uses MyST Markdown, the PyData Sphinx Theme, Sphinx Design cards, and
static AutoAPI source parsing. No model dependencies/GPU are needed to build.
The theme provides section navigation, search, a page contents panel, and
light/dark appearance. Source pages and source-derived API are rebuilt together.

## Publish

GitHub Pages serves the prebuilt `gh-pages` branch at `/`. The
`.nojekyll` file preserves Sphinx `_static`, `_images`, and `_downloads` paths.
The documentation workflow builds HTML on pushes and pull requests, checks
the build, and on `main` updates the Pages branch. The repository homepage and
README point to the project site.

The workflow explicitly requests a Pages build after updating that branch:
GitHub does not automatically trigger a Pages build from every push made with
the workflow's built-in token. The job needs repository Contents and Pages
write permissions for these two publishing operations.

When GitHub Actions cannot start because of account/billing restrictions, that
is a hosting prerequisite, not a Sphinx build failure. A maintainer can build
the same HTML locally and update the Pages branch with the documented publishing
script. GitHub still must accept/perform the Pages deployment. Do not call a
website live until its published URL returns the expected pages and assets.

After a successful local HTML build, the maintainer command is:

```sh
python scripts/publish_docs.py --dry-run
python scripts/publish_docs.py
```

The script uses a temporary ordinary clone of `gh-pages`, preserves its history
and any existing CNAME, and pushes without force. It does not create a Git
worktree or rewrite the application checkout. Authenticate through the normal
Git platform integration; do not put credentials in documentation files.

The workflow does not use a `CNAME`, custom domain, paid service, or external
analytics. `.readthedocs.yaml` remains an optional alternative hosting recipe.

## Normal and offline source downloads

The download list links to immutable Git tag ZIPs. The normal `v1.4.4` tag has
no `samstudio/resources/offline_profile.json`. The `v1.4.4-offline` tag adds that
marker from `offline/profile.json` and uses the offline guide as its root README.
Its application version and source are otherwise shared with the normal release.
Create the offline commit in a temporary ordinary clone, never by modifying the
normal working checkout. Preserve existing tags; push new tags without force.

Neither source archive includes `.venv*`, `.python312`, `offline-cache` or model
weights. Verify both ZIPs after publishing, including CRCs, entry points, edition
marker presence/absence and comparable initial sizes. The user then prepares
the offline runtime/wheels/checkpoints on a matching connected platform. Do not
label the source ZIP itself as an already prepared dependency bundle.
