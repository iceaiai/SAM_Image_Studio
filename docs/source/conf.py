"""Sphinx configuration; read source statically without importing Qt or Torch."""
from pathlib import Path
import ast

ROOT = Path(__file__).resolve().parents[2]
project = "SAM Image Studio"
copyright = "2026, SAM Image Studio contributors"
author = "SAM Image Studio contributors"
# Keep the documentation version synchronized without importing the application.
module = ast.parse((ROOT / "samstudio" / "__init__.py").read_text(encoding="utf-8"))
release = next(
    ast.literal_eval(node.value)
    for node in module.body
    if isinstance(node, ast.Assign)
    and any(isinstance(t, ast.Name) and t.id == "__version__" for t in node.targets)
)
version = release
extensions = ["myst_parser", "sphinx_design", "autoapi.extension", "sphinx.ext.napoleon"]
source_suffix = {".rst": "restructuredtext", ".md": "markdown"}
root_doc = "index"
exclude_patterns = []
language = "en"
html_theme = "pydata_sphinx_theme"
html_title = f"{project} {release}"
html_theme_options = {
    "logo": {"text": "SAM Image Studio"},
    "navigation_depth": 3,
    "show_nav_level": 1,
    "navbar_align": "left",
    "navbar_end": ["theme-switcher", "navbar-icon-links"],
    "icon_links": [{"name": "GitHub", "url": "https://github.com/iceaiai/SAM_Image_Studio", "icon": "fa-brands fa-github"}],
    "show_prev_next": True,
    "footer_start": ["copyright"],
    "footer_end": ["sphinx-version", "theme-version"],
}
html_context = {"github_user": "iceaiai", "github_repo": "SAM_Image_Studio", "github_version": "main", "doc_path": "docs/source"}
html_baseurl = "https://iceaiai.github.io/SAM_Image_Studio/"
html_static_path = ["_static"]
html_css_files = ["studio.css"]
html_copy_source = False
html_show_sourcelink = False
myst_enable_extensions = ["colon_fence", "dollarmath"]
myst_heading_anchors = 4

# AutoAPI parses all application modules. It does not download model weights,
# import optional backends, or initialize a GUI during documentation builds.
autoapi_dirs = [str(ROOT / "samstudio")]
autoapi_type = "python"
autoapi_ignore = ["*/__main__.py"]
autoapi_options = ["members", "undoc-members", "show-inheritance", "show-module-summary"]
autoapi_member_order = "bysource"
autoapi_add_toctree_entry = False
autoapi_keep_files = False


def setup(app):
    # The release intentionally re-exports StatisticsDialog through dialogs.
    # AutoAPI cannot resolve that circular alias, but it still documents the
    # actual class in statistics_dialog. Filter only this known alias cycle;
    # all other import-resolution and documentation warnings remain errors.
    import logging

    class KnownDialogAliasCycle(logging.Filter):
        def filter(self, record):
            message = record.getMessage()
            prefix = "Cannot resolve cyclic import: "
            if not message.startswith(prefix):
                return True
            modules = message[len(prefix):].split(", ")
            cycle = modules[modules.index(modules[-1]):-1]
            return set(cycle) != {"samstudio.dialogs", "samstudio.statistics_dialog"}

    logging.getLogger("sphinx.autoapi._mapper").addFilter(KnownDialogAliasCycle())
