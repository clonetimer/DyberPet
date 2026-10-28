"""Blender-side source-aligned, orthographic Q-chibi front/side/back renderer.

Run from render_turnaround_blender.py with --disable-autoexec. This produces
only unapproved reference evidence, never a completed character or animation.
"""
import argparse
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
from blender_chibi_scene import demo_model, import_model, position_objects, camera_and_lighting


def arguments():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--demo", action="store_true")
    group.add_argument("--input", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--front-yaw", type=float, default=0)
    opts = parser.parse_args(argv)
    if not -180 <= opts.front_yaw <= 180 or not math.isfinite(opts.front_yaw):
        parser.error("front yaw must be a finite angle between -180 and +180 degrees")
    return opts


def main():
    args = arguments()
    bpy.ops.wm.read_factory_settings(use_empty=True)
    objects = demo_model()[0] if args.demo else import_model(args.input)
    position_objects(objects)
    scene = camera_and_lighting()
    scene.render.resolution_x = 512
    scene.render.resolution_y = 512
    scene.render.resolution_percentage = 100
    scene.camera.data.type = "ORTHO"
    scene.camera.data.ortho_scale = 3.65
    scene.frame_set(1)
    args.output.mkdir(parents=True, exist_ok=True)
    center = Vector((0.0, 0.0, 1.4))
    views = {"front": 0, "side": 90, "back": 180}
    camera = scene.camera
    for name, delta in views.items():
        a = math.radians(args.front_yaw + delta)
        camera.location = (8.0 * math.sin(a), -8.0 * math.cos(a), 1.4)
        camera.rotation_euler = (center - camera.location).to_track_quat("-Z", "Y").to_euler()
        scene.render.filepath = str(args.output / (name + ".png"))
        bpy.ops.render.render(write_still=True)
    report = {
        "source": "synthetic geometry fixture" if args.demo else args.input.name,
        "demo": bool(args.demo),
        "renderer": "Blender",
        "version": bpy.app.version_string,
        "projection": "orthographic",
        "front_yaw_degrees": args.front_yaw,
        "views": views,
        "view_semantics": {
            "front": "camera at model -Y before optional yaw",
            "side": "camera at model +X before optional yaw (right side)",
            "back": "camera at model +Y before optional yaw",
        },
        "resolution": [512, 512],
        "reviewed": False,
        "caution": "Imported models may have different front axes; manually verify all three views.",
    }
    (args.output / "TURNAROUND_BLENDER_REPORT.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    print("Rendered unapproved three-view reference:", args.output)


if __name__ == "__main__":
    main()
