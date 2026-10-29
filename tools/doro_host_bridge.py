"""Bridge a Live2D Doro window to existing DyberPet host functions.

Doro does not instantiate duplicate task, inventory or save systems. The main
PetWidget remains the source of truth. It can be hidden visually while Doro
is active but its existing system panels and scheduler continue to work.
"""
from __future__ import annotations

from tools.doro_role_progress import (
    ROLE_KEY, ensure_doro_profile, doro_progress,
)
from tools.doro_vitals import (
    ensure_doro_vitals, record_doro_activity, record_doro_task,
    snapshot_doro_vitals,
)


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

    def _pet_data(self):
        # The existing application owns PetData as a singleton; import
        # lazily so independent Doro previews have no data side effects.
        if self.pet is None:
            return None
        try:
            import DyberPet.settings as settings
            return getattr(settings, "pet_data", None)
        except (ImportError, AttributeError):
            return None

    def activate_doro_profile(self):
        data = self._pet_data()
        profile = ensure_doro_profile(data)
        if profile is not None:
            ensure_doro_vitals(data)
        return profile

    def record_doro_action(self, action):
        return record_doro_activity(self._pet_data(), action)

    def record_completed_task(self, event):
        return record_doro_task(self._pet_data(), event)

    def doro_display_context(self):
        source = self.current_host_status()
        return {
            "display_role": ROLE_KEY,
            "data_owner": source["base_role"] if source else None,
            "interactions": doro_progress(self._pet_data()),
            "doro_status": snapshot_doro_vitals(self._pet_data()),
        }

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
