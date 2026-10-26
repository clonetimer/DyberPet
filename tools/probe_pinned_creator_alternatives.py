"""R5 isolated original-artist alternatives for the five high-silhouette-risk roles.

The first preference is the installed R4 candidate. Here we probe only
additional, already pinned creator sources for the SAME exact identity.
No artist image is committed, copied to the current app, or put in the report.
A less-tall silhouette is just a manual review lead, never proof of Q likeness.
"""
from __future__ import annotations

import argparse
import importlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from tools.character_source_coverage import source_coverage
from tools.personal_source_batch import INSTALLERS
from tools.creator_standee_triage import triage_one_creator
from tools.genshin_library import scan_genshin_library

PRIORITY = (
    "genshin_ayaka", "genshin_venti", "genshin_furina",
    "genshin_sandrone", "genshin_yoimiya",
)
MAX_ATTEMPTS = 10


def probe_pinned_alternatives(*, confirmed=False, profiles=PRIORITY,
                              max_attempts=MAX_ATTEMPTS, coverage=None,
                              dispatch=None, scan=None, inspect=None):
    if not confirmed:
        raise ValueError("Explicit opt-in required before any real creator downloads")
    if (not isinstance(max_attempts, int) or
            not 1 <= max_attempts <= MAX_ATTEMPTS):
        raise ValueError("At most 10 pinned alternative probes are allowed")
    if (not isinstance(profiles, (tuple, list)) or not profiles or
            len(set(profiles)) != len(profiles) or
            any(p not in PRIORITY for p in profiles)):
        raise ValueError("Only five measured original-art risk profiles may be probed")
    registry = coverage or source_coverage()
    roles = {x["id"]: x for x in registry["characters"]}
    if dispatch is None:
        def dispatch(provider, key, root):
            module, function = INSTALLERS[provider]
            return getattr(importlib.import_module(module), function)(
                key, root, confirmed=True)
    scan = scan or scan_genshin_library
    inspect = inspect or triage_one_creator
    tested = []
    for profile in profiles:
        options = roles[profile]["source_candidates"]
        if len(options) < 2:
            tested.append({"profile": profile, "status": "no_pinned_alternative"})
            continue
        # Skip first preferred source. Alternatives are only fixed candidates,
        # not yet approved or necessarily different from installed R4 art.
        for option in options[1:]:
            if len(tested) >= max_attempts:
                break
            provider, key = option["provider"], option["source_key"]
            if provider not in INSTALLERS:
                tested.append({"profile": profile, "provider": provider,
                               "source_key": key, "status": "unsupported"})
                continue
            record = {"profile": profile, "provider": provider, "source_key": key,
                      "human_q_likeness_verified": False,
                      "rights_for_redistribution_verified": False}
            try:
                # Every upstream installer writes into a disposable, empty
                # directory, never into the packaged application or user's role.
                with TemporaryDirectory(prefix="dyberpet-r5-alt-") as tmp:
                    role_root = Path(tmp) / "res" / "role"
                    role_root.mkdir(parents=True)
                    dispatch(provider, key, role_root)
                    inventory = scan(role_root)
                    entry = next((r for r in inventory["characters"]
                                  if r["profile"] == profile), None)
                    if entry is None:
                        raise ValueError("Source installed a different character identity")
                    folders = [x["folder"] for x in entry["installed_folders"]
                               if not x.get("is_original_demo")]
                    if not folders:
                        raise ValueError("No non-demo original-art folder with matching identity")
                    variants = []
                    for folder in folders:
                        measured = inspect(role_root, folder)
                        variants.append({
                            "folder": folder,
                            "silhouette_width_height_ratio": measured.get(
                                "silhouette_width_height_ratio"),
                            "thin_silhouette_risk": any(
                                "silhouette" in x for x in measured["risk_indicators"]),
                            "weak_motion_risk": bool(
                                measured.get("weak_movement_action_evidence")),
                            "risk_indicators": list(measured["risk_indicators"]),
                        })
                    record["status"] = "source_installed_structurally"
                    record["variants"] = variants
            except (OSError, ValueError, RuntimeError, KeyError, TypeError) as exc:
                record["status"] = "source_unavailable_or_invalid"
                record["error"] = type(exc).__name__ + ": " + str(exc)[:180]
            tested.append(record)
        if len(tested) >= max_attempts:
            break
    return {
        "scope": "temporary_exact-pinned-source-probes_json_only",
        "summary": {
            "target_profiles": len(profiles),
            "attempted_pinned_alternative_sources": len(tested),
            "structurally_installed_alternatives": sum(
                x.get("status") == "source_installed_structurally" for x in tested),
            "unavailable_or_invalid": sum(
                x.get("status") == "source_unavailable_or_invalid" for x in tested),
            "human_approved_q_alternatives": 0,
            "art_uploaded": False,
        },
        "probes": tested,
        "warning": ("The approved identity, original chibi likeness and correct "
                    "animation semantics remain UNREVIEWED; a wider silhouette "
                    "alone is NOT proof of a better Q-shaped character."),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--accept-personal-use", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.output.exists() or args.output.is_symlink() or args.output.suffix.lower() != ".json":
        raise ValueError("Use a new JSON-only output file")
    r = probe_pinned_alternatives(confirmed=args.accept_personal_use)
    args.output.write_text(json.dumps(r, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    print("R5_ALTERNATE_REAL_ART_SUMMARY=" + json.dumps(r["summary"], ensure_ascii=False))


if __name__ == "__main__":
    main()
