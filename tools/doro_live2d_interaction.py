"""Doro-specific, original-model-only click responses.

No generated motion, image, audio, artwork or unspecified gesture category.
Expression selection is deterministic and limited to actually declared IDs.
"""

# The referenced Dororong model declares HitAreaFace and HitAreaLegBack.
# Use only expressions from that same model's FileReferences.Expressions.
SOURCE_HIT_REPLIES = {
    "HitAreaFace": ("Amaze", "Idle"),
    "HitAreaLegBack": ("Doubt", "Sullen"),
}


def click_expression_for_area(area_name, available_expressions):
    """The original model must supply BOTH an actual hit and an expression."""
    if not isinstance(area_name, str):
        return None
    priority = SOURCE_HIT_REPLIES.get(area_name)
    if not priority:
        return None
    names = set(available_expressions)
    return next((name for name in priority if name in names), None)


def is_same_source_area_press(pressed_area, released_area):
    """Dragging away does not count as a character tap."""
    return bool(pressed_area) and pressed_area == released_area
