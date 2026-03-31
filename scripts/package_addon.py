from __future__ import annotations

import pathlib
import shutil
import zipfile


ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "bonsai_ai"
BLENDER_ADDON = ROOT / "bonsai_ai_blender"
CORE = ROOT / "bonsai_ai_core"
DIST = ROOT / "dist"
LEGACY_ZIP_PATH = DIST / "bonsai_ai_addon.zip"
BLENDER_ZIP_PATH = DIST / "bonsai_ai_blender.zip"
STAGING = DIST / "staging"


def _zip_tree(root: pathlib.Path, archive: zipfile.ZipFile, relative_to: pathlib.Path) -> None:
    for path in root.rglob("*"):
        if path.is_file():
            archive.write(path, path.relative_to(relative_to))


def _package_legacy_addon() -> None:
    with zipfile.ZipFile(LEGACY_ZIP_PATH, "w", zipfile.ZIP_DEFLATED) as archive:
        _zip_tree(SRC, archive, ROOT / "src")


def _package_blender_addon() -> None:
    if STAGING.exists():
        shutil.rmtree(STAGING)
    addon_stage = STAGING / "bonsai_ai_blender"
    vendor_stage = addon_stage / "vendor" / "bonsai_ai_core"
    direct_stage = addon_stage / "vendor" / "bonsai_ai"
    shutil.copytree(BLENDER_ADDON, addon_stage)
    shutil.copytree(CORE, vendor_stage)
    shutil.copytree(SRC, direct_stage)

    with zipfile.ZipFile(BLENDER_ZIP_PATH, "w", zipfile.ZIP_DEFLATED) as archive:
        _zip_tree(STAGING, archive, STAGING)


def main() -> None:
    DIST.mkdir(exist_ok=True)
    _package_legacy_addon()
    _package_blender_addon()
    print(LEGACY_ZIP_PATH)
    print(BLENDER_ZIP_PATH)


if __name__ == "__main__":
    main()
