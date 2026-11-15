# FlashBridge v0.3.0-alpha — Partially tested / experimental

- **FAST (GUI default):** write + flush only, **no immediate SHA-256 readback**.
- **VERIFIED:** previous write + flush + per-block readback + SHA-256.
- Policy fixed for entire mount; user explicitly authorizes physical RW.
- Fault latch retained, including device-specific WRITE/FLUSH/READBACK diagnostics.
- FAST samples successful I/O records and emits cumulative `IO_STATS`; GUI shows rolling 10s confirmed throughput.
- Retains 4KiB-edge read/modify/write optimization and touched-media-only flush.
- **Known unresolved:** permanent Shift+Delete behavior, zero-byte entries, prior WinError 55 device I/O failure.
- **No physical USB/SD hardware qualification; do not deploy over an active mount.**
- 33 synthetic unit/integration tests; Windows/Linux CI must pass before release completion.

Measured development hardware: ~35–36 ms/MiB physical write and ~28 ms/MiB readback. Removing readback may improve active throughput toward ~27–29 MiB/s on that reader. This is **not a guaranteed measured FAST throughput**.
