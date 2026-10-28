"""Existing GenshinImpact main-role-folder migration into the mature pipeline.

Uses entirely synthetic artwork. It does NOT attest artist permissions or
download the old application. Main/pet role distinction is an actual gate.
"""
import json
import os
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from tools.character_pipeline import (
    PipelineError, init_case, attach_case, rights_review, build_case,
    qa_review, package_release, load_case, attach_turnaround, review_turnaround,
)
from tools.install_native_role import (
    inspect_native_folder, install_native_folder,
)
from tools.genshin_batch import status, probe_asset


def legacy_character(folder):
    (folder / "action").mkdir(parents=True)
    (folder / "pet_conf.json").write_text(json.dumps({
        "default": "idle", "drag": "idle", "fall": "idle",
        "left": "walking", "right": "walking",
    }), encoding="utf-8")
    (folder / "act_conf.json").write_text(json.dumps({
        "idle": {"images": "idle", "frame_refresh": 0.12},
        "walking": {"images": "walk", "frame_refresh": 0.1,
                    "direction": "right", "frame_move": 3}
    }), encoding="utf-8")
    for prefix in ("idle", "walk"):
        for index in range(4):
            image = Image.new("RGBA", (80, 100), (60, 120, 190, 255))
            image.save(folder / "action" / f"{prefix}_{index}.png")


class LegacyGenshinRoleMigrationTests(unittest.TestCase):
    def setUp(self):
        holder = tempfile.TemporaryDirectory()
        self.addCleanup(holder.cleanup)
        self.root = Path(holder.name)
        self.role = self.root / "legacy-app" / "res" / "role" / "魈"
        legacy_character(self.role)
        self.workspace = self.root / "review-workspace"
        self.case = init_case(self.workspace, "genshin_xiao_main", "魈",
                              "dyberpet_collection",
                              "https://www.bilibili.com/video/BV1gv4y1a7Q7",
                              "native_zip", "genshin_xiao", "栎咕咕")
        self.evidence = self.root / "actual-artwork-terms.txt"
        self.evidence.write_text("synthetic test permission only", encoding="utf-8")

    def approve_synthetic_qviews(self):
        viewdir = self.root / "qchibi-three-view-test"
        viewdir.mkdir(exist_ok=True)
        for i, key in enumerate(("front", "side", "back")):
            Image.new("RGB", (120, 160), (30 + i * 60, 80, 110)).save(
                viewdir / (key + ".png"))
        attach_turnaround(
            self.case, front=viewdir / "front.png",
            side=viewdir / "side.png", back=viewdir / "back.png",
            reference_url="https://artist.example/synthetic-three-view",
            artist="Synthetic fixture artist", variant="Xiao test costume")
        review_turnaround(
            self.case, "Fixture reviewer", {
                "silhouette": True, "outfit": True,
                "identity": True, "cross_view": True})

    def test_single_original_folder_is_read_only_identified(self):
        report = inspect_native_folder(self.role)
        self.assertEqual(report["validation"]["actions"], 2)
        self.assertEqual(report["validation"]["images"], 8)
        self.assertEqual(len(report["files"]), 10)
        self.assertGreater(report["total_bytes"], 0)

    def test_attachment_auto_switches_zip_to_extracted_folder_and_resets_rights(self):
        data = attach_case(self.case, self.role)
        self.assertEqual(data["source"]["kind"], "native_folder")
        self.assertEqual(data["source"]["artist"], "栎咕咕")
        self.assertFalse(data["rights"]["redistribution"])
        with self.assertRaisesRegex(PipelineError, "rights review"):
            build_case(self.case)

    def test_full_local_build_requires_human_review_not_redistribution(self):
        attach_case(self.case, self.role)
        rights_review(self.case, "CI synthetic user", str(self.evidence),
                      local_use=True)
        self.approve_synthetic_qviews()
        built = build_case(self.case)
        self.assertTrue((built / "action" / "walk_3.png").exists())
        self.assertTrue((built / "PIPELINE_SOURCE.json").exists())
        receipt = json.loads((built / "INSTALL_REPORT.json").read_text("utf-8"))
        self.assertEqual(receipt["source_kind"], "extracted_native_role_folder")
        self.assertEqual(receipt["validation"]["actions"], 2)
        self.assertEqual(load_case(self.case)["status"], "built")
        qa_review(self.case, "CI reviewer", visual_pass=True, runtime_pass=True)
        with self.assertRaisesRegex(PipelineError, "redistribution"):
            package_release(self.case)

    def test_unchanged_source_after_build_only(self):
        attach_case(self.case, self.role)
        rights_review(self.case, "CI", str(self.evidence), local_use=True)
        (self.role / "action" / "idle_0.png").write_bytes(b"tampered")
        with self.assertRaisesRegex(PipelineError, "Source files changed"):
            build_case(self.case)
        self.assertFalse((self.workspace / "build").exists())

    def test_rejects_legacy_full_app_and_mini_pet(self):
        with self.assertRaisesRegex(ValueError, "entire old application"):
            inspect_native_folder(self.role.parents[2])
        mini = self.root / "old-res" / "res" / "pet" / "派蒙"
        legacy_character(mini)
        with self.assertRaisesRegex(ValueError, "mini-pets"):
            inspect_native_folder(mini)

    def test_folder_installer_never_overwrites(self):
        out = self.root / "out"
        a = install_native_folder(self.role, out)
        self.assertTrue(a.exists())
        self.assertEqual(install_native_folder(self.role, out).name, "ChibiPet_2")
        with self.assertRaises(FileExistsError):
            install_native_folder(self.role, out, role_folder=a.name)

    def test_unsafe_scripts_and_symlinked_resources_blocked(self):
        script = self.role / "launch.bat"
        script.write_text("echo no")
        with self.assertRaisesRegex(ValueError, "Executable/script"):
            inspect_native_folder(self.role)
        script.unlink()
        link = self.role / "action" / "attack_0.png"
        try:
            link.symlink_to(self.role / "action" / "idle_0.png")
        except (NotImplementedError, OSError):
            self.skipTest("Symlink unavailable")
        with self.assertRaisesRegex(ValueError, "Linked"):
            inspect_native_folder(self.role)

    def test_install_rejects_output_root_inside_original(self):
        with self.assertRaisesRegex(ValueError, "outside original"):
            install_native_folder(self.role, self.role / "nested")

    def test_read_only_probe_recognizes_extracted_original_character(self):
        preview = probe_asset(self.role)
        self.assertEqual(preview["kind"], "native_folder")
        self.assertEqual(preview["configuration"]["frames"], 8)
        self.assertFalse(preview["license_verified"])
        self.assertFalse(preview["role_identity_verified"])
        self.assertFalse(preview["asset_modified"])

    def test_read_only_probe_of_zip_does_not_unpack_or_approve_art(self):
        import zipfile
        archive = self.root / "xiao-synthetic.zip"
        with zipfile.ZipFile(archive, "w") as container:
            for file in self.role.rglob("*"):
                if file.is_file():
                    container.write(file, "res/role/Xiao/" + file.relative_to(
                        self.role).as_posix())
        result = probe_asset(archive)
        self.assertEqual(result["kind"], "native_zip")
        self.assertEqual(result["configuration"]["contained_role_folder"], "Xiao")
        self.assertFalse(result["playable_role_verified"])
        self.assertFalse((self.root / "Xiao").exists())

    def test_status_tracks_real_pipeline_without_claiming_role_installation(self):
        result = status(self.workspace, ("xiao",))
        self.assertEqual(result["characters"][0]["stage"], "awaiting_local_artwork")
        self.assertEqual(result["counts"]["qa_verified"], 0)
        attach_case(self.case, self.role)
        self.assertEqual(status(self.workspace, ("xiao",))["characters"][0]["stage"],
                         "source_attached")
        rights_review(self.case, "CI", str(self.evidence), local_use=True)
        self.assertEqual(status(self.workspace, ("xiao",))["characters"][0]["stage"],
                         "rights_reviewed")
        self.approve_synthetic_qviews()
        build_case(self.case)
        self.assertEqual(status(self.workspace, ("xiao",))["characters"][0]["stage"],
                         "built_pending_visual_runtime_qa")
        qa_review(self.case, "CI", visual_pass=True, runtime_pass=True)
        row = status(self.workspace, ("xiao",))["characters"][0]
        self.assertEqual(row["stage"], "qa_reviewed")
        self.assertTrue(row["playable_role_verified"])
        self.assertFalse(row["redistribution_verified"])

    def test_unseeded_status_does_not_create_workspace(self):
        unknown = self.root / "unset"
        report = status(unknown, ("xiao", "wanderer"))
        self.assertEqual(report["counts"]["seeded"], 0)
        self.assertEqual(report["counts"]["qa_verified"], 0)
        self.assertFalse(unknown.exists())

    def test_actual_qt_import_worker_routes_folder_to_guarded_installer(self):
        import ast
        from shutil import rmtree
        source = Path(__file__).resolve().parents[1] / "DyberPet" / "DyberSettings" / "CharCardUI.py"
        tree = ast.parse(source.read_text("utf-8"))
        worker = next(node for node in tree.body if isinstance(node, ast.ClassDef)
                      and node.name == "ChibiImportThread")
        impl = next(node for node in worker.body if isinstance(node, ast.FunctionDef)
                    and node.name == "run")
        ns = {"rmtree": rmtree,
              "CheckCharFiles": lambda path: (0, []),
              "Path": Path}
        exec(compile(ast.Module(body=[impl], type_ignores=[]),
                     str(source), "exec"), ns)
        class Signal:
            def __init__(self):
                self.calls = []
            def emit(self, *args):
                self.calls.append(args)
        class Worker:
            pass
        instance = Worker()
        instance.source = self.role
        instance.output_root = self.root / "qt-live-role"
        instance.mode = "native_folder"
        instance.profile = None
        instance.preset = None
        instance.folder = None
        instance.done = Signal()
        ns["run"](instance)
        self.assertEqual(len(instance.done.calls), 1)
        name, error = instance.done.calls[0]
        self.assertEqual(error, "")
        self.assertTrue((instance.output_root / name / "action" / "walk_0.png").exists())
        self.assertFalse((self.root / "legacy-app" / "res" / "role" / "魈" /
                          "INSTALL_REPORT.json").exists())

    def test_explicit_folder_name_must_be_safe(self):
        with self.assertRaisesRegex(ValueError, "ASCII"):
            install_native_folder(self.role, self.root / "out", role_folder="../escape")


if __name__ == "__main__":
    unittest.main()
