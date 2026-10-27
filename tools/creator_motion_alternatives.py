"""Conservative, read-only comparison of SAME-person original motion frames.

The only positive finding is that one actual artist version provides
structurally stronger visible pose evidence for the SAME native interaction.
It is NOT a vote on resemblance, Q-style, animation semantics or copyright.
Never modify, splice, synthesize, or auto-activate any creator artwork.
"""
from __future__ import annotations

WEAK_MOVEMENT_FLAGS = frozenset((
    "single_frame_motion",
    "translation_only_or_static_pose",
    "long_identical_pose_run",
))


def compare_motion_evidence(left, right):
    """Return an optional *manual review* candidate, never an automatic winner.

    Only infer a review lead when precisely one side has a known weak-motion
    indicator and the other has two or more distinct visible poses, two or
    more frames and zero recorded pose risks. Unknown/incomplete/mismatched
    analysis cannot be promoted to a "better" author artwork.
    """
    fallback = {
        "status": "no_safe_review_lead", "candidate_index": None,
        "human_likeness_approved": False, "motion_semantics_approved": False,
        "source_art_modified": False,
        "text": "暂无足够的逐帧证据区分两套动作；请人工逐帧核对",
    }
    if not isinstance(left, dict) or not isinstance(right, dict):
        return fallback
    try:
        if (not left.get("movement_expected") or
                not right.get("movement_expected") or
                left.get("action") is None or right.get("action") is None):
            return fallback
        for item in (left, right):
            if (not isinstance(item.get("risk_indicators"), list) or
                    type(item.get("unique_visible_poses")) is not int or
                    type(item.get("frame_count")) is not int or
                    item["frame_count"] < 1 or
                    not 0 <= item["unique_visible_poses"] <= item["frame_count"]):
                return fallback
    except (KeyError, TypeError, ValueError):
        return fallback

    def weak(item):
        return bool(WEAK_MOVEMENT_FLAGS.intersection(item["risk_indicators"]))

    def stronger(item):
        return (not item["risk_indicators"] and
                item["unique_visible_poses"] >= 2 and
                item["frame_count"] >= 2)

    if weak(left) and stronger(right):
        index = 1
    elif weak(right) and stronger(left):
        index = 0
    else:
        return fallback

    candidate = (left, right)[index]
    return {
        "status": "stronger_pose_evidence_pending_human_review",
        "candidate_index": index,
        "human_likeness_approved": False, "motion_semantics_approved": False,
        "source_art_modified": False,
        "text": (
            f"仅从逐帧姿态证据看，{'左侧 A' if index == 0 else '右侧 B'}"
            f"值得优先复核：{candidate['frame_count']} 帧，"
            f"{candidate['unique_visible_poses']} 种不同可见姿态，未触发"
            "现有自动运动风险项。并不证明动作自然或形象接近原设。"
        ),
    }
