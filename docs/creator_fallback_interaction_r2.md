# DyberPet Creator Art + Interaction R2

## Scope

This development increment starts from `release/personal65-python-rust-20261026` and improves the **real 65-source subset of the 123 Genshin templates**, plus existing Guga/Doro creator roles. It never synthesizes missing characters or adds third-party art to the repository.

## Pinned source recovery

Earlier batch installs selected the first supported source and counted the entire role as failed when that single endpoint was unavailable, even if more verified source candidates existed.

- The source coverage planner now records `supported_sources[]` per role, preserving the exact preference ordering from the existing coverage registry.
- The installer attempts a maximum of four *already registered and version-pinned* sources, sequentially, **stopping immediately after a successful install**. Manual-only/unknown sources are never silently treated as valid installers.
- `max_roles` remains a bound on *distinct character installs*, not HTTP calls. `source_attempts` and `fallback_recovered_profiles` are reported separately from `installed_unreviewed` and `failed`.
- Every attempt has a provider, source key, status and bounded failure reason. Failures do not rewrite installed artist art or claim visual likeness/voice/rights approval.
- Existing older installation-plan JSON without a `supported_sources` field keeps single-source behavior; no hidden additional downloads.
- Real coverage gains are determined only by rerunning cloud installs, not by tests of mocked network failures. An existing 58/59 success count must not be automatically reclassified as 65.

## Actual-sprite interactive previews

Role management's `预览本机原画逐帧动作` now sorts installed variants by how many **genuinely decodable original PNG actions** map to the application's 12 manual interaction categories. It is only the *preview order*; it does not rewrite saves, change active pets or imply likeness certification.

The `NativeFramePreviewDialog` shows 12 shortcuts (greeting, jump, observe, rest, sit, walk, run, talk, sleep, pat, climb, crawl). A button is available **only** if the selected creator-art version really provides an action mapped by exact name; a click selects and plays that installed PNG animation. Missing or broken actions stay disabled. Switching versions recalculates available interactions immediately; categories from different variants are never pooled into a fake per-character capability list. The existing full-frame scrubber, visual review controls and user export remain.

No motion is procedurally generated and no unauthorized sound sample is added.

## QA and release limitations

Offline regression runs Linux and Windows with Qt offscreen, Pillow and synthetic test sprites. It checks fallback retry bounds, no-consent behavior, invalid path handling, variant-specific button states and actual PNG playback selection.

Human review remains necessary for creator art identity, movement quality, physical Windows UI behavior and third-party licensing. **Do not publish a public Release with redistributed third-party sprites.** Draft owner-only delivery is separate from this source PR.
