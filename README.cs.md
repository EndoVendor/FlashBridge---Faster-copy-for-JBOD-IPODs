# FlashBridge — v0.3.3-rc2

> **Začni zde — v0.3.3-rc2 (částečně testovaný release candidate):** [Podrobný návod česky](docs/USER_GUIDE.cs.md) · [English guide](docs/USER_GUIDE.md) · [Bezpečnost](SECURITY.cs.md) · [Hardwarová přejímka](RELEASE_CHECKLIST.md)
>
> **Windows EXE:** [Trvalá stránka GitHub prerelease → Assets](https://github.com/martinfrolik-art/FlashBridge---Faster-copy-for-JBOD-IPODs/releases/tag/v0.3.3-rc2) (**FlashBridge-v0.3.3-rc2-Windows-x64-UNSIGNED.zip**; samostatné EXE a SHA256.txt jsou také dostupné). Rozbal ZIP a spusť **FlashBridge.exe** s právy správce; **Python ani CMD nejsou potřeba**. **ImDisk se instaluje zvlášť** tlačítkem **Nainstalovat ImDisk…**. **EXE není digitálně podepsané; jde o experimentální vydání bez záruky.**
>
> **Co umí:** inspekci **karty A, karty B a složeného iPodu** bez zápisu a připojení **existujícího podporovaného dvoukartového FAT32 JBOD**. **Neformátuje karty, nevytváří oddíly iPodu ani neinstaluje firmware.** Fyzický RW je experimentální — nepoužívej jedinou kopii důležitých dat.

**Správce dvoukartového FAT32 JBOD pro Windows** · [English](README.md) · [Poznámky k vydání](RELEASE_NOTES.md)

**Stav: TÉMĚŘ FINÁLNÍ RELEASE CANDIDATE — EXPERIMENTÁLNÍ SOFTWARE POSKYTOVANÝ „TAK, JAK JE“, BEZ ZÁRUKY.** Windows EXE bylo sestaveno a použito pro skutečné přenosy na vývojové konfiguraci; **nejde však o stabilní ani hardwarově certifikované vydání**. Inspektor, průvodce instalací ImDisku a řešení blokovaného odpojení ještě potřebují hardwarovou přejímku. FlashBridge neopravuje FAT32. **Nepoužívej jedinou kopii důležitých dat.** Fyzický zápisový engine je stejný jako v0.3.2-alpha. Viz [vyloučení záruk v licenci MIT](LICENSE) a [bezpečnostní omezení](SECURITY.cs.md).

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

Tlačítko **Nápověda a bezpečnost** otevře šest přehledů: Přehled, Postup, Odpojování, Bezpečnost, Diagnostika a Inspektor iPodu. Obsah je anglicky i česky a vysvětluje požadavky, postup, interpretaci režimů a řešení blokací.

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

## Nedestruktivní inspektor iPodu (novinka rc2)

**FlashBridge nikdy neformátuje SD karty ani na ně neinstaluje iPod firmware.** Máme pouze jediný referenční iPod 5/5.5G a jeden adaptér. Je to příliš malý vzorek pro univerzální postup inicializace. iPod může mít samostatnou partition pro firmware a partition FAT32; geometrie sektorů se může lišit.

1. Vyjmi první kartu, vlož ji samostatně do čtečky, vyber právě jeden fyzický disk a zvol **Uložit otisk vybrané karty (RO)**. Ulož JSON A. Totéž proveď s druhou kartou (JSON B). Neodsouhlasuj případnou nabídku Windows na inicializaci ani formátování.
2. Vrať obě karty do původního adaptéru a iPodu. Připoj iPod přes USB v diskovém režimu, obnov seznam a identifikuj jeho fyzický disk podle kapacity a označení.
3. Vyber iPod disk, zvol **Porovnat disk iPodu (RO)**, načti dva uložené otisky. Aplikace ověří vzorky z obou možných pořadí při lineárním spojení.
4. Výsledek obsahuje shody a neshody malých SHA-256 vzorků a rozdíl kapacit. **Ani úplná shoda nezaručuje bootovatelnost, úplnou integritu ani univerzální podporu adaptéru.** Neshoda může znamenat jinou geometrii, změněná data či jiný způsob mapování adaptéru; v takovém případě se nic nezapisuje a pořadí se nehádá.

Inspektor v protokolu také samostatně zachytí skutečně viděnou kapacitu, MBR/partition mapu, případné FAT32 struktury a vzorkované hashe samotného iPodu. Neprovádí formát, opravu, klonování, mount ani žádný zápis. Jeho report nikdy sám nepovoluje RW v běžné části aplikace. Uložené JSONy obsahují metadata a hashe, ne obsah hudby.

## Volitelná instalace ImDisk

Tlačítko **Nainstalovat ImDisk…** po potvrzení stáhne instalátor z `static.ltr-data.se` přes HTTPS do nové prázdné složky a zkontroluje digitální podpis vydavatele prostřednictvím Windows Authenticode. Pokud podpis nelze ověřit, instalátor se **nespustí**; uživatel může otevřít oficiální web a nainstalovat ovladač ručně. Samotnou instalaci a případné UAC musí uživatel výslovně potvrdit. ImDisk má na moderních Windows známá omezení.

Oficiální vydavatel: https://www.ltr-data.se/opencode.html#ImDisk
