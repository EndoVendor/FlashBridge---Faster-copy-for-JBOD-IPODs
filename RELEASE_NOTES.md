# FlashBridge v0.3.1-alpha — Partially tested / experimental

- **FAST (GUI default):** write + flush only, **no immediate SHA-256 readback**.
- **VERIFIED:** previous write + flush + per-block readback + SHA-256.
- Policy fixed for entire mount; user explicitly authorizes physical RW.
- Fault latch retained, including device-specific WRITE/FLUSH/READBACK diagnostics.
- FAST samples successful I/O records and emits cumulative `IO_STATS`; GUI shows rolling 10s confirmed throughput.
- Fuses two edge-preserving 4KiB RMW boundaries plus interior into one physical WRITE for misaligned requests; keeps touched-media-only flush.
- Adds physical write call/byte and RMW read call/byte counts to logs. Actual performance remains unmeasured.
- **Known unresolved:** permanent Shift+Delete behavior, zero-byte entries, prior WinError 55 device I/O failure.
- **No physical USB/SD hardware qualification; do not deploy over an active mount.**
- 40 synthetic unit/integration tests; Windows/Linux CI must pass before release completion.

Measured development hardware: ~35–36 ms/MiB physical write and ~28 ms/MiB readback. Previous Fast measurements were ~25 MB/s, but v0.3.1 has not been measured on physical SD media; no additional speedup claim is made. This is **not a guaranteed measured FAST throughput**.
