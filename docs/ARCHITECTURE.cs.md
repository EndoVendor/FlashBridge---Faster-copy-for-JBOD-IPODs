# Architektura (česky)

[English](ARCHITECTURE.md)

## Datová cesta

```text
 GUI Windows (Tkinter, EN / CS)
     |
 Detekce Get-Disk + jen čtení MBR/FAT32
     |
 Plán: první karta + druhá karta + geometrie FAT32
     |
 Přezkoušení před mountem
     v
 ImDisk <-> localhost TCP proxy (náhodný port)
     |
 JoinedDisk: sekvenční spojení A + B
     |
 RawDevice A / RawDevice B
```

Jde o **sekvenční spojení bajtů**, nikoliv prokládání RAID 0. Logický offset do velikosti první karty patří prvnímu médiu; zbytek druhému. Virtuální svazek začíná až na FAT32 offsetu (bez MBR).

## Detekce

- Výběr omezuje kandidáty na USB/SD/MMC a vylučuje systémové, bootovací, offline a prázdné disky.
- Z MBR hledá začátky oddílů při délkách sektoru 512/1024/2048/4096 B; kontroluje FAT32 BPB, záložní boot sektor a FSInfo.
- Přijatelný hlavní oddíl musí přesahovat první médium a končit blízko součtu obou médií. Nejednoznačný výsledek se odmítá.
- Na začátku obou médií se čtou 4KiB fingerprinty; před zápisem proběhne znovu kontrola identity.
- Shoda počátků obou FAT slouží jako základní brána RW, **nikoli jako důkaz celkové konzistence FAT32**.

## Zápisová vrstva

ImDisk používá lokální TCP protokol `INFO`, `READ`, `WRITE`, `CLOSE`. Příkaz `INFO` oznamuje zarovnání I/O **512 B**; to je jiný parametr než logický sektor FAT32 nastavený při mountu `-S`.

Proxy poslouchá jen na **127.0.0.1**, pro každý mount na náhodném portu. Protokol ImDisk **neobsahuje autentizaci**, takže se smí používat jen na důvěryhodném PC. Port neforwarduj.

Velké zápisy se streamují po částech. Fyzické požadavky jsou zarovnány na 4 KiB (okrajové sektory se čtou, upraví a znovu zapíší). Následuje `FlushFileBuffers` a porovnání SHA-256 po zpětném čtení. Při chybě se nové zápisy zablokují a ImDisk dostane chybu místo úmyslného zavření spojení.

**Nejde o transakční filesystem.** Přerušení mezi aktualizacemi FAT, adresářů a dat může souborový systém poškodit. Nelze garantovat fyzickou trvalost zápisu na kartách s vlastní cache.

## Životní cyklus aplikace

`DETEKCE -> OVĚŘENÍ -> PROXY -> MOUNT -> PŘENOS -> ODPOJENÍ -> UKONČENÍ`

Pokud není bezpečně dokončeno standardní odpojení ImDisk `-d`, GUI ponechá otevřenou proxy i média. Neprovádí force-removal.

## Kopírování

Vestavěné kopírování analyzuje `Music` a `Audiobooks`, ignoruje existující cílové cesty a soubory nad limit FAT32 4 GiB. Nová data ukládá jako `.flashbridge.partial`; před přejmenováním je volitelně ověřuje SHA-256. Po přerušení lze pokračovat až po kontrole prefixu. Již existující, ale poškozený soubor s finálním názvem nástroj neopraví.

## Testy a logy

Syntetické testy pokrývají detekci, odmítnutí nejistoty, přechod hranice obou karet, velký TCP požadavek, chyby zápisu a kopírování. Windows CI **nenahrazuje test s fyzickými SD kartami**. Logy jsou v `%LOCALAPPDATA%\FlashBridge\logs` a mohou obsahovat jména souborů i cest — před zveřejněním je anonymizuj.


**v0.3.0:** Režim FAST vypouští readback bloků, nikoli flush. Neopravuje problém trvalého mazání FAT32 a negarantuje integritu po výpadku. Úspěšné zápisy jsou v logu vzorkované, chyby úplné.

**v0.3.2:** Nově se pro každé médium používá ověřená hlášená geometrie sektorů.
Při hodnotách 512/512 B se zapisuje přímo bez 4KiB RMW; při neznámé nebo
rozporné geometrii zůstává konzervativní cesta. Statistiky rozlišují
propustnost za skutečný čas, aktivní zápis, čtení a čekání na požadavky ImDisk.
Nedochází ke spekulativnímu zápisu ani k automatickému opakování zápisu po chybě.

### v0.3.3-rc1: rozhraní a EXE

Kopírovací průvodce Music/Audiobooks byl odstraněn z GUI; pomocná funkce v knihovně zůstává jen kvůli kompatibilitě/testům. Odpojování nadále používá bezpečný `imdisk -d`, kontroluje identitu virtuální jednotky, při odmítnutí ponechává proxy i fyzické disky a nabízí opakování po zavření správců souborů. `-D`/`-R` ani ukončování procesů se nepoužívá. Build Windows EXE je ve workflow `windows-exe.yml`; ImDisk zůstává vnější závislostí. Fyzický zápisový engine je beze změny.


### v0.3.3-rc2 — nedestruktivní inspektor a instalace závislosti

Modul flashbridge_inspector.py je oddělený od připojené ImDisk proxy. Vybraný PhysicalDrive otevírá pouze pro čtení a ukládá SHA-256 malých vzorků, kapacitu, hlášenou geometrii sektorů, MBR oddíly a omezené vzorky FAT32. Postup má tři části: otisk karty A → otisk karty B → samostatný otisk a porovnání sestaveného iPodu přes USB. Zkouší obě **lineární** pořadí, avšak ani shoda neprokazuje model adaptéru, bootovatelnost, úplnou integritu a nikdy nepovoluje RW.

Modul flashbridge_imdisk_setup.py může po výslovném souhlasu stáhnout instalační EXE z oficiálního HTTPS hostitele LTR Data do prázdné dočasné složky. Spuštění vyžaduje platný Authenticode podpis očekávaného vydavatele; PyInstaller EXE ovladač ImDisk neobsahuje.

Přesný postup a popisky ovládání viz [český návod](USER_GUIDE.cs.md) a [English guide](USER_GUIDE.md).
