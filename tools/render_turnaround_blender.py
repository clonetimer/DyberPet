#!/usr/bin/env python3
"""Offline 3-view Blender renderer for an authorized, self-contained GLB.

All three views come from the same geometry, camera scale and render session.
It neither approves likeness nor licenses artwork, and does NOT create motion.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import shutil
import subprocess
import tempfile
from pathlib import Path

from PIL import Image

try:
    from .turnaround_gate import VIEWS
except ImportError:
    from turnaround_gate import VIEWS

SCENE_SCRIPT = Path(__file__).with_name("blender_turnaround_scene.py")


class TurnaroundRenderError(ValueError):
    pass


def check_source(source: Path):
    source = Path(source).expanduser()
    if source.is_symlink() or not source.is_file():
        raise TurnaroundRenderError("Use a regular, authorized local GLB file")
    source = source.resolve()
    if source.suffix.lower() != ".glb":
        raise TurnaroundRenderError(
            "Source must be self-contained GLB; first export FBX/VRM/PMX to GLB "
            "locally with the creator's permission")
    if not 20 <= source.stat().st_size <= 250 * 1024 * 1024:
        raise TurnaroundRenderError("GLB file must be 20 bytes to 250 MiB")
    with source.open("rb") as handle:
        header = handle.read(12)
    if (len(header) != 12 or header[:4] != b"glTF" or
            int.from_bytes(header[4:8], "little") != 2 or
            int.from_bytes(header[8:12], "little") != source.stat().st_size):
        raise TurnaroundRenderError("Invalid GLB version or declared length")
    return source


def check_three_views(out: Path):
    hashes = {}
    for name in VIEWS:
        image = out / (name + ".png")
        if image.is_symlink() or not image.is_file():
            raise TurnaroundRenderError("Missing orthographic view: " + name)
        if not 0 < image.stat().st_size < 20 * 1024 * 1024:
            raise TurnaroundRenderError("Oversized or empty rendered view")
        try:
            with Image.open(image) as im:
                im.verify()
            with Image.open(image) as im:
                if im.format != "PNG" or im.size != (512, 512):
                    raise TurnaroundRenderError("Expected a 512x512 PNG")
                rgba = im.convert("RGBA")
                alpha = rgba.getchannel("A")
                bounds = alpha.getbbox()
                if bounds is None:
                    raise TurnaroundRenderError("Empty rendered view: " + name)
                if min(bounds[:2]) <= 0 or max(bounds[2:]) >= 512:
                    raise TurnaroundRenderError("Model clipped at image edge: " + name)
                if any(alpha.getpixel(pos) != 0 for pos in ((0, 0), (0, 511), (511, 0), (511, 511))):
                    raise TurnaroundRenderError("Reference background not transparent")
        except OSError as exc:
            raise TurnaroundRenderError("Invalid rendered PNG: " + name) from exc
        hashes[name] = hashlib.sha256(image.read_bytes()).hexdigest()
    if len(set(hashes.values())) != 3:
        raise TurnaroundRenderError("Identical views: check scene/camera orientation")
    return hashes


def render_turnaround(blender: str, output: Path, *,
                      source: Path | None = None, demo=False,
                      front_yaw: float = 0.0, timeout=600):
    if (source is None) == (not demo):
        raise TurnaroundRenderError("Choose exactly one of source GLB and demo")
    if not math.isfinite(front_yaw) or not -180 <= front_yaw <= 180:
        raise TurnaroundRenderError("front yaw must be -180 to 180 degrees")
    if not 10 <= timeout <= 1800:
        raise TurnaroundRenderError("timeout must be 10 to 1800 seconds")
    source = check_source(source) if source is not None else None
    executable = shutil.which(blender) or str(Path(blender).expanduser())
    if not Path(executable).is_file() or not SCENE_SCRIPT.is_file():
        raise TurnaroundRenderError("Blender executable or scene script missing")
    output = Path(output).expanduser().absolute()
    if output.exists() or output.is_symlink():
        raise FileExistsError("Output already exists; no overwrite: " + str(output))
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".turnaround-", dir=output.parent) as temporary:
        stage = Path(temporary) / "views"
        stage.mkdir()
        command = [executable, "--background", "--factory-startup",
                   "--disable-autoexec", "--python-exit-code", "23",
                   "--threads", "2", "--python", str(SCENE_SCRIPT.resolve()), "--"]
        command += ["--demo"] if demo else ["--input", str(source)]
        command += ["--output", str(stage), "--front-yaw", str(front_yaw)]
        try:
            process = subprocess.run(command, stdout=subprocess.PIPE,
                                     stderr=subprocess.STDOUT, text=True,
                                     timeout=timeout, check=False)
        except subprocess.TimeoutExpired as exc:
            raise TurnaroundRenderError("Blender timed out without output") from exc
        if process.returncode:
            raise TurnaroundRenderError(
                "Blender returned failure: " + (process.stdout or "")[-1800:])
        report_path = stage / "TURNAROUND_BLENDER_REPORT.json"
        if not report_path.is_file():
            raise TurnaroundRenderError("Missing source-aligned render report")
        report = json.loads(report_path.read_text(encoding="utf-8"))
        if (report.get("demo") != demo or report.get("projection") != "orthographic"
                or set(report.get("views", {})) != set(VIEWS)
                or report.get("front_yaw_degrees") != front_yaw):
            raise TurnaroundRenderError("Renderer report mismatch")
        hashes = check_three_views(stage)
        report.update({
            "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest() if source else None,
            "view_sha256": hashes,
            "requires_manual_review": True,
            "rights_verified_automatically": False,
            "published": False,
        })
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2)+"\n",
                               encoding="utf-8")
        if output.exists():
            raise FileExistsError("Output appeared during render")
        stage.rename(output)
    return output


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--demo", action="store_true")
    g.add_argument("--source", type=Path)
    p.add_argument("--blender", default="blender")
    p.add_argument("--front-yaw", type=float, default=0)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--timeout", type=int, default=600)
    args = p.parse_args(argv)
    try:
        output = render_turnaround(args.blender, args.output,
                                   source=args.source, demo=args.demo,
                                   front_yaw=args.front_yaw, timeout=args.timeout)
    except (TurnaroundRenderError, OSError, ValueError, FileExistsError) as exc:
        p.exit(1, "Turnaround blocked: " + str(exc) + "\n")
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
