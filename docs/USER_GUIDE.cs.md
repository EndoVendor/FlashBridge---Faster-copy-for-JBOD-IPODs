# FlashBridge v0.3.3-rc2 — uživatelský návod (čeština)

[English guide](USER_GUIDE.md) · [Úvod projektu](../README.cs.md) · [Bezpečnost](../SECURITY.cs.md) · [Přejímací seznam](../RELEASE_CHECKLIST.md)

**Stav: release candidate; hardwarová přejímka rc2 ještě neproběhla.** Základní zápisový engine vychází z v0.3.2-alpha. FlashBridge používá přímý přístup k fyzickým kartám, proto není určený pro jedinou kopii nenahraditelných dat. Začni v režimu pouze pro čtení (RO).

## 1. Co program dělá — a co ne

FlashBridge zpřístupňuje **již existující dvoukartové sekvenční FAT32 JBOD** z flashově upraveného iPodu jako dočasnou virtuální jednotku Windows pomocí ImDisku. Obě karty musí být vloženy do **dvou samostatných USB čteček**. Program nekopíruje hudbu sám: po připojení virtuální jednotky používej Průzkumníka nebo Total Commander.

Nový **iPod Storage Inspector** zkoumá **první kartu zvlášť, druhou kartu zvlášť a poté sestavený iPod přes USB**. Zaznamenává malé vzorky SHA-256, kapacity a dostupné MBR/FAT32 struktury. Umí zkusit obě pořadí při *lineárním spojení*. Není to čtení celé karty, identifikace modelu adaptéru, test bootovatelnosti ani automatické povolení RW.

**Program NEFORMÁTUJE SD karty**, nevytváří nový iPod disk, nepřepisuje partition tabulky, neinstaluje firmware/bootloader ani neopravuje FAT32. Jiný flash adaptér může mít zcela jiné mapování; neshoda vzorků sama o sobě neprokazuje poškození karet.

## 2. Stažení a první spuštění

1. Otevři [trvalý GitHub prerelease v0.3.3-rc2](https://github.com/martinfrolik-art/FlashBridge---Faster-copy-for-JBOD-IPODs/releases/tag/v0.3.3-rc2). V části **Assets** stáhni **FlashBridge-v0.3.3-rc2-Windows-x64-UNSIGNED.zip** (nebo samostatný EXE) a **SHA256.txt** pro kontrolu. Jde o **nepodepsané experimentální vydání bez záruky**, nikoli o stabilní verzi.
2. Rozbal stažený ZIP a přečti přiložené README. Spusť **FlashBridge.exe** ve Windows 10/11 x64 a schval výzvu správce (UAC). **Python ani CMD nepotřebuješ.** EXE není podepsané, takže Windows může zobrazit varování SmartScreen. Nepovažuj to za ověření bezpečnosti; stahuj výhradně z tohoto repozitáře a kontroluj původ.
3. ImDisk je **samostatný ovladač**, nikoli součást EXE. Tlačítkem **Zkontrolovat ImDisk** ověř jeho dostupnost. Není-li nainstalován, použij **Nainstalovat ImDisk…**. Program stáhne instalační EXE pouze z oficiálního HTTPS hostitele LTR Data, přes Windows ověří platný Authenticode podpis očekávaného vydavatele a až poté nabídne běžnou instalaci. Pokud podpis nebo stažení nevyhoví, instalátor nespustí. V takovém případě pokračuj ručně z [oficiální stránky ImDisk](https://www.ltr-data.se/opencode.html#ImDisk).
4. Neodsouhlasuj nabídku Windows „Inicializovat disk“ ani „Naformátovat disk“ u jednotlivých karet. **Nejde o běžné samostatné FAT32 svazky.**

## 3. Ovládací prvky — co přesně znamenají

| Ovládání (české GUI) | Účinek | Zapisuje na SD kartu? |
| --- | --- | --- |
| **Obnovit disky** | Načte fyzické disky a jejich identifikaci z Windows | Ne |
| **Najít JBOD automaticky** | Zkouší rozpoznat existující podporovanou dvojici podle FAT32 důkazů | Ne |
| **Ověřit vybranou dvojici** | Zkontroluje přesně dva označené fyzické disky; pořadí neurčuje podle velikosti ani čísla | Ne |
| **Uložit otisk vybrané karty (RO)** | Uloží JSON s metadaty a hashi malých vzorků jedné vybrané karty | Ne |
| **Porovnat disk iPodu (RO)** | Načte dva uložené otisky a porovná je s vybraným fyzickým diskem iPodu přes USB | Ne |
| **Zkontrolovat ImDisk** | Zjišťuje dostupnost virtuálního diskového ovladače | Ne |
| **Nainstalovat ImDisk…** | Po souhlasu stáhne a ověří instalátor Windows ovladače; vyžaduje další potvrzení | Ne na karty |
| **Připojit RO** | Vystaví rozpoznaný JBOD jako virtuální jednotku jen pro čtení | Ne |
| **Připojit RW (experimentální)** | Povolí skutečný zápis na obě fyzické karty po samostatném potvrzení **WRITE** | **Ano** |
| **FAST** | V RW vyžádá flush po každém zápisovém požadavku, **bez zpětného čtení bloků** | Ano, v RW |
| **VERIFIED** | V RW vyžádá flush a porovná znovu načtené bloky pomocí SHA-256 | Ano, v RW |
| **Bezpečně odpojit** | Pokusí se standardně odebrat ImDisk a ověřit odebrání jednotky | Nevytváří nové soubory; dokončení OS zápisů může probíhat |
| **Otevřít složku logů** | Otevře místní diagnostiku | Ne |

**Důležité:** Výsledek inspektoru „CANDIDATE ONLY“ znamená důkaz slučitelného lineárního mapování **v odebraných vzorcích**, nikoli certifikaci adaptéru. „NOT PROVEN“ znamená, že lineární shoda nebyla prokázána, ne automaticky vadnou kartu. Inspektor neovlivňuje nezávislé ověření, které podmiňuje připojení RW.

## 4. Scénář A — inspekce rozložení karet a iPodu (doporučený první test)

Tento scénář **nevyžaduje instalaci ImDisku ani připojení virtuálního JBOD**; nic do fyzických karet nezapisuje sama aplikace.

1. Vyjmi obě SD karty z flash adaptéru. Označ si jejich skutečné pozice **A** a **B**, ať je nezaměníš.
2. Vlož **jen kartu A** do samostatné čtečky, v aplikaci klikni **Obnovit disky**, zkontroluj velikost a popis fyzického disku. Označ **právě jeden disk**.
3. Klikni **Uložit otisk vybrané karty (RO)** a ulož soubor například **card-A.json** mimo kartu.
4. Stejným postupem zachyť kartu B jako **card-B.json**. Nevol volbu „Formátovat“ nebo „Inicializovat“, i když ji Windows nabízí.
5. Vrať karty **na původní místa do adaptéru**, připoj iPod přes USB v diskovém režimu, klikni **Obnovit disky**. Pozorně vyber **fyzický disk iPodu**, nikoli systémový disk ani písmeno jednotky.
6. Klikni **Porovnat disk iPodu (RO)**; zvol oba JSON soubory a ulož **flashbridge-ipod-comparison.json**.
7. V reportu přečti **variants / order / matches / mismatches / unavailable / status**, součet kapacit a **ipod_snapshot** (kapacita, MBR partition entries, FAT32 kandidáti a vzorky). Testuje se A→B i B→A.
8. Pokud nejsou shody jednoznačné, **nic neodhaduj a nepřecházej na experimentální zápis**. Jiné adaptéry mohou používat jiné mapování nebo velikost sektorů.

JSON obsahuje metadata, názvy disků a SHA-256 vzorků, nikoli kompletní obsah hudby. Přesto jej před veřejným sdílením zkontroluj.

## 5. Scénář B — čtení existujícího JBOD a případné kopírování

1. Připoj **obě původní karty** do dvou USB čteček. Neformátuj.
2. Spusť aplikaci jako správce, zkontroluj ImDisk a klikni **Najít JBOD automaticky**. Pokud automatika hlásí nejednoznačnost, označ správné **dva fyzické disky** a klikni **Ověřit vybranou dvojici**. Když ověření neuspěje, nepokračuj násilím.
3. Zkontroluj důkazy: **PRVNÍ / DRUHÁ**, začátek FAT32, délku svazku, sektorovou geometrii, záložní boot sektor a stav FAT hlaviček. Nejde o důkaz celkové integrity filesystemu.
4. Vyber volné písmeno virtuální jednotky (například **R:**). Nejprve klikni **Připojit RO** a ve správci souborů ověř, že adresáře dávají smysl.
5. Pro kopírování na kartu teprve po ověřené záloze a na postradatelných testovacích médiích zvol **FAST** nebo **VERIFIED**, klikni **Připojit RW (experimentální)** a zadej přesně **WRITE**. Povoluješ fyzický zápis, ne jen zobrazení disku.
6. Kopíruj běžným Průzkumníkem či Total Commanderem. FlashBridge nemá zvláštní funkci „doplň chybějící Music/Audiobooks“.
7. **Nemaž trvale soubory přes Shift+Delete.** Z vývojových běhů máme nevyřešené případy nulových souborů / neuvolněného místa; mazání není spolehlivě ověřeno. FAST není verifikace dat.
8. Po skončení všech přenosů zavři veškeré Průzkumníky a Commandery, včetně těch otevřených na **C:**. Poté klikni **Bezpečně odpojit**. Po potvrzení odebrání ImDisku vysuň obě fyzické čtečky ve Windows a teprve potom vyjmi SD karty.

Při neúspěšném odpojení **neodpojuj fyzické karty**, nevypínej FlashBridge ani nepoužívej vynucené ImDisk odstranění. Zavři programy, které mohou držet disk, a použij **Opakovat**. Pokud je stále blokováno, ulož log a zjisti držitele svazku.

## 6. Problémy a další postup

| Situace | Co udělat |
| --- | --- |
| Windows nabízí inicializaci/formát | **Odmítni**. Samostatná JBOD karta nemusí obsahovat platný samostatný filesystem. |
| Disk se neobjeví | Zkontroluj připojení čtečky, kabel, správce zařízení; poté **Obnovit disky**. Nic neinicializuj. |
| Automatika nenašla JBOD | Zkontroluj samostatné karty a jejich velikosti. Může jít o jiný adaptér či nepodporované rozložení. Nejprve použij inspektor. |
| Inspektor píše „NOT PROVEN“ | Prohlédni oba kandidátní směry a dostupnost vzorků; znamená to pouze neprokázanou lineární shodu. |
| ImDisk chybí | **Zkontrolovat ImDisk**, případně **Nainstalovat ImDisk…**; pokud podpis nelze ověřit, otevři oficiální web. |
| R: je obsazeno | Vyber jiné volné písmeno. Nenuť aplikaci přepsat existující jednotku. |
| ImDisk odmítl odpojení | Zavři **všechna** okna Exploreru/Commanderu a dialogy souborů; vrať se a klikni **Opakovat**. Karty nech připojené. |
| I/O chyba / WinError / chybné soubory | Přeruš nové zápisy, ponech zařízení připojená pro bezpečné odpojení, uschovej log. Nespouštěj naslepo CHKDSK ani obnovu. |
| Chceš připravit dvě zcela nové karty | Tato verze to **neumí**. Karty musí být již inicializované iPodem/adaptérem; univerzální formátování není ověřené. |

## 7. Diagnostika, výkon, soukromí

Diagnostické soubory **.log** a **.jsonl** jsou ve složce **%LOCALAPPDATA%\FlashBridge\logs**. Ve FAST režimu jsou jednotlivé události IO_END pouze vzorkované; souhrny přenosů čti z **IO_STATS**. Přenosová rychlost se může měnit podle média, čtečky a interní správy flash paměti; žádná konkrétní hodnota není garantována.

**Známé hranice:** dvě karty, sekvenční FAT32, ne exFAT/RAID0/tři a více médií; bez formátování, obnovy firmwaru a automatických oprav. Potvrzený flush ani VERIFIED readback negarantují přežití výpadku napájení. Před zveřejněním anonymizuj logy a disková metadata.

## 8. Co přesně je otestováno

- **62 syntetických testů** prošlo na Windows a Linuxu v Pythonu 3.10 i 3.13 pro finální commit rc2.
- Windows x64 EXE bylo úspěšně sestaveno pomocí PyInstaller a zabaleno jako GitHub Actions artifact.
- **Neověřeno:** první spuštění a instalace ImDisku na cílovém PC, snímání skutečných karet, porovnání reálného iPodu, blokované odpojení a RW na postradatelných médiích. To jsou body hardwarové přejímky, nikoli prokázané schopnosti release kandidáta.

Chyby hlásit přes [GitHub Issues](https://github.com/martinfrolik-art/FlashBridge---Faster-copy-for-JBOD-IPODs/issues), nejlépe s verzí Windows, modelem obou USB čteček, přesným postupem a **anonymizovaným** JSONL logem. Nepřikládej celé obrazy SD karet ani osobní hudební soubory.
