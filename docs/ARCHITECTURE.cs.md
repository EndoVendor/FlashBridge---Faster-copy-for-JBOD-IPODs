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
