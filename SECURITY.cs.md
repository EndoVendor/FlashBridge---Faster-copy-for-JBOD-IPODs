# Bezpečnost a integrita dat

[English](SECURITY.md)

**Experimentální program s přístupem k fyzickému zápisu.** Chyba aplikace, ovladače, odpojení nebo výpadek napájení mohou nenávratně poškodit data. Kontrola MBR/FAT32 neověřuje všechny soubory ani alokační řetězce.

Aplikace nesbírá telemetrii ani neotevírá síťový port do internetu. TCP proxy ImDisku však na localhostu **nemá autentizaci** a jiné místní procesy mohou teoreticky komunikovat na přiděleném portu. Používej jen na důvěryhodném PC. Pro přístup k fyzickým diskům jsou potřeba práva správce.

## Ochrany

- Odmítne nejednoznačné pořadí médií a zjevně chráněné systémové disky.
- Před připojením znovu kontroluje velikosti, identifikační otisky a FAT32 geometrii.
- Nespouští formátování, CHKDSK, automatickou opravu, zrcadlení, testovací zápisy ani násilné odpojení.
- Oba RW režimy potvrdí zápis až po úspěšném požadavku na flush. **VERIFIED** navíc zpětně čte bloky a porovnává SHA-256; **FAST zpětné čtení nemá**. Po I/O chybě blokují další zápisy. Flush ani readback nejsou zárukou trvalého uložení při výpadku napájení.
- Neúplné odpojení ImDisku brání běžnému ukončení GUI.
- Existující cílové soubory nepřepisuje, ale ani automaticky neopravuje jejich případné poškození.

## Omezení

- FAT32 není transakční filesystem; rozpracovaný zápis může zanechat nesoulad metadat.
- Firmware flash a USB čteček může cacheovat zápisy; potvrzení tedy není absolutní zárukou trvalého uložení.
- Podporován je jen dvoukartový sekvenční FAT32 JBOD, nikoli libovolný RAID nebo více karet.
- Veřejná verze zatím není nezávisle ověřena na skutečném hardwaru.
- Logy mohou obsahovat názvy zařízení a osobní cesty; před zveřejněním je anonymizuj.

Chybu lze nahlásit v GitHub Issues spolu s **anonymizovanými logy**, verzemi OS, Pythonu a ImDisku. Nezveřejňuj obsah karet ani hudební soubory.

## Známý nevyřešený problém mazání

Na vývojovém JBOD některé smazané soubory po přerušených zápisových relacích zůstávaly v adresáři nebo měly nulovou délku. **Příčina není prokázaná ani opravená.** Nepoužívej experimentální RW pro jedinečná důležitá data.


**v0.3.0:** Režim FAST vypouští readback bloků, nikoli flush. Neopravuje problém trvalého mazání FAT32 a negarantuje integritu po výpadku. Úspěšné zápisy jsou v logu vzorkované, chyby úplné.
