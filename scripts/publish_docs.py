"""Publish an already built Sphinx site to gh-pages without rewriting its history.

Run from a checkout with authenticated Git access. This only copies generated
HTML to a temporary clone; it does not change the application checkout.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def git(*args, cwd=ROOT, capture=False):
    return subprocess.run(["git", *map(str, args)], cwd=cwd, check=True,
                          text=True, capture_output=capture).stdout


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build-dir", type=Path, default=ROOT / "docs/_build/html")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    built = args.build_dir.resolve()
    if not (built / "index.html").is_file() or not (built / "_static").is_dir():
        parser.error("Build the Sphinx HTML site successfully before publishing.")
    # Guard the few paths copied into the temporary checkout's root.
    if (built / ".git").exists() or any(p.is_symlink() for p in built.rglob("*")):
        parser.error("The generated site must not contain Git metadata or symbolic links.")
    origin = git("remote", "get-url", "origin", capture=True).strip()
    source_sha = git("rev-parse", "HEAD", capture=True).strip()
    name = git("config", "user.name", capture=True).strip()
    email = git("config", "user.email", capture=True).strip()
    probe = subprocess.run(["git", "ls-remote", "--exit-code", origin,
                            "refs/heads/gh-pages"], capture_output=True, text=True)
    if probe.returncode not in (0, 2):
        raise RuntimeError("Could not inspect the Pages branch using existing Git authentication.")
    with tempfile.TemporaryDirectory(prefix="samstudio-pages-") as directory:
        checkout = Path(directory)
        if probe.returncode == 0:
            git("clone", "--depth", "1", "--branch", "gh-pages", "--single-branch", origin, checkout)
            # This is a fresh temporary clone, never the user's checkout.
            for path in checkout.iterdir():
                if path.name in (".git", "CNAME"):
                    continue
                if path.is_dir():
                    shutil.rmtree(path)
                else:
                    path.unlink()
        else:
            git("init", "--initial-branch=gh-pages", checkout)
            git("remote", "add", "origin", origin, cwd=checkout)
        shutil.copytree(built, checkout, dirs_exist_ok=True,
                        ignore=shutil.ignore_patterns(".doctrees", ".buildinfo"))
        (checkout / ".nojekyll").touch()
        git("config", "user.name", name, cwd=checkout)
        git("config", "user.email", email, cwd=checkout)
        git("add", "--all", cwd=checkout)
        unchanged = subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=checkout)
        if unchanged.returncode == 0:
            print("Pages content is already current.")
            return 0
        if unchanged.returncode != 1:
            raise RuntimeError("Could not inspect the generated Pages changes.")
        if args.dry_run:
            print(f"Prepared {len(list(built.rglob('*')))} generated entries from {source_sha}; dry run, no push.")
            return 0
        git("commit", "-m", f"Publish Sphinx website from {source_sha[:12]}", cwd=checkout, capture=True)
        git("push", "origin", "HEAD:refs/heads/gh-pages", cwd=checkout)
        print("Published the generated files to gh-pages. Verify the GitHub Pages deployment separately.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
