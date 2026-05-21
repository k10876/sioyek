#!/usr/bin/env python3
import shutil
from pathlib import Path

from PIL import Image


MAX_COEXIST_VARIANTS = 12
BASE_ICON_DIR = "android/res"
OVERLAY_DIR = "android/coexist_icon_overlays"
OUTPUT_DIR = "android/coexist_icons"
BADGE_SCALE = 0.75


def copy_base_icons(base_icon_dir: Path, output_root: Path):
    base_output = output_root / "base"
    if base_output.exists():
        shutil.rmtree(base_output)
    base_output.mkdir(parents=True, exist_ok=True)

    for icon_path in sorted(base_icon_dir.glob("drawable-*/icon.png")):
        destination_dir = base_output / icon_path.parent.name
        destination_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(icon_path, destination_dir / "icon.png")


def render_variant_icons(base_icon_dir: Path, overlay_dir: Path, output_root: Path, number: int):
    overlay_path = overlay_dir / f"{number:02d}.png"
    if not overlay_path.is_file():
        raise FileNotFoundError(f"Overlay image not found: {overlay_path}")

    variant_output = output_root / f"{number:02d}"
    if variant_output.exists():
        shutil.rmtree(variant_output)
    variant_output.mkdir(parents=True, exist_ok=True)

    with Image.open(overlay_path).convert("RGBA") as overlay_source:
        for icon_path in sorted(base_icon_dir.glob("drawable-*/icon.png")):
            destination_dir = variant_output / icon_path.parent.name
            destination_dir.mkdir(parents=True, exist_ok=True)

            with Image.open(icon_path).convert("RGBA") as base_icon:
                icon_width, icon_height = base_icon.size
                overlay_size = max(1, round(icon_width * BADGE_SCALE))
                overlay = overlay_source.resize((overlay_size, overlay_size), Image.Resampling.LANCZOS)
                x = icon_width - overlay_size
                y = icon_height - overlay_size
                composited = base_icon.copy()
                composited.alpha_composite(overlay, dest=(x, y))
                composited.save(destination_dir / "icon.png")


def main():
    repo_root = Path(__file__).resolve().parents[1]
    base_icon_dir = (repo_root / BASE_ICON_DIR).resolve()
    overlay_dir = (repo_root / OVERLAY_DIR).resolve()
    output_root = (repo_root / OUTPUT_DIR).resolve()

    if not base_icon_dir.is_dir():
        raise FileNotFoundError(f"Base icon dir not found: {base_icon_dir}")
    if not overlay_dir.is_dir():
        raise FileNotFoundError(f"Overlay dir not found: {overlay_dir}")

    output_root.mkdir(parents=True, exist_ok=True)

    copy_base_icons(base_icon_dir, output_root)
    for number in range(1, MAX_COEXIST_VARIANTS + 1):
        render_variant_icons(base_icon_dir, overlay_dir, output_root, number)

    print(f"Regenerated icon sets in {output_root}")


if __name__ == "__main__":
    main()
