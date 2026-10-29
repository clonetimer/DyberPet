"""Bridge a Live2D Doro window to existing DyberPet host functions.

Doro does not instantiate duplicate task, inventory or save systems. The main
PetWidget remains the source of truth. It can be hidden visually while Doro
is active but its existing system panels and scheduler continue to work.
"""
from __future__ import annotations


class DoroHostBridge:
    def __init__(self, app):
        self.app = app

    @property
    def pet(self):
        return getattr(self.app, "p", None)

    def _send(self, signal_name):
        pet = self.pet
        signal = getattr(pet, signal_name, None)
        emit = getattr(signal, "emit", None)
        if not callable(emit):
            return False
        try:
            emit()
        except RuntimeError:
            return False
        return True

    def open_control_panel(self):
        """Existing character-management/settings panel, not a Doro copy."""
        return self._send("show_controlPanel")

    def open_dashboard(self):
        """Existing status/tasks/inventory/notifications panel."""
        return self._send("show_dashboard")

    def current_host_status(self):
        """Read-only snapshot; clearly label the *underlying* saved role."""
        pet = self.pet
        if pet is None:
            return None
        name = getattr(pet, "curr_pet_name", None)
        if not isinstance(name, str) or not name:
            return None
        try:
            hp = pet.pet_hp.value()
            fv = pet.pet_fv.value()
        except (AttributeError, RuntimeError, TypeError):
            return None
        if not isinstance(hp, (int, float)) or not isinstance(fv, (int, float)):
            return None
        return {"base_role": name, "hp": round(hp), "fv": round(fv)}
