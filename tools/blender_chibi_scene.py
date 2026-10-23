"""Blender-side transparent animation renderer (run with blender --background --python).

A demo geometric mascot is created procedurally for regression tests.
For real inputs this is root-motion-only, NOT a humanoid retargeting system.
Input is limited to GLB/GLTF/FBX; export PMX/VRM/Blend using an authorized
Blender/MMD plugin and the owner's rules before invoking this script.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector

SUPPORTED = {"idle", "left_walk", "right_walk", "wave", "jump", "wait", "sleep", "review"}
SUFFIXES = {".glb", ".gltf", ".fbx"}


def args_from_blender():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    p = argparse.ArgumentParser(description=__doc__)
    group = p.add_mutually_exclusive_group(required=True)
    group.add_argument("--demo", action="store_true")
    group.add_argument("--input", type=Path)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--frames", type=int, default=6)
    p.add_argument("--actions", type=str, default="idle,left_walk,right_walk,wave,jump,wait,review")
    args = p.parse_args(argv)
    if not 1 <= args.frames <= 24:
        p.error("frames must be between 1 and 24 per action")
    acts = [v.strip() for v in args.actions.split(",")]
    if not acts or len(acts) != len(set(acts)) or any(a not in SUPPORTED for a in acts):
        p.error("Invalid or duplicated actions")
    if "idle" not in acts:
        p.error("idle is mandatory for DyberPet")
    args.actions = acts
    return args


def material(label, color):
    mat = bpy.data.materials.new(label)
    mat.diffuse_color = (*color, 1)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    principled = nodes.get("Principled BSDF")
    if principled is not None:
        principled.inputs["Base Color"].default_value = (*color, 1)
        principled.inputs["Roughness"].default_value = 0.72
    return mat


def ellipsoid(label, xyz, scale, mat, collection):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=12, ring_count=8, location=xyz)
    ob = bpy.context.object
    ob.name = label
    ob.scale = scale
    ob.data.materials.append(mat)
    collection.append(ob)
    return ob


def demo_model():
    """An original Q-shaped geometry fixture, not a game character."""
    skin = material("Demo_Lilac", (0.50, 0.38, 0.77))
    hair = material("Demo_Coral", (0.93, 0.53, 0.63))
    eye = material("Demo_Eyes", (0.07, 0.11, 0.23))
    pale = material("Demo_Cream", (0.95, 0.90, 0.82))
    objects = []
    ellipsoid("DemoBody", (0, 0, 1.00), (.43, .30, .53), skin, objects)
    ellipsoid("DemoHead", (0, 0, 1.84), (.70, .53, .67), hair, objects)
    ellipsoid("DemoFace", (0, -.43, 1.72), (.52, .13, .43), pale, objects)
    for x in (-.22, .22):
        ellipsoid("DemoEye", (x, -.55, 1.78), (.085, .045, .12), eye, objects)
        ellipsoid("DemoFoot", (x, -.02, .32), (.20, .28, .21), skin, objects)
    ellipsoid("DemoArmLeft", (-.47, -.01, 1.08), (.16, .23, .32), pale, objects)
    arm = ellipsoid("DemoArmRight", (.47, -.01, 1.08), (.16, .23, .32), pale, objects)
    return objects, arm


def import_model(filepath):
    filepath = filepath.resolve()
    if not filepath.is_file():
        raise ValueError("3D input not found")
    if filepath.suffix.lower() not in SUFFIXES:
        raise ValueError("Use GLB/GLTF/FBX; PMX/VRM/BLEND requires authorized local export to GLB")
    if filepath.suffix.lower() in {".glb", ".gltf"}:
        bpy.ops.import_scene.gltf(filepath=str(filepath))
    else:
        bpy.ops.import_scene.fbx(filepath=str(filepath))
    models = [ob for ob in bpy.context.scene.objects if ob.type in {"MESH", "ARMATURE"}]
    if not any(o.type == "MESH" for o in models):
        raise ValueError("Imported model has no mesh")
    return models


def position_objects(objects):
    """Keep armatures and their hierarchy; normalize using existing root objects."""
    meshes = [o for o in objects if o.type == "MESH"]
    bpy.context.view_layer.update()
    positions = [o.matrix_world @ Vector(corner)
                 for o in meshes for corner in o.bound_box]
    lo = [min(p[i] for p in positions) for i in range(3)]
    hi = [max(p[i] for p in positions) for i in range(3)]
    size = max(hi[0]-lo[0], hi[1]-lo[1], hi[2]-lo[2])
    if size <= 1e-5:
        raise ValueError("Model bounds are empty")
    scale = 2.5 / size
    root = bpy.data.objects.new("DyberPet_AnimationRoot", None)
    bpy.context.scene.collection.objects.link(root)
    for ob in objects:
        if ob.parent is None:
            world = ob.matrix_world.copy()
            ob.parent = root
            ob.matrix_world = world
    root.scale = (scale, scale, scale)
    root.location = (-((lo[0]+hi[0])/2)*scale,
                     -((lo[1]+hi[1])/2)*scale, -lo[2]*scale+.12)
    bpy.context.view_layer.update()
    return root


def camera_and_lighting():
    bpy.ops.object.camera_add(location=(0, -8.7, 1.55))
    cam = bpy.context.object
    point = Vector((0, 0, 1.40))
    cam.rotation_euler = (point - cam.location).to_track_quat("-Z", "Y").to_euler()
    cam.data.type = "ORTHO"
    cam.data.ortho_scale = 3.6
    scene = bpy.context.scene
    scene.camera = cam
    bpy.ops.object.light_add(type="AREA", location=(1, -3, 5))
    bpy.context.object.data.energy = 620
    bpy.context.object.data.shape = "DISK"
    bpy.context.object.data.size = 5
    bpy.ops.object.light_add(type="AREA", location=(-3, 0, 3))
    bpy.context.object.data.energy = 380
    scene.render.resolution_x = 192
    scene.render.resolution_y = 208
    scene.render.resolution_percentage = 100
    scene.render.film_transparent = True
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.render.image_settings.color_depth = "8"
    scene.render.image_settings.compression = 15
    if bpy.app.version >= (4, 2, 0):
        scene.render.engine = "BLENDER_EEVEE_NEXT"
    else:
        scene.render.engine = "BLENDER_EEVEE"
    scene.camera.data.lens = 45
    scene.render.film_transparent = True
    return scene


def pose(root, arm, initial_location, action, t):
    phase = 2 * math.pi * t
    x, y, z = initial_location
    dx, dz, rot = 0.0, 0.0, 0.0
    if action == "idle":
        dz = .028 * math.sin(phase)
    elif action in {"left_walk", "right_walk"}:
        direction = -1 if action == "left_walk" else 1
        dx = direction * .09 * t
        dz = .025 * abs(math.sin(phase))
        rot = direction * .10
    elif action == "jump":
        dz = .45 * math.sin(math.pi * t)
    elif action == "wave":
        rot = .03 * math.sin(phase)
    elif action == "wait":
        dz = -.035
    elif action == "sleep":
        dz = -.12
        rot = -.13
    elif action == "review":
        rot = .07 * math.sin(phase)
    root.location = (x+dx, y, z+dz)
    root.rotation_euler[1] = rot
    if arm is not None:
        arm.rotation_euler[1] = .65 * (0.5+0.5*math.sin(phase)) if action == "wave" else 0


def main():
    args = args_from_blender()
    bpy.ops.wm.read_factory_settings(use_empty=True)
    if args.demo:
        objs, arm = demo_model()
        source_label = "synthetic original test geometry"
    else:
        objs, arm = import_model(args.input), None
        source_label = args.input.name
    ctrl = position_objects(objs)
    scene = camera_and_lighting()
    args.output.mkdir(parents=True, exist_ok=True)
    original = tuple(ctrl.location)
    for name in args.actions:
        for index in range(args.frames):
            t = index / args.frames
            pose(ctrl, arm, original, name, t)
            scene.frame_set(index + 1)
            scene.render.filepath = str(args.output / f"{name}_{index}.png")
            bpy.ops.render.render(write_still=True)
    report = {
        "renderer": "Blender", "version": bpy.app.version_string,
        "source": source_label, "demo": bool(args.demo),
        "output_format": "192x208 transparent RGBA PNG",
        "actions": {a: args.frames for a in args.actions},
        "animation_quality": (
            "procedural original fixture" if args.demo
            else "root-motion-only; rigged limb/motion animation NOT retargeted"
        ),
        "limitations": [
            "No native PMX or VRM importer; export using permitted Blender addons",
            "No motion retargeting from MMD VMD/VRM animation datasets",
            "Root-motion preview should be artist-reviewed for visual correctness",
        ],
    }
    (args.output / "BLENDER_RENDER_REPORT.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False)+"\n", encoding="utf-8")
    print("DyberPet render completed:", args.output)


if __name__ == "__main__":
    main()
