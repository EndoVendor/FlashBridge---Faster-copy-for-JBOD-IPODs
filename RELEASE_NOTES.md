# FlashBridge v0.2.1-alpha — Partially tested

**Experimental source preview, not hardware-qualified.**

- Reduced huge read-modify-write overhead for misaligned FAT32 layouts: up to two 4KiB edge pre-reads, direct aligned interior writes.
- Reduced redundant `FlushFileBuffers`: only media touched by each write are flushed.
- Full per-write flush plus SHA-256 readback remains enabled.
- Added phase timing (`receive`, `physical write`, `flush`, `readback`) and touched-media evidence to `IO_END` diagnostic logs.
- **Open critical issue:** deletions have sometimes left files present or zero-length after prior interrupted writes; the cause has not been proven or fixed. RW is unsuitable for critical or irreplaceable data.
- No sustained Windows/USB throughput gain has been measured or guaranteed.

Synthetic tests only; never interpret success as certification of physical cards.
