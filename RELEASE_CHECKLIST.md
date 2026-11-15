# Release checklist / Přejímka před zveřejněním

- [x] English README + Czech equivalent
- [x] GUI language selector (English default, Czech optional)
- [x] Synthetic test suite and CI workflow
- [x] MIT license, contribution rules, security limitations, issue template
- [x] No user-specific disk hashes, media files, serials, or local user paths in repository
- [x] Version labeled **Partially tested / alpha**, physical write capability labeled experimental
- [ ] Independent Windows 10 and Windows 11 integration validation with ImDisk
- [ ] Disposable hardware media validation with injected unplug / power-loss scenarios
- [ ] Benchmark comparison documented across multiple card readers
- [ ] External code/security review for physical-device write path
- [ ] Signed Windows executable and installer (optional; not bundled)

**Do not publish v1.0 or advertise production-safe raw writing until the unchecked items are addressed.**

**Česky:** Zdrojový repozitář a dokumentace jsou připravené. Ostrá RW funkce nemá nezávislou hardwarovou přejímku; dokud neproběhne, vydání musí zůstat experimentální alfa verzí.
