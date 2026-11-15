# FlashBridge — v0.3.3-rc1

**Správce dvoukartového FAT32 JBOD pro Windows** · [English](README.md) · [Poznámky k vydání](RELEASE_NOTES.md)

**Klasifikace: ČÁSTEČNĚ TESTOVANÝ KANDIDÁT NA VYDÁNÍ.** FlashBridge neopravuje souborový systém a experimentální přímý zápis neprošel nezávislou hardwarovou přejímkou. **Není vhodný pro jedinou kopii důležitých dat.** V této verzi jsou nové, na skutečných Windows dosud neověřené úpravy GUI a chybového postupu odpojení; fyzický I/O engine zůstává z v0.3.2-alpha.

## Co aplikace dělá

FlashBridge zpřístupní **existující navazující (concatenated) FAT32 svazek na dvou kartách** jako jeden virtuální disk Windows. **Nevytváří JBOD znovu, neformátuje, neupravuje tabulky oddílů, neinstaluje firmware iPodu ani nezapisuje jako RAID0.** U flashově upraveného iPodu může obejít pomalý přenos přes USB rozhraní iPodu pomocí dvou samostatných čteček.

Pořadí karet určuje z MBR, BPB FAT32, záložního boot sektoru, FSInfo a počátků FAT tabulek. Neznámá nebo nejednoznačná dvojice se neodhadne. Před připojením se znovu ověřuje identita zařízení, pořadí a geometrie svazku.

## Požadavky

- Windows 10/11 x64, práva správce, **dvě samostatné USB čtečky** a dvě původní karty tvořící podporované JBOD FAT32.
- Samostatná instalace **ImDisk Virtual Disk Driver** včetně dostupného `imdisk.exe` v PATH. [Oficiální ImDisk](https://www.ltr-data.se/opencode.html/#ImDisk). FlashBridge EXE **neobsahuje** ovladač ImDisk ani jeho instalátor.
- Před použitím experimentálního RW režimu spolehlivá záloha. FAT32 nemá žurnál.
- V uživatelské distribuci **`FlashBridge.exe`**; ke spuštění není třeba Python, CMD ani PowerShell. EXE samo vyvolá požadavek UAC. Program **není digitálně podepsaný** a může zobrazit varování SmartScreen.

## Doporučený postup

1. Obě původní JBOD karty vlož do samostatných čteček. Pokud Windows nabídnou formátování, **odmítni**.
2. Nainstaluj samostatně ImDisk. Spusť **`FlashBridge.exe`** a schval UAC.
3. Klikni **Najít JBOD automaticky**. Zkontroluj důkazy, pořadí **PRVNÍ/DRUHÁ** a geometrii FAT32. Nejasnosti nepřekonávej ručním odhadem.
4. Vyber volné písmeno, obvykle `R:`. Začni **Připojit RO**, což umožní prohlížet bez zápisu.
5. Jen pokud potřebuješ měnit soubory, ověř zálohu, vyber **FAST** nebo **VERIFIED**, použij **Připojit RW** a potvrď ochrannou frázi. Samotné soubory kopíruj Průzkumníkem/Total Commanderem. **Volitelný průvodce kopírováním Music/Audiobooks byl z GUI odstraněn.**
6. Dokonči kopírování a zavři **všechna okna** Průzkumníka a Total Commanderu, i když zrovna ukazují jinou jednotku, například `C:`. Zavři také dialogy pro práci se soubory, terminály a další programy, které mohly zjišťovat disky.
7. Klikni **Bezpečně odpojit**. Pokud ImDisk odmítne odebrání, nech karty připojené, zavři zbývající okna a klikni **Opakovat**. Počkej na potvrzené odebrání virtuálního disku.
8. Teprve pak bezpečně vysuň obě fyzické USB čtečky ve Windows a vrať karty do iPodu.

## Proč bezpečné odpojení někdy nejde

Normální odpojení používá příkaz `imdisk.exe -d -m R:` (s aktuálním písmenem). V testu odmítalo odebrání, pokud zůstalo otevřené **jakékoliv okno Průzkumníka nebo Commanderu, dokonce i na C:, nikoli R:**. Není tím prokázáno, že každé takové okno vždy drží otevřenou jednotku R:, ale jde o reálný problém pozorovaný na Windows.

Nově FlashBridge zobrazí srozumitelné vysvětlení, zapíše událost `UNMOUNT_BUSY`, **neukončí proxy ani přístup k médiím** a nabídne **Opakovat**. Nezabíjí procesy, nerestartuje Explorer a nepoužívá vynucené `imdisk -D` či nouzové `-R`. Mohly by přerušit aktualizaci FAT32 a poškodit data. Pokud se odpojení stále nedaří, zachovej logy a zjisti proces držící jednotku. **Nikdy nevyjímej kartu, dokud ImDisk stále eviduje virtuální svazek.**

## Režimy a bezpečnost

| Režim | Funkce | Omezení |
|---|---|---|
| RO | Virtuální disk jen pro čtení | Vhodné pro kontrolu, nikoli důkaz zdraví FAT32 |
| RW FAST | Zápis na fyzická média a `FlushFileBuffers` před potvrzením každého zápisového požadavku | Rychlejší, bez zpětné kontroly dat; firmware může používat cache |
| RW VERIFIED | Totéž + SHA-256 porovnání zpětně přečtených bloků | Pomalejší, stále bez záruky proti výpadku napájení |

**Známé nevyřešené chyby:** Trvalé mazání (`Shift+Delete`) někdy ponechávalo nulové soubory nebo nevracelo místo. V dřívějších relacích se vyskytl `WinError 55`. Nespoléhej na bezpečnost mazání na RW svazku. Nástroj neprovádí opravy CHKDSK, formátování, automatické opravy, násilné odpojování, syntetické zápisy ani write-behind cache.

## Nápověda a diagnostika

Tlačítko **Nápověda a bezpečnost** otevře pět přehledů: Přehled, Postup, Odpojování, Bezpečnost a Diagnostika. Obsah je anglicky i česky a vysvětluje požadavky, postup, interpretaci režimů a řešení blokací.

Logy: `%LOCALAPPDATA%\FlashBridge\logs\` (`.log`, `.jsonl`). V GUI je tlačítko **Otevřít složku logů**. `IO_STATS` obsahuje souhrnné bajty i rozklad aktivního zápisu, skutečně uplynulého času, čekání, čtení a fyzických operací. Ve FAST režimu jsou jednotlivé úspěšné `IO_END` jen vzorkované; nesčítej je jako všechny zápisy.

Při testu 15. 11. 2026 šlo běžně o 27–30 MiB/s s občasnými špičkami 40–50+ MiB/s. Výkon závisí na kartách, čtečkách a zátěži; **nejde o záruku**. Experiment s ventilátorem neprokázal jednoznačně tepelnou příčinu kolísání.

**Soukromí:** logy mohou obsahovat názvy disků, cesty a soubory. Před zveřejněním je zkontroluj a případně anonymizuj.

## Windows EXE, zdrojový kód a přejímka

Koncová distribuce má obsahovat **`FlashBridge.exe`**, nikoli `.cmd`. Workflow `.github/workflows/windows-exe.yml` sestavuje EXE pomocí PyInstaller na Windows runneru, přikládá README, licenci a poznámky k vydání a zveřejňuje výsledek jako GitHub Actions artifact. EXE vyžaduje UAC, je bez konzole a **není podepsaný**.

Vývojář může na Windows sestavení opakovat instalací `pyinstaller==6.22.3` a příkazem `python -m PyInstaller --clean --noconfirm --onefile --windowed --uac-admin --name FlashBridge --icon assets\flashbridge.ico flashbridge_gui.pyw`. PyInstaller musí pro Windows EXE běžet **na Windows**. Linuxový test nevytvoří ani neotestuje funkční Windows EXE.

Testy: `python -m unittest discover -s tests -v` a `python -m py_compile flashbridge_core.py flashbridge_gui.py flashbridge_i18n.py`. Syntetické testy **nenahrazují** integrační zkoušky na skutečných kartách. Původní pomocné kopírovací funkce zůstaly ve zdrojovém `flashbridge_core.py` kvůli kompatibilitě a testům, **nejsou dostupné v GUI**.

Podporováno: jednoznačně identifikovaný dvoukartový concatenated FAT32, RO/RW proxy ImDisk, EN/CS GUI, diagnostika. Nepodporováno: obecné JBOD, exFAT, RAID striping, 3+ karet, certifikace stavu médií, oprava souborového systému a instalace bootloaderu iPodu.

Před veřejným stabilním vydáním je nutno ověřit sestavení a spuštění EXE na Windows 10/11, přítomnost ImDisk, běžné i blokované odpojení (při otevřeném Průzkumníku), RO čtení a **RW jen na postradatelných testovacích kartách** včetně ověření souborů a zotavení po výpadku.

Licence MIT ([LICENSE](LICENSE)). ImDisk se instaluje zvlášť a podléhá vlastní licenci. Viz [Bezpečnost](SECURITY.cs.md), [Architektura](docs/ARCHITECTURE.cs.md) a [Přejímací seznam](RELEASE_CHECKLIST.md).
