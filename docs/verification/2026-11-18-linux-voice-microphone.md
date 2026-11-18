# DyberPet Linux voice and microphone acceptance

Current branch: `feat/ai-companion-runtime-20261117`  
PulseAudio integration head: `1ec0e0197dbd0d7c3324302b230db47cd1cf63fe`

## Linux speech backend

- eSpeak NG CLI 1.51 is used by the cancellable Linux playback backend.
- Speech text is sent through stdin, never shell text or command-line arguments.
- Stop and the shared timeout terminate the worker-owned child process; a nonzero exit is not successful playback.
- 131 real pyttsx3-enumerated voice IDs previously passed CLI WAV synthesis compatibility, including Mandarin and Cantonese voice IDs.

## Microphone sample-rate negotiation

- Prefer 16 kHz.
- If rejected, try the selected device's reported default sample rate, then a bounded set including 192, 96, 88.2, 48, 44.1, 32, 22.05 and 8 kHz.
- Return and display the actual opened sample rate; calculate frame count and level metrics using that rate.
- Unit tests cover 16 kHz rejection followed by 96 kHz device-default success and the all-candidates-rejected path.

## PulseAudio integration evidence

Workflow: [Linux X11 acceptance and portable candidate](https://github.com/clonetimer/DyberPet/actions/runs/44286039855)

The job installed PulseAudio and pulseaudio-utils, started a daemon, created a named 48 kHz null source, and set it as the default source. It then ran the product's own `probe_microphone` through sounddevice/PortAudio against an exact PulseAudio-backed input device.

- Test: `test_selected_pulse_input_source_can_be_opened_and_captured`
- Result: **1/1 PASS, 0.862 seconds**
- The test did not silently fall back to a different input device.
- The same Linux source X11 job continued through real Qt/XCB UI and application smoke checks successfully.

This proves the PulseAudio server → PortAudio → DyberPet capture path for a virtual null source. It does not prove a physical microphone, ALSA hardware, native PipeWire host API, permission prompts, Vosk accuracy or long-duration device stability.

## Remaining real-device acceptance

1. Physical microphone open/capture on the user's Linux device and actual ALSA/PulseAudio/PipeWire setup.
2. Verify input permissions and device switching after unplug/replug.
3. Run Vosk recognition on known Mandarin speech and inspect transcript quality.
4. Listen to eSpeak NG output through the physical speaker/headset and assess Mandarin pronunciation.
5. Verify repeated stop/restart and long-duration half-duplex voice conversation.



## PipeWire PulseAudio-compatibility integration

A second Linux integration session is added separately from the native PulseAudio test. CI first stops the PulseAudio daemon, starts `pipewire`, `wireplumber` and `pipewire-pulse` inside an isolated D-Bus session and `XDG_RUNTIME_DIR`, creates a named 48 kHz null sink and selects its `.monitor` source via the PulseAudio compatibility protocol, then runs the same product `probe_microphone` PortAudio capture test with exact host/device matching.

This specifically validates the PipeWire-provided PulseAudio compatibility server. It does not claim native PipeWire PortAudio host API support or physical ALSA hardware support. Final status must be taken from the Linux workflow for the new PR head.


## ALSA host API integration

Linux X11 CI adds a dedicated ALSA null PCM test. It writes a temporary ALSA configuration (outside the repository and user home) mapping the default PCM to the ALSA null plugin, sets `ALSA_CONFIG_PATH`, then requires PortAudio to expose an ALSA input host and opens the selected device through the product `probe_microphone` implementation. The test reads PCM and verifies stream cleanup. It does not fall back to PulseAudio and fails if the ALSA host input is unavailable.

This verifies the PortAudio ALSA host API against a virtual null PCM. It does not certify physical ALSA hardware, mixer controls, device permissions or hotplug behavior.

## CI dependency installation bounds

The Linux source and frozen jobs now use apt Acquire retry and HTTP/HTTPS timeout options plus an 8-minute outer timeout for package index and system package installation. This makes mirror/network stalls fail within a bounded interval rather than holding the Linux acceptance workflow indefinitely.


## Exact-source selection hardening

The PulseAudio integration test now reads `pactl get-default-source` and requires a unique exact-name match in the PortAudio PulseAudio host catalog before opening the input. This prevents a machine with multiple physical, monitor or virtual sources from accidentally testing the wrong device. PipeWire's compatibility test uses a `module-null-sink` monitor source and selects its exact default-source name. The integration test fails on missing or ambiguous source identity and never falls back to the first enumerated input.


## PipeWire module compatibility correction

The first PipeWire CI attempt failed before PortAudio capture: `pipewire-pulse` returned `Failure: No such entity` for PulseAudio's `module-null-source`. This is a compatibility-module availability difference, not an input-stream failure. The test now creates `module-null-sink` (supported by pipewire-pulse) and selects its `.monitor` source. Both PulseAudio and PipeWire tests now read `pactl get-default-source` and require a unique exact-name match in the PortAudio catalog before calling the product capture function. The corrected result must be read from the new head's Linux CI.


## PulseAudio source identity vs PortAudio device identity

A failed run on head `f59dd6f` showed that `pactl get-default-source` correctly returned the test source name, while the PortAudio PulseAudio Host API exposed its own default-input device name rather than the server source string. These are separate naming namespaces. The corrected test now:

1. Requires `pactl get-default-source` to equal the exact CI source under test.
2. Reads the PortAudio default input index and confirms its Host API is PulseAudio.
3. Uses that exact PortAudio device name + Host API identity with the product `probe_microphone` function.

This avoids both false negatives from comparing unlike names and false positives from arbitrarily selecting any PulseAudio-capable device. The PipeWire run uses the null-sink monitor source as its expected default.
