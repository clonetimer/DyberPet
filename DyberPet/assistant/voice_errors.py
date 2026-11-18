"""Shared failure type for optional offline voice components."""


class VoiceUnavailable(RuntimeError):
    def __init__(self, message, *, engine_completed=None):
        super().__init__(message)
        self.engine_completed = (
            engine_completed if isinstance(engine_completed, bool) else None)
