# Contributing / Spolupráce

**English is the project's primary maintenance language.** Czech GUI strings and documentation must be kept in sync with the English source. Pull requests, commit messages and issue titles should preferably be in English; Czech reports are welcome.

## Developer workflow

1. Use Python 3.10+ on a machine where a Tkinter build is available; no third-party pip packages are required.
2. Run `python -m unittest discover -s tests -v` and `python -m py_compile flashbridge_core.py flashbridge_gui.py flashbridge_gui.pyw flashbridge_i18n.py` before submitting.
3. Add every new GUI string to both dictionaries in `flashbridge_i18n.py`. English is canonical. Unit tests enforce matching keys and placeholders.
4. Add synthetic media tests for boundary, protocol, error and recovery changes. **Never require physical media or raw writes in CI.**
5. Keep Windows ImDisk-specific operations isolated; test them on disposable, non-personal media only after synthetic tests pass.
6. Keep docs/README and docs/ARCHITECTURE in both languages in sync.

Performance PRs must include a repeatable benchmark methodology, hardware and filesystem details; never claim a universal speedup from a single setup. Avoid changing write semantics without test cases for partial 4KiB sectors, FAT metadata writes, injected I/O errors, large proxy commands, and unmount.

**Česky:** Výchozí jazyk je angličtina, čeština je plnohodnotná lokalizace. Všechny nové UI řetězce přidej v obou jazykových tabulkách, projdi syntetické testy a nikdy při CI neprováděj zápisy na fyzické disky. Měření výkonu musí uvádět hardware a metodiku.
