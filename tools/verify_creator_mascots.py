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
        for name in ("guga","doro"):
            record=install_creator_mascot(name,root,confirmed=True)
            v=validate_native_role(root/record["folder"])
            playback=action_preview_plan(root/record["folder"])
            walk={x["name"]: x for x in playback["actions"]}
            if (playback["total_frames"]!=v["images"] or
                    not all(walk.get(k,{}).get("frame_count",0)>=4
                            for k in ("left_walk","right_walk"))):
                raise RuntimeError("Real creator source cannot provide stable native preview frames: "+name)
            if v["actions"]<4 or v["images"]<20:
                raise RuntimeError("External Codex pet lacks meaningful animation: "+name)
            rows.append({
                "key":name,"source_id":record["source_id"],
                "actions":v["actions"],"frames":v["images"],
                "preview_action_count":len(playback["actions"]),
                "rights_verified":False,
            })
        inventory=scan_mascot_library(root)["summary"]
        if (inventory["imported_creator_art_count"]!=2 or
                inventory["original_demo_count"]!=0 or
                inventory["invalid_count"]!=0):
            raise RuntimeError("Exact-source imported mascots are not classified correctly")
        print("MASCOT_PINNED_CREATOR_SOURCE_ACCEPTED",
              json.dumps({"imports":rows,"no_source_art_republished":True},
                         ensure_ascii=False))


if __name__=="__main__":
    main()
