"""Recognize *completed* host task transitions before crediting Doro.

The host emits two legacy completion signals whose provenance is ambiguous.
Track the authoritative scheduler status sequence instead: no starts, no
rewards; cancelled or duplicate endings cannot mint coins. For tomato runs,
each intermediate rest earns one pomodoro credit, and the final batch end
earns one task credit (never both for the same boundary).
"""
from __future__ import annotations

from dataclasses import dataclass

@dataclass
class DoroTaskSettlement:
    phase: str = "idle"

    def reset(self):
        self.phase = "idle"

    def transition(self, status: str):
        """Return R64/R65's existing reward event or None."""
        if status == "focus_start":
            if self.phase == "idle":
                self.phase = "focus"
            return None
        if status == "focus_end":
            if self.phase != "focus":
                return None
            self.phase = "idle"
            return "task_finished"
        if status == "focus_cancel":
            if self.phase == "focus":
                self.phase = "idle"
            return None
        if status == "tomato_start":
            if self.phase in ("idle", "tomato_rest"):
                self.phase = "tomato"
            return None
        if status == "tomato_rest":
            if self.phase != "tomato":
                return None
            self.phase = "tomato_rest"
            return "pomodoro_finished"
        if status == "tomato_end":
            if self.phase != "tomato":
                return None
            self.phase = "idle"
            return "task_finished"
        if status == "tomato_cencel":
            if self.phase in ("tomato", "tomato_rest"):
                self.phase = "idle"
            return None
        return None
