# FlashBridge

**Automatická identifikace dvoukartového FAT32 JBOD, připojování a monitoring ve Windows.**  
[English — hlavní dokumentace](README.md) | **Čeština**

> **Stav: PARTIALLY TESTED (ČÁSTEČNĚ TESTOVÁNO) · v0.3.0-alpha · experimentální zdrojová verze.** Detekce pouze pro čtení byla v původním vývojovém scénáři použita se skutečnými kartami. Tato veřejná verze prošla simulovanými testy, **nikoliv nezávislou certifikací kombinace Windows/ImDisk/USB**. Přímý fyzický zápis může poškodit souborový systém. Kontrola boot sektoru není zárukou integrity souborů.

FlashBridge je desktopová aplikace s GUI Tkinter. Z dvojice flash médií skládá **sekvenční (konkatenovaný)** virtuální disk bez vytváření jeho obrazu. Pořadí určuje podle obsahu médií, nikoliv značky, kapacity nebo čísla `PhysicalDrive`. Existující FAT32 pak připojuje přes externí [ovladač ImDisk](https://www.ltr-data.se/opencode.html/#ImDisk) a lokální TCP proxy.

Vznikl kvůli pomalým přenosům přes USB rozhraní iPodu. Přímé čtečky toto úzké hrdlo mohou obejít, **ale vyšší rychlost není zaručena pro každý hardware**.

## Podporované funkce a hranice

| Funkce | Stav |
|---|---|
| Windows 10/11, Python 3.10+, GUI Tkinter | Cílové prostředí; integrace potřebuje další ověření na hardwaru |
| Dvě USB/SD flash média různých výrobců a kapacit | Ano, pouze při jednoznačné identifikaci |
| Sekvenční FAT32 svazek překračující první médium | Podporovaný návrh |
| Automatické pořadí dle MBR, FAT32, záložního sektoru a FSInfo | Implementováno, při nejistotě zablokuje zápis |
| Připojení jen pro čtení přes ImDisk | Implementováno |
| RW připojení, potvrzení zápisu a diagnostické logy | **Experimentální** |
| Doplnění chybějících Music/Audiobooks včetně SHA-256 | Implementováno, nepřepisuje existující soubory |
| Libovolný RAID/JBOD, RAID 0, tři a více karet, exFAT | **Nepodporováno** |
| Úplná diagnostika fyzického zdraví karet či automatická oprava FAT | **Nepodporováno** |

*Flash-agnostic* znamená nezávislost na značce, kapacitě a číslování disků. Neznamená možnost bezpečně odhadnout neznámý layout libovolného pole.

## Známý problém: mazání v RW režimu

**Nevyřešeno a pozorováno na vývojovém JBOD:** některé smazané soubory
zůstávaly v adresáři nebo měly nulovou velikost. **Oprava zatím nebyla potvrzena.**
Příčinou mohou být přerušené aktualizace FAT či adresářů při selhání proxy,
ale není to prokázané. FlashBridge nemá transakční obnovu ani plnohodnotnou
kontrolu FAT. **Nepoužívej RW na jedinou kopii důležitých dat a nespoléhej na
správné uvolnění místa mazáním.** Při výskytu ukonči zápisy a bezpečně odpoj
svazek; opravy bez diagnózy nespouštěj.

## Zrychlení zápisu v0.3.0-alpha: FAST a VERIFIED

**Před připojením RW** vyber způsob zápisu; za provozu přepnutí není možné.

| Režim | Fyzický zápis | FlushFileBuffers | Readback + SHA-256 po bloku |
|---|---|---|---|
| **FAST (výchozí)** | Ano | Po každém požadavku, jen dotčené karty | **Ne** |
| VERIFIED | Ano | Po každém požadavku, jen dotčené karty | Ano, celý požadavek |

**FAST nekontroluje obsah zapsaných bloků.** Windows dostane potvrzení až
po dokončení zápisu a návratu `FlushFileBuffers`, ale ani úspěšný flush
není absolutní zárukou zachování dat při výpadku USB nebo napájení.
FAT32 nemá žurnál a přerušený zápis metadat může svazek poškodit v obou režimech.

Na vývojovém hardwaru bylo naměřeno zhruba **35–36 ms/MiB na zápis** a
**28 ms/MiB na readback**. Vypuštění readbacku dává teoretický strop
**27–29 MiB/s při aktivních zápisech**, nikoli garantovanou rychlost
kopírování. Prvních 200 MB/s v Exploreru mohlo být zásadně ovlivněno cache.
Sekvenční JBOD nezapisuje automaticky paralelně na dvě karty.

Zůstává optimalizace původního 2KiB posunu: předčítají se jen krajní neúplné
4KiB bloky, nikoli celý 1MiB blok. Synchronizuje se jen dotčená karta,
obě pouze při přechodu přes jejich hranici.

FAST omezuje objem běžných logů, ale chyby fyzického zápisu a flush eviduje
podrobně. Každých 64 požadavků zapisuje `IO_STATS` se souhrnnými hodnotami.
GUI ukazuje průběžnou rychlost za posledních **10 sekund**, nikoli rychlost
jediného zápisového bloku. Plná diagnostika požadavků zůstává v režimu VERIFIED.

**Nevyřešené mazání:** `Shift+Delete` může zanechávat položky nebo nulové
soubory; běžný `Delete` může pouze přesouvat do Koše. Režim FAST toto neopravuje.

## Instalace a použití

1. Rozbal ZIP například do `C:\FlashBridge`; nespouštěj program přímo z archivu.
2. Nainstaluj Python 3.10+ s Tkinter a originální ovladač a příkazový nástroj ImDisk. **ImDisk není součástí balíčku.**
3. Spusť `START_FlashBridge.cmd` (vyžádá práva správce). Alternativně spusť jako správce `python flashbridge_gui.pyw`.
4. Vpravo nahoře přepni **Čeština** nebo **English** (výchozí).
5. Nech automaticky rozpoznat **jedinou jednoznačnou dvojici**. Zkontroluj doložené pořadí. Pokud automatika dvojici nedokáže prokázat, vyber dvě média a nech je explicitně ověřit.
6. Vyber volné písmeno. Před RW zvol **FAST** (výchozí, bez readbacku) nebo **VERIFIED** (se zpětným ověřováním). **Připojit RW (experimentální)** vyžaduje výslovné potvrzení zápisu na obě karty; **Připojit RO** nezapisuje.
7. Chceš-li doplnit hudbu, vyber zdroj obsahující `Music` a `Audiobooks`, použij **Zjistit chybějící** a zkontroluj volné místo. Potom **Kopírovat jen chybějící**. Existující cesty se nepřepisují.
8. Zavři otevřené soubory a zvol **Bezpečně odpojit**. Počkej, až zařízení zmizí z ImDisku. Fyzické čtečky odeber bezpečně přes Windows.

### Bezpečnost

- Detekce **neformátuje, neopravuje FAT, nepouští CHKDSK, nemaže, nezrcadlí ani nezapisuje testovací soubory**.
- Před připojením opět ověřuje identitu, kapacitu a geometrii; systémové/bootovací disky vylučuje.
- Nejednoznačné pořadí a neshoda základních FAT hlaviček RW blokují. Nejde ale o kompletní kontrolu konzistence FAT32.
- Pro fyzické zápisy používá 4KiB zarovnání s read-modify-write a velké požadavky zpracovává po částech. Po chybě zablokuje další zápisy a předá chybu ImDisku.
- V obou RW režimech požaduje `FlushFileBuffers`; **pouze VERIFIED** provádí plný SHA-256 readback. Firmware čtečky či flash může mít vlastní cache; **nejde o záruku trvalého uložení po náhlém výpadku**.
- Existující soubory se přeskakují **podle cesty** — již existující, ale poškozený či nedokončený soubor se automaticky neopraví. Soubory nad 4 GiB nelze uložit na FAT32.

### Logování a soukromí

Logy se ukládají do `%LOCALAPPDATA%\FlashBridge\logs\` jako `.log` a rotovaný `.jsonl`. Obsahují stav, názvy zařízení, offsety, délky operací a diagnostiku chyb. **Mohou obsahovat úplné cesty a názvy skladeb** — před sdílením na GitHubu je zkontroluj a anonymizuj. Nezveřejňuj obrazy karet ani hudební soubory.

### Testy

```powershell
python -m unittest discover -s tests -v
python -m py_compile flashbridge_core.py flashbridge_gui.py flashbridge_gui.pyw flashbridge_i18n.py
```

CI testuje syntetická média na Windows a Linuxu. Neověřuje reálné přenosové rychlosti ani fyzickou bezpečnost. Podrobnosti: [architektura](docs/ARCHITECTURE.cs.md), [bezpečnost](SECURITY.cs.md) a [spolupráce](CONTRIBUTING.md).

**Licence:** [MIT](LICENSE) pro zdrojový kód FlashBridge. Windows a ImDisk jsou samostatné produkty s vlastními licencemi. Balíček neobsahuje podepsaný `.exe` a zatím nejde o produkčně certifikovanou aplikaci.


**Klasifikace vydání: Partially tested.** V lokálním prostředí prošlo 33 syntetických testů. Automatická detekce dvojice reálných karet byla ověřena ve vývojovém scénáři. Publikovaná alfa verze nemá nezávislé ověření kombinace Windows/ImDisk/USB a fyzické RW zůstává experimentální. Bez záruky zvýšení výkonu nebo bezpečnosti dat.

### Analýza rychlosti (pouze čtení logu)

Po skončení relace spusť:

```powershell
python tools/profile_report.py "$env:LOCALAPPDATA\FlashBridge\logs\TVUJ_SOUBOR.jsonl"
```

Režim FAST vzorkuje běžné `IO_END`; celkový počet bajtů a fáze obsahuje
`IO_STATS`. Počet vzorkovaných zápisů není celkový počet zápisů. Ve FAST
je `readback_ms` nulový; VERIFIED měří plné zpětné čtení. Ani jeden režim
nepotvrzuje zápisy před dokončením požadovaného flush.
