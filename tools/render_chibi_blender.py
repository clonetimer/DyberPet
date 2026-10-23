#!/usr/bin/env python3
"""Launch a local Blender headless chibi renderer with no asset fetching.

Demo mode uses original geometric primitives only. For user art only GLB/GLTF
and FBX are directly imported; PMX/VRM need authorized Blender add-ons/export.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

ACTIONS = ("idle", "left_walk", "right_walk", "wave", "jump", "wait", "sleep", "review")
FORMATS = {".glb", ".gltf", ".fbx"}
SCRIPT = Path(__file__).with_name("blender_chibi_scene.py")


class RenderError(ValueError):
    pass


def validate_frames(directory: Path, expected: tuple[str, ...], num: int):
    try:
        from PIL import Image
    except ImportError as exc:
        raise RenderError("Pillow is required for render QA") from exc
    observations = {}
    for name in expected:
        sequence = [directory / f"{name}_{i}.png" for i in range(num)]
        missing = [p.name for p in sequence if not p.is_file()]
        if missing:
            raise RenderError(f"Missing rendered action {name}: {missing}")
        transparent, visible, cropped = 0, 0, 0
        for frame in sequence:
            with Image.open(frame) as source:
                if source.size != (192, 208):
                    raise RenderError("Renderer output is not 192x208: " + frame.name)
                rgba = source.convert("RGBA")
                bounds = rgba.getchannel("A").getbbox()
                if bounds is None:
                    raise RenderError("Fully transparent animation frame: " + frame.name)
                if bounds[0] <= 0 or bounds[1] <= 0 or bounds[2] >= 192 or bounds[3] >= 208:
                    cropped += 1
                corners = [rgba.getpixel(pt)[3] for pt in
                           ((0, 0), (191, 0), (0, 207), (191, 207))]
                transparent += int(any(a == 0 for a in corners))
                visible += 1
        if not transparent:
            raise RenderError("Frames are opaque at every corner: " + name)
        observations[name] = {"frames": visible,
                              "has_transparency": bool(transparent),
                              "edge_touch_count": cropped}
    return observations


def render_blender(blender: str, output: Path, *, source: Path | None = None,
                   demo: bool = False, actions: tuple[str, ...] = ("idle", "wave"),
                   frames: int = 2, timeout: int = 600) -> Path:
    if demo == (source is not None):
        raise RenderError("Choose exactly one of demo=True or source=...")
    if not 1 <= frames <= 24:
        raise RenderError("frames must be 1–24")
    if (not actions or len(set(actions)) != len(actions) or
            "idle" not in actions or any(a not in ACTIONS for a in actions)):
        raise RenderError("Invalid actions; idle is required")
    if not demo:
        source = Path(source).expanduser().resolve()
        if not source.is_file():
            raise RenderError("Model file not found")
        if source.suffix.lower() not in FORMATS:
            raise RenderError(
                "Only GLB/GLTF/FBX supported. PMX/VRM/BLEND must be "
                "converted to GLB with authorized plugins and model permissions."
            )
    output = Path(output).expanduser().resolve()
    if output.exists():
        raise FileExistsError("Output directory already exists; never overwrite: " + str(output))
    if not 10 <= timeout <= 1800:
        raise RenderError("timeout must be 10–1800 seconds")
    if not SCRIPT.is_file():
        raise RenderError("Blender scene script missing")
    executable = shutil.which(blender) or str(Path(blender).expanduser())
    if not Path(executable).is_file():
        raise RenderError("Blender executable not found: " + blender)
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=output.parent, prefix=".blender-chibi-") as tmp:
        temp_output = Path(tmp) / "render"
        temp_output.mkdir()
        command = [
            executable, "--background", "--factory-startup", "--disable-autoexec",
            "--python-exit-code", "23", "--threads", "2",
            "--python", str(SCRIPT.resolve()), "--",
        ]
        command += ["--demo"] if demo else ["--input", str(source)]
        command += ["--output", str(temp_output), "--frames", str(frames),
                    "--actions", ",".join(actions)]
        try:
            process = subprocess.run(
                command, text=True, stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT, timeout=timeout, check=False)
        except subprocess.TimeoutExpired as exc:
            raise RenderError("Blender render timed out; no output installed") from exc
        except OSError as exc:
            raise RenderError("Could not launch Blender: " + str(exc)) from exc
        if process.returncode != 0:
            raise RenderError("Blender failed: " + (process.stdout or "")[-3000:])
        report_path = temp_output / "BLENDER_RENDER_REPORT.json"
        if not report_path.is_file():
            raise RenderError("Blender did not write render report")
        report = json.loads(report_path.read_text(encoding="utf-8"))
        if report.get("demo") != demo or set(report.get("actions", {})) != set(actions):
            raise RenderError("Blender report does not match requested source/actions")
        qa = validate_frames(temp_output, actions, frames)
        report["frame_qa"] = qa
        report["launcher"] = {"disable_autoexec": True, "rendered_locally": True,
                              "automated_rights_verification": False}
        report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False)+"\n",
                               encoding="utf-8")
        if output.exists():
            raise FileExistsError("Output appeared during render; refusing overwrite")
        temp_output.rename(output)
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    g = parser.add_mutually_exclusive_group(required=True)
    g.add_argument("--demo", action="store_true",
                   help="Original geometric fixture for pipeline smoke tests")
    g.add_argument("--source", type=Path, help="Authorized local GLB/GLTF/FBX")
    parser.add_argument("--blender", default="blender")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--frames", type=int, default=6)
    parser.add_argument("--actions", default="idle,left_walk,right_walk,wave,jump,wait,review")
    parser.add_argument("--timeout", type=int, default=600)
    args = parser.parse_args()
    actions = tuple(a.strip() for a in args.actions.split(","))
    try:
        result = render_blender(args.blender, args.output, source=args.source,
                                demo=args.demo, actions=actions, frames=args.frames,
                                timeout=args.timeout)
    except (RenderError, OSError, ValueError, json.JSONDecodeError) as exc:
        parser.exit(1, "Render blocked: " + str(exc) + "\n")
    print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
