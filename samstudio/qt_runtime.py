"""Select the working WSLg X11 platform while respecting explicit overrides."""
from __future__ import annotations

import os
import platform


def configure_qt_platform():
    wsl = bool(os.environ.get("WSL_DISTRO_NAME")) or "microsoft" in platform.release().lower()
    if wsl and os.environ.get("DISPLAY"):
        os.environ.setdefault("QT_QPA_PLATFORM", "xcb")
