"""Validate local file proposals and execute one explicitly reviewed step at a time."""
from __future__ import annotations

import json
import threading
import unicodedata
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path

from .action_runtime import ActionRuntime
from .files import PetWorkspace, WorkspaceError

_MAX_JSON_BYTES = 128 * 1024
_MAX_STEPS = 5
_MAX_FIELD_CHARS = 120
_MAX_STEP_CHARS = 8000
_MAX_PLAN_CHARS = 16000
_ACTIONS = ("create_file", "create_note")
_INVALID_LABEL_CATEGORIES = {"Cc", "Cf", "Cs"}
_ACTIVE_STATES = ("ready", "awaiting_approval")


class TaskPlanError(ValueError):
    """The proposed plan or requested transition violates the task protocol."""


def _has_invalid_label_characters(value: str) -> bool:
    return any(unicodedata.category(character) in _INVALID_LABEL_CATEGORIES for character in value)


@dataclass(frozen=True)
class TaskStep:
    action: str
    name: str
    content: str

    def __post_init__(self):
        if type(self.action) is not str or self.action not in _ACTIONS:
            raise TaskPlanError("Task steps must create a new file or note")
        if type(self.name) is not str or _has_invalid_label_characters(self.name):
            raise TaskPlanError("Task file names must be text without control or formatting characters")
        try:
            validated_name = PetWorkspace.validate_name(self.name)
        except WorkspaceError as exc:
            raise TaskPlanError(str(exc)) from exc
        if validated_name != self.name:
            raise TaskPlanError("Task file names must already be in their final form")
        if self.action == "create_note" and Path(self.name).suffix.lower() not in (".md", ".txt"):
            raise TaskPlanError("Notes must use .md or .txt")
        if type(self.content) is not str or len(self.content) > _MAX_STEP_CHARS:
            raise TaskPlanError("Each task file must contain at most 8,000 characters of text")
        try:
            self.content.encode("utf-8")
        except UnicodeEncodeError as exc:
            raise TaskPlanError("Task file content must be valid Unicode") from exc


@dataclass(frozen=True)
class TaskPlan:
    title: str
    steps: tuple[TaskStep, ...]

    def __post_init__(self):
        if (type(self.title) is not str or not 1 <= len(self.title) <= _MAX_FIELD_CHARS
                or not self.title.strip() or _has_invalid_label_characters(self.title)):
            raise TaskPlanError("Task title must have 1–120 characters without control or formatting characters")
        if not isinstance(self.steps, (list, tuple)):
            raise TaskPlanError("Task steps must be an ordered collection")
        steps = tuple(self.steps)
        if not 1 <= len(steps) <= _MAX_STEPS or any(type(step) is not TaskStep for step in steps):
            raise TaskPlanError("Task plan must contain 1–5 valid steps")
        if len({step.name.casefold() for step in steps}) != len(steps):
            raise TaskPlanError("Task file names must be distinct, including differences in letter case")
        if sum(len(step.content) for step in steps) > _MAX_PLAN_CHARS:
            raise TaskPlanError("Task file content exceeds 16,000 characters in total")
        object.__setattr__(self, "steps", steps)


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise TaskPlanError("Task plan JSON contains a duplicate key")
        result[key] = value
    return result


def _reject_constant(_value):
    raise TaskPlanError("Task plan JSON contains an invalid number")


def parse_task_plan(text: str) -> TaskPlan:
    """Read exactly one version-1 JSON proposal without accessing a workspace."""
    if type(text) is not str:
        raise TaskPlanError("Task plan must be JSON text")
    try:
        if len(text) > _MAX_JSON_BYTES or len(text.encode("utf-8")) > _MAX_JSON_BYTES:
            raise TaskPlanError("Task plan JSON exceeds 128 KiB")
    except UnicodeEncodeError as exc:
        raise TaskPlanError("Task plan JSON must be valid Unicode") from exc
    try:
        payload = json.loads(text, object_pairs_hook=_unique_object, parse_constant=_reject_constant)
    except TaskPlanError:
        raise
    except (ValueError, RecursionError) as exc:
        raise TaskPlanError("Task plan must be one complete JSON object") from exc
    if not isinstance(payload, dict) or payload.keys() != {"version", "title", "steps"}:
        raise TaskPlanError("Task plan must contain exactly version, title and steps")
    if type(payload["version"]) is not int or payload["version"] != 1:
        raise TaskPlanError("Task plan version must be the integer 1")
    steps = payload["steps"]
    if not isinstance(steps, list) or not 1 <= len(steps) <= _MAX_STEPS:
        raise TaskPlanError("Task plan must contain 1–5 steps")
    parsed_steps = []
    for step in steps:
        if not isinstance(step, dict) or step.keys() != {"action", "name", "content"}:
            raise TaskPlanError("Each task step must contain exactly action, name and content")
        parsed_steps.append(TaskStep(**step))
    return TaskPlan(payload["title"], tuple(parsed_steps))


class TaskSession:
    """Prepare only the current step and bind all decisions to one workspace revision."""

    def __init__(self, plan: TaskPlan, runtime: ActionRuntime):
        if type(plan) is not TaskPlan:
            raise TaskPlanError("A task session requires a validated plan")
        self._plan = plan
        self._runtime = runtime
        self._binding = runtime.workspace_binding()
        self._lock = threading.Lock()
        self._state = "ready"
        self._completed: list[dict] = []
        self._error = ""
        self._request_id: str | None = None

    @property
    def plan(self) -> TaskPlan:
        return self._plan

    @property
    def workspace(self) -> PetWorkspace:
        return self._binding[0]

    @property
    def state(self) -> str:
        with self._lock:
            return self._state

    @property
    def completed(self) -> tuple[dict, ...]:
        with self._lock:
            return tuple(deepcopy(self._completed))

    @property
    def error(self) -> str:
        with self._lock:
            return self._error

    def _close(self, state: str):
        if self._request_id is not None:
            self._runtime.invalidate_pending(self._request_id)
            self._request_id = None
        self._state = state

    def _fail(self, error: Exception):
        self._close("failed")
        self._error = str(error) or type(error).__name__

    def _require_active(self):
        if self._state not in _ACTIVE_STATES:
            raise TaskPlanError("This task session has already ended")

    def prepare_next(self) -> dict:
        with self._lock:
            self._require_active()
            try:
                if self._state != "ready":
                    raise TaskPlanError("The current task step is already awaiting approval")
                with self._runtime.workspace_scope(self._binding):
                    index = len(self._completed)
                    step = self._plan.steps[index]
                    request = self._runtime.prepare(step.action, {"name": step.name, "content": step.content})
                    self._request_id = request["request_id"]
                    self._state = "awaiting_approval"
                    return {**request, "index": index, "total": len(self._plan.steps),
                            "action": step.action, "name": step.name, "content": step.content}
            except Exception as exc:
                self._fail(exc)
                raise

    def decide(self, request_id: str, confirmed: bool) -> dict | None:
        with self._lock:
            self._require_active()
            try:
                if (self._state != "awaiting_approval" or type(request_id) is not str
                        or request_id != self._request_id):
                    raise TaskPlanError("Only the current task step can be approved")
                with self._runtime.workspace_scope(self._binding):
                    if not self._runtime.approve(request_id, confirmed is True):
                        self._close("cancelled")
                        return None
                    result = self._runtime.execute(request_id)
                    self._request_id = None
                    self._completed.append(deepcopy(result))
                    self._state = "completed" if len(self._completed) == len(self._plan.steps) else "ready"
                    return result
            except Exception as exc:
                self._fail(exc)
                raise

    def cancel(self):
        with self._lock:
            if self._state in _ACTIVE_STATES:
                self._close("cancelled")
