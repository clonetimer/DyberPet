#!/usr/bin/env python3
"""Online CI only: confirm pinned Guga/Doro creator sprites really install.

No third-party sprites are uploaded to a CI artifact or committed to the repo.
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

try:
    from .install_creator_mascots import install_creator_mascot
    from .mascot_library import scan_mascot_library
    from .install_native_role import validate_native_role
    from .role_action_preview import action_preview_plan
except ImportError:
    from install_creator_mascots import install_creator_mascot
    from mascot_library import scan_mascot_library
    from install_native_role import validate_native_role
    from role_action_preview import action_preview_plan


def main():
    with tempfile.TemporaryDirectory(prefix="dyberpet-pinned-upstream-") as td:
        root=Path(td)/"role"
        rows=[]
        for name, variant in (("guga", "classic"), ("doro", "classic"),
                              ("doro", "handdrawn_v2")):
            record=install_creator_mascot(name,root,confirmed=True,
                                          variant=variant)
            v=validate_native_role(root/record["folder"])
            playback=action_preview_plan(root/record["folder"])
            import_report=json.loads((root/record["folder"]/"IMPORT_REPORT.json").read_text("utf-8"))
            provenance=json.loads((root/record["folder"]/"PERSONAL_IMPORT.json").read_text("utf-8"))
            motion=json.loads((root/record["folder"]/"CREATOR_ORIGINAL_MOTION_QA.json").read_text("utf-8"))
            pose_risks=[{"action":a["action"],
                         "risk_indicators":a["risk_indicators"],
                         "source_frames":a["frame_count"],
                         "different_visible_poses":a["unique_visible_poses"]}
                        for a in motion["actions"] if a["risk_indicators"]]
            if (import_report.get("style")!="classic" or
                    import_report.get("preserve_source_frames") is not True or
                    import_report.get("source_pixel_integrity_verified") is not True or
                    provenance.get("display_name") not in ("咕嘎","Doro") or
                    provenance.get("likeness_manually_reviewed") is not False or
                    provenance.get("motion_original_frames_checked") is not True or
                    provenance.get("motion_semantics_manually_reviewed") is not False or
                    motion["summary"]["all_frames_examined"] is not True or
                    motion["summary"]["actions_inspected"] != v["actions"] or
                    motion["summary"]["original_art_modified"] is not False or
                    motion["summary"]["motion_semantics_approved"] is not False):
                raise RuntimeError("Artist sprite geometry or character provenance was not preserved: "+name)
            walk={x["name"]: x for x in playback["actions"]}
            if (playback["total_frames"]!=v["images"] or
                    not all(walk.get(k,{}).get("frame_count",0)>=4
                            for k in ("left_walk","right_walk"))):
                raise RuntimeError("Real creator source cannot provide stable native preview frames: "+name)
            if v["actions"]<4 or v["images"]<20:
                raise RuntimeError("External Codex pet lacks meaningful animation: "+name)
            rows.append({
                "key":name,"source_variant":variant,"source_id":record["source_id"],
                "actions":v["actions"],"frames":v["images"],
                "preview_action_count":len(playback["actions"]),
                "original_motion_png_frames_inspected":motion["summary"]["frames_inspected"],
                "original_motion_pose_risks":pose_risks,
                "visual_motion_manually_approved":False,
                "physical_desktop_qa_approved":False,
                "rights_verified":False,
            })
        found=scan_mascot_library(root)
        inventory=found["summary"]
        distinct_sources={folder["source_id"]
                          for mascot in found["mascots"]
                          for folder in mascot["imported_creator_art"]}
        if (inventory["imported_creator_art_count"]!=2 or
                inventory["original_demo_count"]!=0 or
                inventory["invalid_count"]!=0 or
                distinct_sources!={"guga--circus", "doro--lingxiaotian",
                                   "doro--godxxy1229"}):
            raise RuntimeError("Exact-source imported mascot variants were not classified")
        print("MASCOT_PINNED_CREATOR_SOURCE_ACCEPTED",
              json.dumps({"imports":rows,"no_source_art_republished":True},
                         ensure_ascii=False))


if __name__=="__main__":
    main()
