# Approved Task Plans Implementation Plan

> **For agentic workers:** Use superpowers:subagent-driven-development or superpowers:executing-plans; follow the isolated file ownership below and record evidence.

**Goal:** Turn an explicit local AI request into a bounded file plan that the user reviews and executes one step at a time.

**Architecture:** A pure validated immutable plan and stateful approval session wrap the existing ActionRuntime. A separate local structured-output adapter generates proposals; the Qt task review dialog alone obtains user decisions.

**Tech Stack:** Python 3.9+, stdlib, existing PySide6, existing loopback HTTP transport. No new application dependency.

**Spec:** `docs/superpowers/specs/2026-11-18-approved-task-plans-design.md`

## Global Constraints

- Version 1 strict JSON, 1–5 steps, create_file/create_note only; title 1–120 characters.
- Each file <=8,000 characters; aggregate <=16,000 characters; raw plan <=128 KiB.
- Existing workspace extensions and no-overwrite rules apply; preserve exact reviewed bytes.
- No shell, background reads, auto approval, overwrite, bulk execution or automatic retry.
- Draft PR #99 stays on its existing feature branch; main is not merged or released.

## Review Focus

- Role/workspace/history/window changes while generation or confirmation is pending invalidate old work.
- A plan failing on step two must preserve and accurately report step one.
- Post-write audit errors must not cause retries or label a completed write as failed.
- Two clicks/replayed request IDs cannot write twice or approve the wrong step.
- Malformed/truncated/unsupported model responses never produce an executable proposal.

## Task 1: Strict plan and execution session

Files: create `DyberPet/assistant/task_plan.py`, `tests/test_assistant_task_plan.py`; modify `action_runtime.py` and its tests only for atomic scope invalidation.

Interfaces: `TaskPlanError(ValueError)`, immutable `TaskStep(action, name, content)`, `TaskPlan(title, steps)`, `parse_task_plan(text) -> TaskPlan`; `TaskSession(plan, runtime)` exposes `state`, `completed`, `error`, `prepare_next() -> dict`, `decide(request_id, confirmed) -> dict | None`, `cancel()`.

Prepare result includes runtime request_id/preview plus `index` (0-based), `total`, `action`, `name`, `content`. `completed` contains successful runtime result dictionaries. States: `ready`, `awaiting_approval`, `completed`, `cancelled`, `failed`. `decide` handles only the currently prepared request; exceptions close session as failed and propagate. Cancellation retains completed results. Workspace object identity is captured and checked before prepare/decide. Add `ActionRuntime.invalidate_pending()` and ensure lock covers state-changing operations.

- [x] Write/run failing tests for invalid protocol, no writes before approval, per-step approval, cancellation, failure, expiry, replay and workspace replacement.
- [x] Implement immutable validation, session state and minimal runtime scope hardening.
- [x] Run `python -m unittest discover -s tests -p 'test_assistant_task_plan.py' -v` and action-runtime suite; inspect result.

## Task 2: Local model adapter and review UI

Files: create `task_planner.py`, `task_review.py`, `tests/test_assistant_task_planner.py`; modify `ui.py`, `tests/test_assistant_qt.py`.

Interface: `generate_task_plan(text, *, base_url, model, file_context=None) -> TaskPlan`. Uses current `_local_base` and `_json_request`, nonstream JSON Schema request; `max_tokens=4096`, timeout 45s, strict complete reply checks. Optional selected-file context is validated and appears as untrusted user data, not system instructions. `TaskReviewDialog(session, parent=None)` presents exact current action/path/content and per-step status; approval executes one current request, cancel/window dismissal stops remainder. Qt owner binds proposal to a generation token and clears all stale session state.

- [x] Write/run failing adapter tests with local HTTP fixtures; implement the request/validation contract.
- [x] Write/run failing Qt tests for exact preview, one-click/one-step, cancel/partial completion and stale session changes; implement review and integration.
- [x] Run targeted Qt suite and assistant discovery; preserve the user input when busy and ignore stale worker failures.

## Task 3: Experience, review and delivery

Files: `docs/DEVELOPMENT_EXPERIENCE.md`, `docs/pet_assistant.md`, this plan's evidence record.

- [x] Record prior experience with the precise green baseline, causal lessons and hardware evidence limits.
- [x] Review all changes in a fresh agent, resolve material findings with regression evidence.
- [x] Run assistant/full repository tests as feasible; report failures/skips by cause. Compile and inspect diff.
- [ ] Commit one coherent batch, push existing branch, update PR description, inspect SHA-specific Desktop and Windows CI once useful work has finished. The final remote result is recorded on PR #99; local evidence is in `docs/verification/2026-11-18-approved-task-plans.md`.
