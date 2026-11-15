"""Runtime English/Czech GUI translations. English is the source language."""
from __future__ import annotations
from typing import Any

EN = {
    'window_title': 'FlashBridge — Evidence-based JBOD manager',
    'help_button': 'Help & safety',
    'help_title': 'FlashBridge — Information toolbox',
    'help_close': 'Close',
    'help_overview': 'Overview', 'help_workflow': 'How to use',
    'help_unmount': 'Safe unmount', 'help_safety': 'Safety',
    'help_diagnostics': 'Diagnostics', 'help_inspector':'iPod inspector',
    'file_copy_note': 'File transfers: use Windows File Explorer or your preferred file manager. FlashBridge provides the mounted volume; it does not copy or delete files.',
    'unmount_busy_title': 'Windows is still using the virtual volume',
    'unmount_busy_help': ('Safe unmount was refused by ImDisk. Close all Explorer windows and Total Commander instances, '
                           'even if they currently display another drive (for example C:). Close file dialogs, '
                           'terminals or media players that might access the virtual drive, then select Retry.\n\n'
                           'Do NOT unplug either SD card or stop FlashBridge while the virtual ImDisk device remains. '
                           'Cancel keeps it mounted. Force removal is intentionally unavailable.'),
    'unmount_diagnostic': 'ImDisk output: {detail}',
    'help_text_overview': ('FlashBridge {version}\n\nPurpose\n'
                           'Temporarily exposes a pre-existing two-card, concatenated FAT32 JBOD as one drive letter in Windows. '
                           'It was designed for a flash-modded iPod; it does NOT combine data anew or format cards. ImDisk installation is opt-in.\n\n'
                           'Requires Windows 10/11, administrator privileges, two connected card readers and a separate ImDisk driver installation. '
                           'It does not support exFAT, RAID0 striping or arbitrary pairs of disks.\n\n'
                           'RO means read-only. RW means experimental direct writes to the real cards.'),
    'help_text_workflow': ('1. Insert both original JBOD cards into independent readers.\n'
                           '2. Check that the ImDisk driver is installed; launch FlashBridge with administrator approval.\n'
                           '3. Auto-detect the pair, then check the FIRST/SECOND order and FAT32 evidence.\n'
                           '4. Mount RO to inspect. For writing, only after backup and deliberate consent, choose FAST or VERIFIED and mount RW.\n'
                           '5. Copy with Explorer / Total Commander to the mounted volume, if necessary.\n'
                           '6. Finish every copy, close all file-manager windows, and use Safe unmount.\n'
                           '7. Wait for a confirmed removal, then eject each physical USB reader in Windows.\n\n'
                           'The application does not contain a music/audiobook copy wizard; Windows manages ordinary file transfers.'),
    'help_text_unmount': ('Normal unmount uses imdisk.exe -d (safe detach); never -D or -R.\n\n'
                           'Windows may keep handles to the virtual disk even when an Explorer/Commander window shows C: rather than R:. '
                           'Close *all* Explorer windows, Total Commander, file-picker dialogs, and terminals that may have enumerated drives. '
                           'Wait briefly and Retry.\n\n'
                           'If still blocked, save logs and investigate which process holds the volume. '
                           'FlashBridge intentionally retains both physical media and the proxy connection while removal fails. '
                           'Never unplug a card, force-remove the device or terminate the application to work around a busy lock.'),
    'help_text_safety': ('EXPERIMENTAL RAW READ/WRITE. NOT FOR THE ONLY COPY OF IMPORTANT DATA.\n\n'
                           'Even a verified FAT32 boot sector does not prove filesystem consistency. '
                           'FAT32 is not journaled; unsafe removal can corrupt data.\n\n'
                           'FAST: write + flush each accepted request; no readback.\n'
                           'VERIFIED: write + flush + SHA-256 block readback; slower, not a power-loss guarantee.\n\n'
                           'KNOWN ISSUES: Shift+Delete/permanent deletion has left zero-length files; older sessions experienced WinError 55. '
                           'Do not rely on deletion/space reclamation; do not use forced unmount or CHKDSK repair through this tool.'),
    'help_text_diagnostics': ('Logs: %LOCALAPPDATA%\\FlashBridge\\logs\n\n'
                                'Each run stores .log and .jsonl diagnostics. Open the log directory from this window. '
                                'Look for IO_STATS, IO_END, WRITE/FLUSH errors, IMDISK_UNMOUNT and UNMOUNT_BUSY. '
                                'Fast-mode IO_END is sampled; IO_STATS totals are authoritative for counters.\n\n'
                                'Performance can alternate between ~28 and 45-50 MiB/s depending on the actual card, reader and workload; '
                                'these are observations, not promises.\n\n'
                                'Logs may contain hardware identifiers, source paths or file names. Review before publicly sharing.'),
    'tagline': 'FAT32 concatenation · detection · monitoring · diagnostics',
    'admin': 'ADMINISTRATOR', 'not_admin': 'NOT ELEVATED',
    'language': 'Language:',
    'ready': 'Ready — no physical writes performed',
    'media_header': '1. Physical media — no hard-coded brands or capacities',
    'media_help': 'Automatic scan reads MBR, FAT32 boot/backup, FSInfo and the beginnings of FAT tables. Nothing is written.',
    'col_number': 'Disk', 'col_name': 'Windows name', 'col_size': 'Capacity',
    'col_bus': 'Interface', 'col_state': 'Protection',
    'candidate': 'Candidate', 'read_only_media': 'Read-only media',
    'refresh': 'Refresh disks', 'auto_detect': 'Auto-detect JBOD',
    'detect_selected': 'Verify selected pair', 'manifest': 'Historical SHA (optional):',
    'browse': 'Browse…',
    'evidence_header': '2. Evidence and FAT32 geometry',
    'no_pair': 'No pair has been identified. Media order will never be guessed.',
    'mount_header': '3. ImDisk virtual volume', 'drive_letter': 'Drive letter:',
    'mount_ro': 'Mount RO', 'mount_rw': 'Mount RW (experimental)',
    'unmount': 'Safe unmount', 'inspect_imdisk': 'Inspect ImDisk',
    'mount_help': 'RW requires verified media order and explicit authorization. No filesystem repairs or synthetic test writes.',
    'io_mode_label': 'RW write policy:',
    'io_fast': 'FAST · flush, no block readback',
    'io_verified': 'VERIFIED · flush + SHA-256 block readback',
    'fast_warning': 'FAST improves throughput but does not verify block contents. Select before mounting; cannot change while mounted. FAT32 deletion issues remain unresolved.',
    'rw_policy_confirm': 'Selected RW policy: {mode}. Device or filesystem failure can corrupt files. Confirmation does not certify device health.',
    'delete_warning': 'KNOWN ISSUE: Shift+Delete / permanent FAT32 deletion may leave zero-byte entries. Not fixed by FAST mode.',
    'logs_header': '4. Live monitoring and diagnostics', 'logs': 'Logs:',
    'open_logs': 'Open log folder',
    'operation_busy': 'Operation in progress',
    'operation_busy_detail': 'Wait for the current operation to finish.',
    'working': 'Running: {label}', 'scanning': 'Enumerating disks',
    'auto_scanning': 'Automatically detecting media pair',
    'manual_scanning': 'Checking selected pair',
    'check_imdisk': 'Inspecting ImDisk',
    'mounting': 'Mounting {mode}', 'unmounting': 'Unmounting {letter}:',
    'manifest_pick': 'Select folder containing historical SHA JSONs (optional)',
    'select_hint': 'Auto-detection examines all plausible pairs. If ambiguous, choose two explicitly.',
    'first': 'FIRST', 'second': 'SECOND', 'fat_start': 'FAT32 start',
    'logical_sector': 'logical sector', 'volume_size': 'volume length',
    'rw_eligible': 'Eligible after confirmation (NOT a filesystem integrity guarantee)',
    'rw_blocked': 'BLOCKED: incompatible FAT table headers',
    'owner_permission_title': 'Administrator required',
    'owner_permission': 'Start FlashBridge as Windows administrator.',
    'fat_mismatch_title': 'FAT inconsistency',
    'fat_mismatch': 'The beginnings of the two FAT tables differ; RW is blocked.',
    'letter_taken_title': 'Drive letter in use',
    'letter_taken': '{letter}: is already in use. Choose another letter.',
    'rw_confirm_title': 'CONFIRM PHYSICAL WRITE ACCESS',
    'rw_confirm': ('This permits actual writes to BOTH physical devices:\n'
                   'First: disk {first} ({size1})\nSecond: disk {second} ({size2})\n\n'
                   'An interrupted write may damage the existing FAT32 filesystem.\n'
                   'No test writes are required.\n\nType exactly WRITE to authorize:'),
    'rw_token': 'WRITE',
    'disks_changed': 'Disk {number} has changed or is unsafe. Mount blocked.',
    'identity_changed': 'Disk identity, order or FAT32 geometry changed. Detect again.',
    'fat_blocked': 'RW blocked: FAT headers differ.',
    'imdisk_busy': 'ImDisk already lists device(s) {units}. Unmount safely before retrying.',
    'letter_taken_short': 'Drive letter occupied: {letter}',
    'server_failed': 'Proxy server failed to start: {error}',
    'mount_failed': 'ImDisk rejected the mount: {error}',
    'ambiguous_imdisk': 'New ImDisk unit is not uniquely identified; do not force-remove it.',
    'unmount_failed': 'Unmount failed: {error}',
    'orphaned_imdisk': 'ImDisk still reports device {unit}. Do not stop proxy while it remains.',
    'mounted': '{mode} {letter}: mounted',
    'mount_failed_status': 'Mount failed. Inspect ImDisk before doing anything else.',
    'unmounted_ok': 'Unmounted safely. Eject the physical USB media in Windows before removal.',
    'unmount_incomplete': 'Unmount incomplete. Keep proxy and media connected.',
    'task_error': 'ERROR: {message}', 'task_error_title': 'FlashBridge error',
    'proxy_fault': 'PROXY FAILURE: STOP WRITING. {error}',
    'proxy_live': '{mode} {letter}: · proxy {connection} · read {read} · written {written} · confirmed (10 s) {speed}/s · active I/O avg {active_avg}/s',
    'connected': 'connected', 'waiting': 'waiting',
    'imdisk_none': 'No virtual disks',
    'close_block_title': 'Unmount the virtual disk first',
    'close_block': 'A proxy server or ImDisk device may still hold physical disks open. Unmount safely before exit.',
    'error_shutdown': 'A worker is still active. Do not close the application.',
    'inspector_header':'Read-only iPod storage inspector',
    'inspector_help':('Snapshot individual cards before inserting them into the iPod. Then connect the assembled iPod via USB, select its physical disk, and compare it against the two saved JSON files. No formatting, firmware installation or write access. Comparison never enables RW automatically.'),
    'snapshot_button':'Save selected card snapshot (RO)',
    'compare_button':'Compare selected iPod disk (RO)',
    'snapshot_save':'Save read-only snapshot',
    'snapshot_success':'Read-only snapshot saved:\n{path}\nDetected FAT32 candidates: {count}. No changes made.',
    'compare_title':'Compare live iPod disk to card snapshots',
    'compare_intro':'This will READ ONLY physical disk {number} ({size}). Ensure it is the iPod presented via USB and that you captured both loose cards first. Both orders will be tested; no writes, formatting, firmware actions or automatic RW authorization.',
    'compare_first':'Select first loose-card snapshot JSON',
    'compare_second':'Select second loose-card snapshot JSON',
    'compare_save':'Save iPod comparison evidence report',
    'compare_success':'Evidence saved to {path}\nBest candidate: {order}; matching anchors: {matches}; mismatching anchors: {mismatches}.\nConclusion: {conclusion}. This does not prove bootability or integrity.',
    'inspecting_card':'Read-only card inspection',
    'comparing_ipod':'Read-only iPod comparison',
    'install_imdisk':'Install ImDisk…',
    'install_title':'Install official ImDisk driver',
    'imdisk_already':'ImDisk executable was found. No installation requested.',
    'install_confirm':('Download the official ImDisk installer from LTR Data over HTTPS into a new empty directory? Windows must validate the vendor Authenticode signature before FlashBridge can launch it. You will still approve installation in the installer. Nothing is installed silently.'),
    'install_started':'Official ImDisk installer launched. Complete its dialogs and refresh devices. No physical card changes were made.',
    'installing_imdisk':'Downloading and verifying official ImDisk installer',
    'install_blocked':'FlashBridge did not execute the installer: {detail}\n\nOpen the publisher website for manual installation instead?',
    'help_text_inspector':'The iPod 5/5.5G may have firmware and data partitions and sector geometry unlike a regular FAT32 card. Capture card A, card B and compare both against the assembled iPod presented through USB. Only sampled SHA-256 anchor blocks and partition/FAT32 metadata are recorded, never raw contents. A linear match is evidence only, not validation of bootability or proof of an adapter type. Unknown layouts remain unsupported; never format based on this report. ImDisk installer is fetched only from the official publisher host and executed only if Authenticode verification succeeds.\n\nNo partitioning or firmware provisioning is implemented.',
}

CS = {
    'window_title': 'FlashBridge — ověřované sestavení JBOD',
    'help_button': 'Nápověda a bezpečnost',
    'help_title': 'FlashBridge — informační panel',
    'help_close': 'Zavřít',
    'help_overview': 'Přehled', 'help_workflow': 'Postup',
    'help_unmount': 'Odpojování', 'help_safety': 'Bezpečnost',
    'help_diagnostics': 'Diagnostika', 'help_inspector':'Inspektor iPodu',
    'file_copy_note': 'Přenos souborů: používej Průzkumníka nebo Total Commander. FlashBridge pouze připojuje virtuální disk; sám soubory nekopíruje ani nemaže.',
    'unmount_busy_title': 'Windows stále používají virtuální svazek',
    'unmount_busy_help': ('ImDisk odmítl bezpečné odpojení. Zavři všechna okna Průzkumníka a všechny instance Total Commanderu, '
                           'i když zobrazují jiné disky (například C:). Zavři dialogy pro výběr souborů, '
                           'terminály a přehrávače, které mohly přistupovat k virtuálnímu disku. Pak zvol Opakovat.\n\n'
                           'Dokud zařízení ImDisk existuje, NEODPOJUJ žádnou kartu ani neukončuj FlashBridge. '
                           'Zrušení nechá svazek připojený. Vynucené odebrání není k dispozici.'),
    'unmount_diagnostic': 'Výstup ImDisk: {detail}',
    'help_text_overview': ('FlashBridge {version}\n\nÚčel\n'
                           'Dočasně zpřístupní již existující FAT32 JBOD rozdělený mezi dvě karty jako jediný disk Windows. '
                           'Vznikl pro iPod upravený na flash paměť. Karty nově nespojuje, neformátuje a neinstaluje ovladač ImDisk.\n\n'
                           'Vyžaduje Windows 10/11, práva správce, dvě čtečky a ImDisk; instalaci ovladače lze spustit volitelně v aplikaci. '
                           'Nepodporuje exFAT, RAID0 ani libovolné dvojice disků.\n\n'
                           'RO = pouze čtení; RW = experimentální přímý zápis na fyzická média.'),
    'help_text_workflow': ('1. Obě původní karty JBOD vlož do samostatných čteček.\n'
                           '2. Ověř instalaci ovladače ImDisk; spusť FlashBridge s právy správce.\n'
                           '3. Automaticky najdi dvojici a zkontroluj pořadí PRVNÍ/DRUHÁ a důkazy FAT32.\n'
                           '4. Pro prohlížení připoj RO. Pro zápis až po záloze a vědomém potvrzení vyber FAST nebo VERIFIED a připoj RW.\n'
                           '5. Případné soubory přenášej standardně Průzkumníkem či Commanderem.\n'
                           '6. Dokonči kopírování, zavři všechna okna správců souborů a zvol Bezpečně odpojit.\n'
                           '7. Po potvrzeném odebrání virtuálního disku bezpečně vysuň obě USB čtečky ve Windows.\n\n'
                           'Průvodce doplňováním Music/Audiobooks není součástí GUI.'),
    'help_text_unmount': ('Bezpečné odebrání používá imdisk.exe -d; nikdy -D ani -R.\n\n'
                           'Windows mohou držet svazek otevřený i když okno Průzkumníka/Commanderu ukazuje C:, nikoli R:. '
                           'Zavři všechna okna Průzkumníka, Commander, dialogy pro práci se soubory a terminály, '
                           'které mohly prohledávat jednotky. Chvíli vyčkej a zvol Opakovat.\n\n'
                           'Když odpojení stále nejde, ulož logy a zjisti, který proces drží svazek. '
                           'FlashBridge při neúspěšném odebrání úmyslně nechává běžet proxy i otevřená média. '
                           'Neodpojuj karty, nevynucuj odebrání ani neukončuj aplikaci kvůli blokaci.'),
    'help_text_safety': ('EXPERIMENTÁLNÍ FYZICKÝ ZÁPIS. NENÍ VHODNÝ PRO JEDINOU KOPII DŮLEŽITÝCH DAT.\n\n'
                           'Souhlas boot sektorů neprokazuje konzistenci FAT32. FAT32 nemá žurnál; násilné odpojení může poškodit data.\n\n'
                           'FAST: po každém přijatém požadavku zápis a flush; bez zpětného čtení.\n'
                           'VERIFIED: zápis, flush a SHA-256 zpětně přečteného bloku; pomalejší, bez záruky odolnosti výpadku napájení.\n\n'
                           'ZNÁMÉ CHYBY: Shift+Delete může zanechat nulové soubory; ve starších relacích nastal WinError 55. '
                           'Nespoléhej na mazání / uvolňování místa. Nepoužívej vynucené odpojování ani opravy CHKDSK přes tento nástroj.'),
    'help_text_diagnostics': ('Logy: %LOCALAPPDATA%\\FlashBridge\\logs\n\n'
                                'Každá relace ukládá .log a .jsonl. Složku otevře tlačítko v tomto okně. '
                                'Sleduj IO_STATS, IO_END, chyby WRITE/FLUSH, IMDISK_UNMOUNT a UNMOUNT_BUSY. '
                                'Ve FAST režimu se IO_END vzorkuje; souhrnné čítače IO_STATS jsou úplné.\n\n'
                                'Výkon může přecházet mezi ~28 a 45–50 MiB/s podle karty, čtečky a zátěže. '
                                'Jde o pozorování, nikoli záruku.\n\n'
                                'Logy mohou obsahovat názvy zařízení i cesty či soubory; před zveřejněním je zkontroluj.'),
    'tagline': 'FAT32 spojení · detekce · dohled · diagnostika',
    'admin': 'SPRÁVCE', 'not_admin': 'BEZ PRÁV SPRÁVCE',
    'language': 'Jazyk:',
    'ready': 'Připraveno — žádné fyzické zápisy',
    'media_header': '1. Fyzická média — bez pevných značek a kapacit',
    'media_help': 'Automatická detekce pouze čte MBR, FAT32, zálohu boot sektoru, FSInfo a počátky FAT. Nic nezapisuje.',
    'col_number': 'Disk', 'col_name': 'Označení Windows', 'col_size': 'Kapacita',
    'col_bus': 'Rozhraní', 'col_state': 'Ochrana',
    'candidate': 'Kandidát', 'read_only_media': 'Jen pro čtení',
    'refresh': 'Obnovit disky', 'auto_detect': 'Najít JBOD automaticky',
    'detect_selected': 'Ověřit vybranou dvojici', 'manifest': 'Historické SHA (volitelné):',
    'browse': 'Vybrat…',
    'evidence_header': '2. Důkazy a geometrie FAT32',
    'no_pair': 'Dvojice zatím nebyla určena. Pořadí médií se nebude hádat.',
    'mount_header': '3. Virtuální svazek ImDisk', 'drive_letter': 'Písmeno:',
    'mount_ro': 'Připojit RO', 'mount_rw': 'Připojit RW (experimentální)',
    'unmount': 'Bezpečně odpojit', 'inspect_imdisk': 'Zkontrolovat ImDisk',
    'mount_help': 'RW vyžaduje jednoznačné pořadí a výslovné potvrzení. Bez automatických oprav a testovacích zápisů.',
    'io_mode_label': 'Způsob RW zápisu:',
    'io_fast': 'FAST · flush bez zpětného čtení bloků',
    'io_verified': 'VERIFIED · flush + SHA-256 zpětné čtení bloků',
    'fast_warning': 'FAST zvyšuje propustnost, ale neověřuje obsah zapsaných bloků. Volba jen před připojením. Problémy mazání FAT32 zůstávají nevyřešené.',
    'rw_policy_confirm': 'Zvolený RW režim: {mode}. Výpadek zařízení nebo FAT32 může poškodit soubory. Potvrzení není záruka zdraví médií.',
    'delete_warning': 'ZNÁMÁ CHYBA: Shift+Delete / trvalé mazání FAT32 může ponechávat nulové soubory. Režim FAST to neopravuje.',
    'logs_header': '4. Živý dohled a diagnostika', 'logs': 'Logy:',
    'open_logs': 'Otevřít složku logů',
    'operation_busy': 'Probíhá operace',
    'operation_busy_detail': 'Nejprve dokonči aktuální operaci.',
    'working': 'Probíhá: {label}', 'scanning': 'Načítání disků',
    'auto_scanning': 'Automatická detekce dvojice',
    'manual_scanning': 'Ověření dvojice',
    'check_imdisk': 'Kontrola ImDisku',
    'mounting': 'Připojování {mode}', 'unmounting': 'Odpojování {letter}:',
    'manifest_pick': 'Složka s historickými SHA JSONy (volitelné)',
    'select_hint': 'Automatická detekce vyhodnotí dostupné dvojice. Při nejednoznačnosti vyber dvě ručně.',
    'first': 'PRVNÍ', 'second': 'DRUHÁ', 'fat_start': 'Začátek FAT32',
    'logical_sector': 'logický sektor', 'volume_size': 'délka svazku',
    'rw_eligible': 'Možné po potvrzení (NENÍ záruka konzistence souborového systému)',
    'rw_blocked': 'BLOKOVÁNO: hlavičky FAT nesouhlasí',
    'owner_permission_title': 'Vyžadována práva správce',
    'owner_permission': 'Spusť FlashBridge jako správce Windows.',
    'fat_mismatch_title': 'Neshoda FAT',
    'fat_mismatch': 'Počátky FAT tabulek se liší, RW je zablokováno.',
    'letter_taken_title': 'Písmeno je obsazeno',
    'letter_taken': '{letter}: je obsazeno. Vyber jiné písmeno.',
    'rw_confirm_title': 'POTVRDIT FYZICKÝ ZÁPIS',
    'rw_confirm': ('Tím povolíš skutečné zápisy na OBOU zařízeních:\n'
                   'První: disk {first} ({size1})\nDruhá: disk {second} ({size2})\n\n'
                   'Přerušený zápis může poškodit existující FAT32.\n'
                   'Testovací zápisy nejsou nutné.\n\nPro potvrzení napiš přesně ZAPIS:'),
    'rw_token': 'ZAPIS',
    'disks_changed': 'Disk {number} se změnil nebo není bezpečný. Připojení zablokováno.',
    'identity_changed': 'Identita, pořadí nebo FAT32 se změnily. Proveď novou detekci.',
    'fat_blocked': 'RW zablokováno: hlavičky FAT nesouhlasí.',
    'imdisk_busy': 'ImDisk už eviduje zařízení {units}. Nejprve je bezpečně odpoj.',
    'letter_taken_short': 'Písmeno obsazeno: {letter}',
    'server_failed': 'Proxy server se nespustil: {error}',
    'mount_failed': 'ImDisk odmítl připojení: {error}',
    'ambiguous_imdisk': 'Nové zařízení ImDisk není jednoznačné. Neodpojuj jej násilím.',
    'unmount_failed': 'Odpojení selhalo: {error}',
    'orphaned_imdisk': 'ImDisk stále eviduje zařízení {unit}. Server neukončuj.',
    'mounted': 'Připojeno {mode} {letter}:',
    'mount_failed_status': 'Připojení selhalo. Nejdřív zkontroluj ImDisk.',
    'unmounted_ok': 'Bezpečně odpojeno. Fyzické USB médium odeber přes Windows.',
    'unmount_incomplete': 'Odpojení není dokončeno. Nech běžet proxy a média připojená.',
    'task_error': 'CHYBA: {message}', 'task_error_title': 'Chyba FlashBridge',
    'proxy_fault': 'CHYBA PROXY: NEZAPISOVAT. {error}',
    'proxy_live': '{mode} {letter}: · proxy {connection} · čteno {read} · zapsáno {written} · potvrzeno (10 s) {speed}/s · aktivní I/O průměr {active_avg}/s',
    'connected': 'připojeno', 'waiting': 'čeká',
    'imdisk_none': 'Žádné virtuální disky',
    'close_block_title': 'Nejdřív odpoj virtuální disk',
    'close_block': 'Server nebo ImDisk může držet fyzické disky. Před ukončením bezpečně odpoj.',
    'error_shutdown': 'Pracovní úloha stále běží. Aplikaci nyní nezavírej.',
    'inspector_header':'Inspektor úložiště iPodu — pouze čtení',
    'inspector_help':('Nejdříve ulož samostatné otisky obou karet. Potom je vrať do iPodu, připoj jej přes USB, vyber jeho fyzický disk a porovnej jej se dvěma uloženými JSONy. Bez formátování, instalace firmwaru a zápisu. Porovnání samo nikdy nepovolí RW.'),
    'snapshot_button':'Uložit otisk vybrané karty (RO)',
    'compare_button':'Porovnat disk iPodu (RO)',
    'snapshot_save':'Uložit nedestruktivní otisk karty',
    'snapshot_success':'Otisk uložen:\n{path}\nRozpoznané FAT32 kandidáty: {count}. Žádná změna disku.',
    'compare_title':'Porovnání iPodu s otisky dvou karet',
    'compare_intro':'Bude se POUZE ČÍST fyzický disk {number} ({size}). Ujisti se, že jde o celý iPod přes USB a že máš již otisky obou samostatných karet. Vyzkouší se obě pořadí. Bez zápisu, formátování, úprav firmwaru nebo automatického povolení RW.',
    'compare_first':'Vyber první JSON otisk samostatné karty',
    'compare_second':'Vyber druhý JSON otisk samostatné karty',
    'compare_save':'Uložit důkazní protokol iPodu',
    'compare_success':'Protokol uložen do {path}\nNejlepší kandidát: {order}; shodných vzorků: {matches}; neshodných vzorků: {mismatches}.\nZávěr: {conclusion}. Neověřuje boot ani úplnou integritu dat.',
    'inspecting_card':'Nedestruktivní inspekce karty',
    'comparing_ipod':'Nedestruktivní porovnání iPodu',
    'install_imdisk':'Nainstalovat ImDisk…',
    'install_title':'Instalovat oficiální ovladač ImDisk',
    'imdisk_already':'Program imdisk.exe už je dostupný. Instalace nebyla spuštěna.',
    'install_confirm':('Stáhnout oficiální instalátor ImDisk od LTR Data přes HTTPS do nové prázdné složky? FlashBridge jej spustí pouze po úspěšném ověření digitálního podpisu vydavatele ve Windows. Následně instalaci sám schválíš v instalačním dialogu. Nic se neinstaluje skrytě.'),
    'install_started':'Oficiální instalátor ImDisk byl spuštěn. Dokonči jeho dialogy a obnov seznam. Fyzické karty se neměnily.',
    'installing_imdisk':'Stahování a ověřování ImDisk instalátoru',
    'install_blocked':'FlashBridge instalátor nespustil: {detail}\n\nOtevřít stránku vydavatele pro ruční instalaci?',
    'help_text_inspector':'iPod 5/5.5G může mít firmware partition i FAT32 datovou partition a odlišnou geometrii sektorů. Ulož otisk karty A, karty B a porovnej je s celým sestaveným iPodem připojeným přes USB. Zapisují se jen SHA-256 vzorky malých bloků a metadata MBR/FAT32, ne obsah souborů. Lineární shoda je jen indikace, ne důkaz bootovatelnosti ani konkrétního typu adaptéru. Neznámé geometrie zůstávají nepodporované; nikdy je neformátuj podle tohoto protokolu. Instalátor ImDisk se stahuje jen z webu oficiálního vydavatele a automaticky se spustí pouze při úspěšném ověření Authenticode.\n\nAplikace neprovádí partitioning ani přípravu firmwaru.',
}

# Prevent partially translated UI: every English key must be represented in Czech.
assert EN.keys() == CS.keys(), 'Translation key sets must match'


def translate(key: str, language: str = 'en', **variables: Any) -> str:
    table = CS if language == 'cs' else EN
    try:
        return table[key].format(**variables)
    except KeyError as exc:
        raise KeyError(f'Invalid localization key or missing value: {key}') from exc


def supported_languages() -> tuple[str, ...]:
    return ('en', 'cs')
