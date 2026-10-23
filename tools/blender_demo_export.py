"""Export the original geometric test mascot as self-contained GLB.

Runs only under Blender. Produces no third-party game art and does not
attempt to fetch textures, models or motion from the network.
"""
from __future__ import annotations

import sys
from pathlib import Path
import bpy

# Blender supplies the script directory as importable path for --python.
from blender_chibi_scene import demo_model


def main():
    args = sys.argv[sys.argv.index("--")+1:] if "--" in sys.argv else []
    if len(args) != 1:
        raise ValueError("Usage: blender --python blender_demo_export.py -- <output.glb>")
    target = Path(args[0]).expanduser().resolve()
    if target.suffix.lower() != ".glb" or target.exists():
        raise ValueError("Output must be a new .glb file")
    target.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    _, arm = demo_model()
    # Original synthetic hand-wave animation; this creates a real glTF
    # animation clip rather than merely translating the whole character.
    arm.rotation_mode = "XYZ"
    for frame, angle in ((1, 0), (8, .8), (15, 0), (22, .8), (29, 0)):
        arm.rotation_euler[1] = angle
        arm.keyframe_insert(data_path="rotation_euler", index=1, frame=frame)
    arm.animation_data.action.name = "wave"
    bpy.ops.export_scene.gltf(filepath=str(target), export_format="GLB",
                              export_apply=False, export_animations=True)
    if not target.is_file() or target.stat().st_size == 0:
        raise ValueError("GLB export produced no geometry")
    print("Original test GLB exported:", target)


if __name__ == "__main__":
    main()
