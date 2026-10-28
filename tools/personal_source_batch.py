#!/usr/bin/env python3
"""Plan or explicitly install pinned creator art on one local PC.

No artwork is bundled, uploaded to GitHub or placed into a public Release.
A pinned source is not an artist-rights, game-likeness or playback approval.
"""
from __future__ import annotations

import argparse
import importlib
import json
from pathlib import Path
import sys

try:
    from .character_source_coverage import source_coverage
    from .genshin_library import scan_genshin_library
except ImportError:
    from tools.character_source_coverage import source_coverage
    from tools.genshin_library import scan_genshin_library

# Only independently full-byte/CI-verified React LFS modules may auto-install.
# Never fetch raw pointers, run upstream TypeScript, or infer art/voice rights.
def default_role_root():
    """PyInstaller helper installs beside DyberPet.exe, never in _MEIPASS."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent / "res" / "role"
    return Path(__file__).resolve().parents[1] / "res" / "role"



MAX_RETRY_REPORT_BYTES = 2 * 1024 * 1024


def read_failed_profiles_from_report(path):
    """Read previous USER-OWNED summary, not its untrusted provider/URL/paths.

    Use only exact failed canonical IDs; recompute all actual trusted source
    URLs and installed/available status from fresh registries and disk scan.
    """
    file = Path(path).expanduser()
    if (file.is_symlink() or not file.is_file() or
            not 0 < file.stat().st_size <= MAX_RETRY_REPORT_BYTES):
        raise ValueError("Retry report must be a readable bounded JSON file")
    try:
        obj = json.loads(file.read_text(encoding="utf-8-sig"))
    except (UnicodeError, OSError, json.JSONDecodeError) as exc:
        raise ValueError("Unable to parse previous installation report") from exc
    if not isinstance(obj, dict) or not isinstance(obj.get("installation"), dict):
        raise ValueError("Previous report has no installation results")
    record = obj["installation"]
    if record.get("scope") != "local_personal_install_only":
        raise ValueError("Previous report is not a personal installation report")
    results = record.get("results")
    if not isinstance(results, list) or not 1 <= len(results) <= 123:
        raise ValueError("Previous installation report contains invalid results")
    failed = set()
    for row in results:
        if not isinstance(row, dict) or not isinstance(row.get("profile"), str):
            raise ValueError("Malformed character status in previous report")
        profile = row["profile"]
        if row.get("status") == "failed":
            if not profile.startswith("genshin_") or len(profile) > 80:
                raise ValueError("Invalid previous failed character identity")
            failed.add(profile)
        elif row.get("status") != "installed_unreviewed":
            raise ValueError("Unexpected previous role status")
    return sorted(failed)


def classify_source_failure(exc):
    """Diagnostic *classification only*. Never weaken source SHA or identity checks."""
    from urllib.error import HTTPError, URLError
    import socket
    import ssl
    if isinstance(exc, HTTPError):
        return "source_http_" + str(exc.code)
    if isinstance(exc, (TimeoutError, socket.timeout)):
        return "network_timeout"
    if isinstance(exc, ssl.SSLError):
        return "tls_verification"
    if isinstance(exc, URLError):
        return "source_network"
    if isinstance(exc, FileExistsError):
        return "source_folder_exists"
    if isinstance(exc, ValueError):
        return "source_integrity_or_format"
    if isinstance(exc, (ConnectionError, OSError)):
        return "io_or_network"
    return "other_error"


INSTALLERS = {
    "native": ("tools.install_artist_genshin", "install_artist_genshin"),
    "codex": ("tools.install_artist_codex", "install_artist_codex"),
    "shimeji": ("tools.install_artist_shimeji", "install_artist_shimeji"),
    "nano_shimeji": ("tools.install_nanopet_shimeji", "install_nanopet_shimeji"),
    "pinned_eula_creator": ("tools.install_pinned_eula_shimeji", "install_pinned_eula_shimeji"),
    "independent_codex": ("tools.install_external_codex", "install_external_codex"),
    "codexpetdb_zip": ("tools.install_pinned_codexpetdb", "install_pinned_codexpetdb"),
    "react_lfs": ("tools.install_verified_react_lfs", "install_verified_react_lfs"),
    "gmcy_diona": ("tools.install_gmcy_diona", "install_gmcy_diona"),
    "gmcy_keqing": ("tools.install_gmcy_keqing", "install_gmcy_keqing"),
}


def plan_personal_sources(role_root, *, only_profiles=None,
                          coverage=None, inventory=None):
    """Read-only plan; never download or create a character directory."""
    root = Path(role_root).expanduser()
    if root.is_symlink() or (root.exists() and not root.is_dir()):
        raise ValueError("Role root must be a real directory, not a symlink")
    coverage = source_coverage() if coverage is None else coverage
    inventory = scan_genshin_library(root) if inventory is None else inventory
    installed = {
        item["profile"] for item in inventory["characters"]
        if any(not f.get("is_original_demo", False)
               for f in item.get("installed_folders", []))
    }
    entries = coverage["characters"]
    known = {r["id"] for r in entries}
    selected = set(only_profiles) if only_profiles is not None else known
    if not selected.issubset(known):
        raise ValueError("Unknown role profile(s): " + ", ".join(sorted(selected - known)))
    planned = []
    for role in entries:
        profile = role["id"]
        if profile not in selected:
            continue
        options = role["source_candidates"]  # Existing source preference ordering.
        supported = next((o for o in options if o["provider"] in INSTALLERS), None)
        chosen = supported or (options[0] if options else None)
        # Ordered strictly by the existing source preference policy. Never
        # add unpinned, unmatched, or manual-only candidates as fallback.
        supported_sources = [
            {"provider": option["provider"], "source_key": option["source_key"],
             "source_url": option["url"]}
            for option in options if option["provider"] in INSTALLERS
        ]
        status = ("already_installed" if profile in installed else
                  "missing_source" if chosen is None else
                  "manual_import_only" if chosen["provider"] not in INSTALLERS else
                  "ready_for_opt_in")
        planned.append({
            "profile": profile, "name": role["name"], "status": status,
            "source_count": len(options),
            "provider": chosen["provider"] if chosen else None,
            "source_key": chosen["source_key"] if chosen else None,
            "source_url": chosen["url"] if chosen else None,
            "supported_sources": supported_sources,
            "automatic_source_count": len(supported_sources),
            "can_retry_pinned_fallback": len(supported_sources) > 1,
            "original_likeness_verified": False,
            "rights_verified_by_tool": False,
            "real_device_playback_verified": False,
        })
    return {
        "scope": "personal_local_install_plan_no_artwork_included",
        "summary": {
            "selected_profiles": len(planned),
            "already_installed_structurally": sum(x["status"] == "already_installed" for x in planned),
            "ready_for_opt_in": sum(x["status"] == "ready_for_opt_in" for x in planned),
            "manual_import_only": sum(x["status"] == "manual_import_only" for x in planned),
            "missing_source": sum(x["status"] == "missing_source" for x in planned),
            "local_invalid_folders": len(inventory.get("invalid_local", [])),
            "roles_with_multiple_auto_sources": sum(
                x["automatic_source_count"] > 1 for x in planned),

        },
        "note": "PINNED SOURCE != INSTALLED/APPROVED ART. Rights, likeness, voice and live playback remain unverified.",
        "characters": planned,
    }


def install_personal_plan(plan, role_root, *, confirmed=False, max_roles=None,
                          dispatch=None, inventory_reader=None, progress=None,
                          should_stop=None, checkpoint=None):
    """Install sources and reconcile every claimed success against actual local art."""
    if not confirmed:
        raise ValueError("Explicit --accept-personal-use confirmation required")
    root = Path(role_root).expanduser()
    if root.is_symlink() or (root.exists() and not root.is_dir()):
        raise ValueError("Role root must be a real directory, not a symlink")
    if max_roles is not None and (not isinstance(max_roles, int) or max_roles < 1):
        raise ValueError("max_roles must be a positive integer")
    if dispatch is None:
        def dispatch(provider, key, dest):
            module, name = INSTALLERS[provider]
            return getattr(importlib.import_module(module), name)(key, dest, confirmed=True)
    results = []
    count = 0
    source_attempts = 0
    fallback_recovered = 0
    stopped_by_user = False
    for item in plan["characters"]:
        if item["status"] != "ready_for_opt_in":
            continue
        if max_roles is not None and count >= max_roles:
            break
        # Cancellation takes effect between complete per-character installs:
        # never interrupt a partially written native role mid-conversion.
        if should_stop is not None and should_stop():
            stopped_by_user = True
            break
        count += 1
        profile, provider, key = item["profile"], item["provider"], item["source_key"]
        if progress is not None:
            progress({"stage": "role_start", "profile": profile, "index": count})
        # Old consumer-generated plans may predate supported_sources; in
        # that case keep single-source behavior. New plans retry ONLY pinned
        # sources listed for this SAME character, in preference order.
        sources = item.get("supported_sources")
        if sources is None:
            sources = [{"provider": provider, "source_key": key,
                        "source_url": item.get("source_url")}]
        if not isinstance(sources, list) or not sources:
            raise ValueError("Invalid pinned source plan")
        if any(not isinstance(x, dict) or
               x.get("provider") not in INSTALLERS or
               not isinstance(x.get("source_key"), str) or
               not x["source_key"] for x in sources):
            raise ValueError("Unrecognized installer in personal plan")
        attempts = []
        successful = None
        # Hard cap retries per character to limit resource exhaustion.
        for source in sources[:4]:
            p, k = source["provider"], source["source_key"]
            source_attempts += 1
            if progress is not None:
                progress({"stage": "source_start", "profile": profile,
                          "provider": p, "attempt": len(attempts) + 1})
            try:
                dispatch(p, k, root)
            except (OSError, ValueError, RuntimeError, KeyError, TypeError) as exc:
                failure_type = classify_source_failure(exc)
                failure_text = type(exc).__name__ + ": " + str(exc)[:240]
                attempts.append({
                    "provider": p, "source_key": k, "status": "failed",
                    "failure_class": failure_type,
                    "reason": failure_text})
                if progress is not None:
                    progress({"stage": "source_failed", "profile": profile,
                              "provider": p, "attempt": len(attempts),
                              "reason": failure_text, "failure_class": failure_type,
                              "has_next_pinned_source": len(attempts) < min(len(sources), 4)})
            else:
                attempts.append({"provider": p, "source_key": k,
                                 "status": "installed_unreviewed"})
                successful = source
                if progress is not None:
                    progress({"stage": "source_returned", "profile": profile,
                              "provider": p, "pending_inventory_check": True})
                break
        if successful is None:
            results.append({"profile": profile, "status": "failed",
                            "reason": attempts[-1]["reason"],
                            "source_attempts": attempts})
        else:
            recovered = len(attempts) > 1
            fallback_recovered += int(recovered)
            results.append({
                "profile": profile, "status": "installed_unreviewed",
                "provider": successful["provider"],
                "source_key": successful["source_key"],
                "used_fallback": recovered, "source_attempts": attempts,
            })
        # Save each completed character immediately, before the next fetch.
        # This event is *provisional*: only the final inventory scan can
        # confirm actual native files, so journals must not claim QA PASS.
        if checkpoint is not None:
            checkpoint({"profile": profile,
                        "status": "pending_inventory_validation"
                                  if successful is not None else "failed",
                        "source_attempts": list(attempts),
                        "index": count})
    # Installer functions may return without throwing even if a role was not
    # actually registered, its frames were rejected, or the identity differs.
    # Rescan the real native role catalogue exactly once after the batch.
    # Do not turn a successful function return into a false installed count.
    verify = scan_genshin_library if inventory_reader is None else inventory_reader
    verification_error = None
    invalid_after = None
    recognized = set()
    recognized_folders = {}
    try:
        updated = verify(root)
        recognized_folders = {
            entry["profile"]: [folder["folder"]
                for folder in entry.get("installed_folders", [])
                if not folder.get("is_original_demo", False)
                and isinstance(folder.get("folder"), str)]
            for entry in updated["characters"]
        }
        recognized = {
            entry["profile"] for entry in updated["characters"]
            if any(not folder.get("is_original_demo", False)
                   for folder in entry.get("installed_folders", []))
        }
        invalid_after = len(updated.get("invalid_local", []))
    except (OSError, ValueError, RuntimeError, KeyError, TypeError) as exc:
        verification_error = type(exc).__name__ + ": " + str(exc)[:180]
    for result in results:
        if result["status"] == "installed_unreviewed":
            if result["profile"] not in recognized:
                result["status"] = "failed"
                result["post_install_validation_failed"] = True
                result["reason"] = ("Local inventory verification unavailable: " + verification_error
                                    if verification_error else
                                    "Installer returned, but no structurally valid creator art was "
                                    "recognized for this exact character")
            else:
                result["post_install_validation_passed"] = True
                # Preview only explicitly recognized, still-present native
                # folders for the exact profile. Never guess from source URL.
                result["verified_native_folders"] = recognized_folders.get(
                    result["profile"], [])
        if progress is not None:
            progress({"stage": "role_verified", "profile": result["profile"],
                      "status": result["status"]})
    return {
        "scope": "local_personal_install_only", "attempted": count,
        "stopped_by_user": stopped_by_user,
        "installed_unreviewed": sum(x["status"] == "installed_unreviewed" for x in results),
        "failed": sum(x["status"] == "failed" for x in results),
        "source_attempts": source_attempts,
        "fallback_recovered_profiles": sum(
            item["status"] == "installed_unreviewed" and item.get("used_fallback", False)
            for item in results),
        "post_install_inventory_checked": verification_error is None,
        "post_install_inventory_error": verification_error,
        "post_install_invalid_folders": invalid_after,
        "post_install_recognized_creator_profiles": len(recognized),
        "results": results, "no_artwork_uploaded": True,
        "failed_profiles": [x["profile"] for x in results if x["status"] == "failed"],
        "failure_class_counts": {
            failure_class: sum(
                any(a.get("failure_class") == failure_class
                    for a in x.get("source_attempts", []))
                for x in results if x["status"] == "failed")
            for failure_class in sorted({
                a["failure_class"] for x in results
                for a in x.get("source_attempts", [])
                if a.get("failure_class")
            })
        },
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--role-root", type=Path,
                    default=default_role_root())
    ap.add_argument("--whale", action="store_true",
                    help="Plan or locally install the independent noncommercial Whale Pet")
    ap.add_argument("--whale-full", action="store_true",
                    help="Convert all 95 pinned whale clips instead of 16 core clips")
    ap.add_argument("--mascots", action="store_true",
                    help="Plan or explicitly install Guga/Doro original creator fan-art locally")
    ap.add_argument("--doro-v2", action="store_true",
                    help="With --mascots, opt in to separately drawn Doro V2 instead of legacy source")
    ap.add_argument("--profile", action="append", default=None,
                    help="Repeatable genshin_... profile (default: all 123 templates)")
    ap.add_argument("--retry-failed-from", type=Path,
                    help="Recompute and retry only failed characters from the previous JSON report; never trust source URLs in report")
    ap.add_argument("--bundle-output", type=Path,
                    help="Create LOCAL offline Windows app ZIP with your installed art; never upload")
    ap.add_argument("--confirm-local-bundle", action="store_true",
                    help="Confirm private/local-only copy and creator use terms")
    ap.add_argument("--install", action="store_true",
                    help="Actually fetch selected exact-pinned sources to local role folder")
    ap.add_argument("--accept-personal-use", action="store_true",
                    help="Explicit opt-in; review each creator's use conditions yourself")
    ap.add_argument("--max-roles", type=int, default=None,
                    help="Maximum installation attempts (try two first)")
    ap.add_argument("--output", type=Path,
                    help="Optional .json plan/report path; never an art archive")
    args = ap.parse_args(argv)
    try:
        if args.bundle_output is not None:
            if args.install or args.mascots or args.doro_v2 or args.whale or args.whale_full or args.profile or args.retry_failed_from or args.output or args.max_roles is not None or args.accept_personal_use:
                raise ValueError("--bundle-output cannot be combined with install/planning options")
            try:
                from .local_offline_bundle import create_local_bundle
            except ImportError:
                from tools.local_offline_bundle import create_local_bundle
            portable_root = args.role_root.resolve().parent.parent
            result = create_local_bundle(portable_root, args.bundle_output,
                                         confirmed=args.confirm_local_bundle)
            if hasattr(sys.stdout, "reconfigure"):
                sys.stdout.reconfigure(encoding="utf-8")
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0
        if args.confirm_local_bundle:
            raise ValueError("--confirm-local-bundle requires --bundle-output")
        if args.retry_failed_from is not None and (args.whale or args.mascots or args.doro_v2):
            raise ValueError("--retry-failed-from applies only to Genshin character installs")
        if args.whale_full and not args.whale:
            raise ValueError("--whale-full requires --whale")
        if args.whale:
            if args.mascots or args.profile or args.doro_v2 or args.max_roles is not None:
                raise ValueError("Whale installation cannot use Genshin/mascot options")
            from tools.install_whale_pet import install_whale_pet, source_catalog, select_actions
            chosen = "full" if args.whale_full else "core"
            catalog = source_catalog()
            result = {"name": "Whale Pet", "selection": chosen,
                      "pinned_animation_catalog": catalog["animation_count"],
                      "selected_animation_count": len(select_actions(catalog, chosen)),
                      "source_commit": catalog["source_commit"],
                      "no_artwork_prebundled": True,
                      "media_license": catalog["source_license"],
                      "installed": False}
            if args.install:
                installed = install_whale_pet(args.role_root,
                                              confirmed=args.accept_personal_use,
                                              selection=chosen)
                result.update(installed= True, installation=installed)
            elif args.accept_personal_use:
                raise ValueError("--accept-personal-use requires --install")
            text_result = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
            if args.output:
                if args.output.suffix.lower() != ".json":
                    raise ValueError("Whale report must have .json extension")
                args.output.parent.mkdir(parents=True, exist_ok=True)
                args.output.write_text(text_result, encoding="utf-8")
            else:
                if hasattr(sys.stdout, "reconfigure"):
                    sys.stdout.reconfigure(encoding="utf-8")
                print(text_result, end="")
            return 0
        if args.mascots and args.profile:
            raise ValueError("--mascots and --profile cannot be combined")
        if args.doro_v2 and not args.mascots:
            raise ValueError("--doro-v2 requires --mascots")
        if args.mascots:
            try:
                from .personal_mascot_batch import plan_mascot_sources, install_mascot_plan
            except ImportError:
                from tools.personal_mascot_batch import plan_mascot_sources, install_mascot_plan
            mascot_plan = plan_mascot_sources(
                args.role_root, doro_variant="handdrawn_v2" if args.doro_v2 else "classic")
            if args.install:
                def mascot_progress(event):
                    if event["stage"] == "role_start":
                        message = f"Installing {event['key']} creator artwork ..."
                    else:
                        message = f"Verified {event['key']}: {event['status']}"
                    # JSON goes to --output file; stdout is safe for Windows PowerShell progress.
                    # Without --output, emit progress on stderr to keep stdout valid JSON.
                    print(message, file=sys.stdout if args.output else sys.stderr, flush=True)
                result = {"plan_summary": mascot_plan["summary"],
                          "installation": install_mascot_plan(
                              mascot_plan, args.role_root,
                              confirmed=args.accept_personal_use,
                              progress=mascot_progress)}
            else:
                if args.accept_personal_use:
                    raise ValueError("--accept-personal-use requires --install")
                result = mascot_plan
            output = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
            if args.output:
                if args.output.suffix.lower() != ".json":
                    raise ValueError("Report must use .json extension")
                args.output.write_text(output, encoding="utf-8")
            else:
                if hasattr(sys.stdout, "reconfigure"):
                    sys.stdout.reconfigure(encoding="utf-8")
                print(output, end="")
            return 0 if not args.install or not result["installation"]["failed"] else 1
        if args.retry_failed_from is not None:
            if args.profile:
                raise ValueError("--retry-failed-from cannot be combined with --profile")
            if args.output is not None and args.output.resolve() == args.retry_failed_from.resolve():
                raise ValueError("New report must not overwrite the original retry report")
            failed_profiles = read_failed_profiles_from_report(args.retry_failed_from)
            if not failed_profiles:
                raise ValueError("Previous report has no failed characters to retry")
            plan = plan_personal_sources(args.role_root, only_profiles=failed_profiles)
        else:
            plan = plan_personal_sources(args.role_root, only_profiles=args.profile)
        if args.install:
            try:
                from .chibi_profiles import CHIBI_PROFILES
            except ImportError:
                from tools.chibi_profiles import CHIBI_PROFILES
            total = min(plan["summary"]["ready_for_opt_in"],
                        args.max_roles if args.max_roles is not None else
                        plan["summary"]["ready_for_opt_in"])
            def show_progress(event):
                stage, profile = event["stage"], event["profile"]
                role_name = CHIBI_PROFILES.get(profile, {}).get("name", profile)
                display = f"{role_name} ({profile})" if role_name != profile else profile
                if stage == "role_start":
                    message = f"[{event['index']}/{total}] 正在安装 {display}"
                elif stage == "source_start":
                    message = f"  source {event['attempt']}: {event['provider']} ..."
                elif stage == "source_failed":
                    suffix = ("; trying next pinned source" if event.get("has_next_pinned_source")
                              else "; no further verified source for this character")
                    message = (f"  source {event['attempt']} failed "
                               f"[{event.get('failure_class', 'unknown')}]: "
                               f"{event.get('reason', '')[:180]}{suffix}")
                elif stage == "source_returned":
                    message = "  download/import returned; checking actual role inventory at end"
                else:
                    message = f"  验证结果 {display}: {event['status']}"
                # JSON goes to --output file; stdout is safe for Windows PowerShell progress.
                # Without --output, emit progress on stderr to keep stdout valid JSON.
                print(message, file=sys.stdout if args.output else sys.stderr, flush=True)
            result = {"plan_summary": plan["summary"],
                      "installation": install_personal_plan(
                          plan, args.role_root, confirmed=args.accept_personal_use,
                          max_roles=args.max_roles, progress=show_progress)}
        else:
            if args.accept_personal_use:
                ap.error("--accept-personal-use requires --install")
            result = plan
        output = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
        if args.output:
            if args.output.suffix.lower() != ".json":
                raise ValueError("Report must use .json extension")
            args.output.write_text(output, encoding="utf-8")
        else:
            if hasattr(sys.stdout, "reconfigure"):
                sys.stdout.reconfigure(encoding="utf-8")
            print(output, end="")
        return 0 if not args.install or not result["installation"]["failed"] else 1
    except (OSError, ValueError, KeyError, TypeError) as exc:
        ap.exit(2, "Personal source plan blocked: " + str(exc) + "\n")


if __name__ == "__main__":
    raise SystemExit(main())
