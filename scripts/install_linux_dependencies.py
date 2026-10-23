"""Install only missing Qt system libraries on Debian/Ubuntu, including WSL.

Called by both supported installers. Does not install Python packages or drivers.
"""
from __future__ import annotations

import argparse
import ctypes
import ctypes.util
import json
import os
import shutil
import subprocess
import sys

LIBRARIES = {
    "GL": "libgl1", "EGL": "libegl1", "OpenGL": "libopengl0",
    "fontconfig": "libfontconfig1", "freetype": "libfreetype6",
    "xkbcommon": "libxkbcommon0", "xkbcommon-x11": "libxkbcommon-x11-0",
    "xcb-cursor": "libxcb-cursor0", "xcb-icccm": "libxcb-icccm4",
    "xcb-image": "libxcb-image0", "xcb-keysyms": "libxcb-keysyms1",
    "xcb-render-util": "libxcb-render-util0", "xcb-xinerama": "libxcb-xinerama0",
    "xcb-xkb": "libxcb-xkb1", "xcb-shape": "libxcb-shape0",
    "xcb-randr": "libxcb-randr0", "dbus-1": "libdbus-1-3",
    "SM": "libsm6", "ICE": "libice6",
}


def missing_packages():
    missing = []
    for library, package in LIBRARIES.items():
        name = ctypes.util.find_library(library)
        try:
            if not name:
                raise OSError(library)
            ctypes.CDLL(name)
        except OSError:
            missing.append(package)
    return sorted(set(missing))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    if not sys.platform.startswith("linux"):
        print("Qt system-library installation is not needed on this platform.")
        return 0
    packages = missing_packages()
    if not packages:
        print("Qt system libraries are available.")
        return 0
    if not shutil.which("apt-get"):
        parser.error("Missing Qt libraries. Install equivalent system packages with your distribution's package manager: " + ", ".join(packages))
    prefix = [] if os.geteuid() == 0 else ["sudo"]
    if prefix and not shutil.which("sudo"):
        parser.error("An administrator must install these Ubuntu system packages: " + " ".join(packages))
    commands = [prefix + ["apt-get", "update"], prefix + ["apt-get", "install", "--yes", *packages, "fonts-dejavu-core"]]
    if args.dry_run:
        print(json.dumps({"missing_packages": packages, "commands": commands}, indent=2))
        return 0
    print("Installing missing Ubuntu Qt libraries; sudo may ask for your Linux password. This does not change Conda base.", flush=True)
    for command in commands:
        subprocess.run(command, check=True)
    remaining = missing_packages()
    if remaining:
        parser.error("Qt libraries still cannot load after installation: " + ", ".join(remaining))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
