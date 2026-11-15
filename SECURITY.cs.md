# Bezpečnost a integrita dat

[English](SECURITY.md)

**ZNÁMÉ OMEZENÍ — Shift+Delete (test vlastníka, 15. 11. 2026):** Po trvalém mazání během vývojových RW relací se několik souborů zobrazovalo jako nulových nebo neodstranitelných a Windows nalezly chyby alokačních řetězců FAT32. Po připojení sestaveného iPodu přímo přes USB je `chkdsk D: /f` opravil; následné `chkdsk D:` prošlo **bez chyb**. U některých záznamů se opět objevila běžná velikost a šly smazat; běžné **Delete bez Shift** v tomto případě fungovalo. V referenčním testu šlo o **opravitelný problém**, nikoli ztrátu celé knihovny. Přesná příčina **není prokázána** (dříve se objevil také USB/proxy `WinError 55`) a běžné Delete není plošně certifikované. **Nepoužívej Shift+Delete; pokud potřebuješ mazat, použij obyčejné Delete, měj zálohy a bezpečně odpojuj.** Experimentální RW je na vlastní riziko. [Technická závada #1](https://github.com/martinfrolik-art/FlashBridge---Faster-copy-for-JBOD-IPODs/issues/1).

**Funkční prototyp v1.0.0 potvrzený vlastníkem na jednom upraveném iPodu; experimentální program s přístupem k fyzickému zápisu, poskytovaný TAK, JAK JE, bez záruky.** Chyba aplikace, ovladače, odpojení nebo výpadek napájení mohou nenávratně poškodit data. Kontrola MBR/FAT32 neověřuje všechny soubory ani alokační řetězce.

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

**Pozorování v referenčním testu:** Po Shift+Delete při experimentálním zápisu několik souborů zůstalo jako nulových či neodstranitelných. Windows CHKDSK nalezl chyby FAT32, opravil je pomocí `chkdsk /f` na sestaveném iPodu a následná kontrola byla čistá; běžné Delete fungovalo. Nebyla pozorována ztráta celé knihovny, úplné hashe všech FLAC však nejsou ověřeny. **Nepoužívej Shift+Delete.** Běžné Delete není plošně garantované a přesná příčina není prokázána; zachovávej zálohy.


**v0.3.0:** Režim FAST vypouští readback bloků, nikoli flush. Neopravuje problém trvalého mazání FAT32 a negarantuje integritu po výpadku. Úspěšné zápisy jsou v logu vzorkované, chyby úplné.
