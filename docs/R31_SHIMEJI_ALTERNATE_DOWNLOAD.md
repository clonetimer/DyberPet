# R31: 23 failed local Shimeji source attempts — pinned fallback transport

## Why this repair is prioritized

The user's real R28 installation log recorded 41 successfully installed original-art roles and 28 failed characters. A provider-level audit found that **all 16 NanoPet Shimeji attempts** and **all 7 standard Shimeji attempts** failed on that PC. These are 23 source attempts, NOT 23 distinct missing characters. Both providers share the same Python download function for hundreds of original PNGs. Other sources achieved partial success, so treating all pinned creator art as nonexistent would be wrong.

[Windows real frozen EXE test (R30)](https://github.com/clonetimer/DyberPet/actions/runs/40659954766) downloaded and installed Albedo, Diona, Fischl, Baizhu and control Amber successfully in an actual PyInstaller EXE. Thus at least several original sources and the Windows frozen package work under GitHub-hosted conditions. The original user's per-source JSON exception report is still required to distinguish local proxy/TLS/timeout/HTTP issues.

## R31 change

- Keep every NanoPet and standard Shimeji immutable Git source URL, pinned Git blob SHA-1, source file length, visual QA and personal-use consent requirements unchanged.
- If direct GitHub Raw fails with an HTTP or network error, try the SAME owner/repo/40-char pinned Git commit/path through GitHub Media and, if still inaccessible, HTTPS jsDelivr. Only explicit allowlisted CDN redirects are accepted. Never fall back on malformed URL, changed PNG bytes, size mismatch, unsafe redirect, invalid frame, or hash mismatch.
- A successful alternate endpoint is remembered only in memory for the same immutable repository+commit. Subsequent PNGs in that original role avoid repeatedly calling a known blocked Raw endpoint; there is no persistent global proxy config.
- Both Windows Python/RustHybrid and Linux frozen builds explicitly import the transport module. No original creator art is added to hosted binaries or committed to public source.
- In the R30 Windows package, Retry-Failed-Roles.cmd can retry only the failures from the old report, preserving 41 successful roles.

## Real integration evidence

[Windows R31 real upstream original art test](https://github.com/clonetimer/DyberPet/actions/runs/40661385536) intentionally blocked raw.githubusercontent.com:
- Original NanoPet Albedo: 46 original source PNGs checked by existing immutable Git blob hashes, 15 native actions installed; structural motion audit still has pending issues, NOT visually approved.
- Independent Shimeji Albedo: 27 original source PNG action images, 8 native actions installed; original pixel bytes preserved.
- No original picture ZIP, PNG, voice, or private role directory was uploaded as a GitHub Actions artifact.

This does **not** prove every previously failed Shimeji author link or the specific user's region/PC will work. Missing or invalid source frames must still fail closed, and 54 Genshin templates still lack fixed original art sources. After a new candidate build, re-run failed-only installation and review the new JSON report before claiming recovery.
