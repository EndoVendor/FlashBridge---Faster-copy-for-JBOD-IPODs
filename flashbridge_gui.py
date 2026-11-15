"""FlashBridge Windows Tk GUI; English first, Czech selectable.

Run as administrator. Device operations are deliberately explicit and fail closed.
"""
from __future__ import annotations

import hashlib
import json
import webbrowser
import os
from pathlib import Path
import queue
import threading
import time
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk

from flashbridge_i18n import translate
from flashbridge_inspector import capture_snapshot, compare_live_ipod, load_snapshot
from flashbridge_imdisk_setup import prepare_and_launch, is_installed, VENDOR_PAGE
from flashbridge_core import (
    ProxyServer, discover_pair, discover_all_pairs, eligible, format_bytes,
    imdisk_list, imdisk_mount, imdisk_unmount, is_elevated, load_optional_manifests,
    make_logger, path_letter_free, powershell_disks, VERSION,
)


def imdisk_units(output):
    import re
    return {int(s) for s in re.findall(r'\\Device\\ImDisk(\d+)', output)}


def disk_meta(d):
    return {'number': d.number, 'size': d.size, 'name': d.name, 'bus': d.bus}


def fat_meta(candidate):
    return {key: getattr(candidate, key) for key in candidate.__dataclass_fields__}


class BridgeApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.language = 'en'  # The public project's primary language.
        self.lang_var = tk.StringVar(value='English')
        self.localized_widgets = []
        self.localized_headings = []
        self.event_q = queue.Queue()
        self.log = make_logger(self.event_q.put)
        self.disks = []
        self.plan = None
        self.server = None
        self.mounted = False
        self.mode = None
        self.mounted_letter = None
        self.imdisk_unit = None
        self.active_task = None
        self.selected = set()
        self.letter = tk.StringVar(value='R')
        # Do not assume any user's source drive letter.
        self.manifests_folder = tk.StringVar(value='')
        self.write_mode = tk.StringVar(value='fast')  # Default RW policy: fast+flush
        self.status = tk.StringVar(value=self.t('ready'))
        self.progress = tk.StringVar(value='0 B')
        self._build()
        self._translate_widgets()
        self._buttons()
        self.root.protocol('WM_DELETE_WINDOW', self._on_close)
        self.root.after(200, self._tick)
        self.root.after(300, self._scan)
        self.log.info('APP_OPEN', version=VERSION, elevated=is_elevated(), locale=self.language)

    def t(self, key, **variables):
        return translate(key, self.language, **variables)

    def _widget(self, cls, parent, key, **kw):
        widget = cls(parent, text=self.t(key), **kw)
        self.localized_widgets.append((widget, key))
        return widget

    def _translate_widgets(self):
        self.root.title(self.t('window_title'))
        for widget, key in self.localized_widgets:
            widget.configure(text=self.t(key))
        for tree, column, key in self.localized_headings:
            tree.heading(column, text=self.t(key))
        self.admin.configure(text=self.t('admin' if is_elevated() else 'not_admin'))
        for d in self.disks:
            if str(d.number) in self.tree.get_children(''):
                self.tree.set(str(d.number), 'state',
                    self.t('read_only_media' if d.readonly else 'candidate'))

    def _set_language(self, _value=None):
        self.language = 'cs' if self.lang_var.get() == 'Čeština' else 'en'
        self._translate_widgets()
        if getattr(self, '_help_popup', None) and self._help_popup.winfo_exists():
            self._help_popup.destroy()
            self._show_help()
        if not self.mounted and not self.active_task:
            self.status.set(self.t('ready'))
        self.log.info('LANGUAGE_CHANGED', locale=self.language)

    def _build(self):
        self.root.geometry('1100x810')
        self.root.minsize(980, 710)
        outer = ttk.Frame(self.root, padding=12)
        outer.pack(fill='both', expand=True)
        top = ttk.Frame(outer)
        top.pack(fill='x', pady=(0, 8))
        ttk.Label(top, text='FlashBridge', font=('Segoe UI', 19, 'bold')).pack(side='left')
        self._widget(ttk.Label, top, 'tagline', foreground='#555').pack(side='left', padx=12)
        self.admin = ttk.Label(top, text='', foreground='#0A7A3E' if is_elevated() else '#B33')
        self.admin.pack(side='right', padx=5)
        self._widget(ttk.Button, top, 'help_button', command=self._show_help).pack(side='right', padx=8)
        ttk.Combobox(top, textvariable=self.lang_var, values=('English', 'Čeština'),
                     width=10, state='readonly').pack(side='right', padx=5)
        self._widget(ttk.Label, top, 'language').pack(side='right', padx=4)
        self.lang_var.trace_add('write', lambda *_: self._set_language())
        ttk.Label(outer, textvariable=self.status, foreground='#206080').pack(fill='x', pady=(0, 6))

        media = self._widget(ttk.LabelFrame, outer, 'media_header')
        media.pack(fill='x', pady=4)
        self._widget(ttk.Label, media, 'media_help', wraplength=1030).pack(anchor='w', padx=8, pady=(7, 4))
        columns = ('number', 'name', 'size', 'bus', 'state')
        self.tree = ttk.Treeview(media, columns=columns, show='headings', height=5, selectmode='extended')
        for name, width, key in (
            ('number', 55, 'col_number'), ('name', 350, 'col_name'),
            ('size', 150, 'col_size'), ('bus', 105, 'col_bus'),
            ('state', 165, 'col_state'),
        ):
            self.tree.column(name, width=width, anchor='w')
            self.localized_headings.append((self.tree, name, key))
        self.tree.pack(fill='x', padx=8)
        self.tree.bind('<<TreeviewSelect>>', self._selection_changed)
        mrow = ttk.Frame(media)
        mrow.pack(fill='x', padx=8, pady=7)
        self.refresh = self._widget(ttk.Button, mrow, 'refresh', command=self._scan)
        self.refresh.pack(side='left')
        self.autodetect = self._widget(ttk.Button, mrow, 'auto_detect', command=self._auto_detect)
        self.autodetect.pack(side='left', padx=6)
        self.detect = self._widget(ttk.Button, mrow, 'detect_selected', command=self._detect)
        self.detect.pack(side='left')
        self._widget(ttk.Label, mrow, 'manifest').pack(side='left', padx=(18, 4))
        ttk.Entry(mrow, textvariable=self.manifests_folder, width=25).pack(side='left')
        self._widget(ttk.Button, mrow, 'browse', command=self._choose_manifest).pack(side='left', padx=4)

        inspection = self._widget(ttk.LabelFrame, outer, 'inspector_header')
        inspection.pack(fill='x', pady=4)
        probe_row = ttk.Frame(inspection)
        probe_row.pack(fill='x', padx=8, pady=6)
        self.snapshot_button = self._widget(ttk.Button, probe_row, 'snapshot_button',
                                             command=self._capture_snapshot)
        self.snapshot_button.pack(side='left', padx=(0, 8))
        self.compare_button = self._widget(ttk.Button, probe_row, 'compare_button',
                                            command=self._compare_ipod)
        self.compare_button.pack(side='left')
        self._widget(ttk.Label, inspection, 'inspector_help', wraplength=1010).pack(
            anchor='w', padx=8, pady=(0, 6))

        evidence = self._widget(ttk.LabelFrame, outer, 'evidence_header')
        evidence.pack(fill='x', pady=4)
        self.explanation = tk.Text(evidence, height=5, wrap='word', font=('Consolas', 9),
                                   relief='flat', background='#F5F8FB', state='disabled')
        self.explanation.pack(fill='x', padx=8, pady=7)
        self._explain(self.t('no_pair'))

        mnt = self._widget(ttk.LabelFrame, outer, 'mount_header')
        mnt.pack(fill='x', pady=4)
        r = ttk.Frame(mnt)
        r.pack(fill='x', padx=8, pady=7)
        self._widget(ttk.Label, r, 'drive_letter').pack(side='left')
        ttk.Combobox(r, textvariable=self.letter, values=list('RSTUVWXYZ'), width=4,
                     state='readonly').pack(side='left', padx=(5, 12))
        self.ro_button = self._widget(ttk.Button, r, 'mount_ro', command=lambda: self._mount(False))
        self.ro_button.pack(side='left', padx=4)
        self.rw_button = self._widget(ttk.Button, r, 'mount_rw', command=lambda: self._mount(True))
        self.rw_button.pack(side='left', padx=4)
        self.unmount_button = self._widget(ttk.Button, r, 'unmount', command=self._unmount)
        self.unmount_button.pack(side='left', padx=4)
        self.inspect_button = self._widget(ttk.Button, r, 'inspect_imdisk', command=self._inspect_imdisk)
        self.inspect_button.pack(side='left', padx=4)
        self.install_driver_button = self._widget(ttk.Button, r, 'install_imdisk',
                                                  command=self._install_imdisk)
        self.install_driver_button.pack(side='left', padx=4)
        modes = ttk.Frame(mnt)
        modes.pack(fill='x', padx=8, pady=(0, 4))
        self._widget(ttk.Label, modes, 'io_mode_label').pack(side='left')
        self.fast_radio = self._widget(ttk.Radiobutton, modes, 'io_fast',
                                       variable=self.write_mode, value='fast')
        self.fast_radio.pack(side='left', padx=(12, 8))
        self.verified_radio = self._widget(ttk.Radiobutton, modes, 'io_verified',
                                           variable=self.write_mode, value='verified')
        self.verified_radio.pack(side='left', padx=(12, 8))
        self._widget(ttk.Label, mnt, 'mount_help', wraplength=1000).pack(anchor='w', padx=8, pady=(0, 5))
        self._widget(ttk.Label, mnt, 'fast_warning', wraplength=1000,
                     foreground='#9C5023').pack(anchor='w', padx=8, pady=(0, 7))
        self._widget(ttk.Label, mnt, 'delete_warning', wraplength=1000,
                     foreground='#9C5023').pack(anchor='w', padx=8, pady=(0, 7))

        self._widget(ttk.Label, outer, 'file_copy_note', wraplength=1040,
                     foreground='#475D6B').pack(anchor='w', pady=(5, 3))

        logs = self._widget(ttk.LabelFrame, outer, 'logs_header')
        logs.pack(fill='both', expand=True, pady=4)
        self.logtext = tk.Text(logs, height=10, wrap='none', state='disabled', font=('Consolas', 9))
        self.logtext.pack(fill='both', expand=True, padx=8, pady=(7, 3))
        footer = ttk.Frame(logs)
        footer.pack(fill='x', padx=8, pady=(0, 7))
        ttk.Label(footer, text=str(self.log.log_path.parent), foreground='#666').pack(side='left')
        self._widget(ttk.Button, footer, 'open_logs', command=self._open_logs).pack(side='right')

    def _explain(self, value):
        self.explanation.configure(state='normal')
        self.explanation.delete('1.0', 'end')
        self.explanation.insert('end', value)
        self.explanation.configure(state='disabled')

    def _post(self, *values):
        self.event_q.put(('action', *values))

    def _task(self, label_key, fn, **variables):
        if self.active_task is not None:
            messagebox.showwarning(self.t('operation_busy'), self.t('operation_busy_detail'))
            return
        self.active_task = label_key
        self.status.set(self.t('working', label=self.t(label_key, **variables)))
        self._buttons()
        def worker():
            try:
                fn()
            except Exception as exc:
                self.log.error('TASK_FAILURE', task=label_key, error=repr(exc))
                self._post('task_error', str(exc))
            finally:
                self._post('task_finished')
        threading.Thread(target=worker, daemon=True, name='Job-'+label_key[:15]).start()

    def _scan(self):
        if self.mounted or self.server: return
        def work():
            disks = powershell_disks()
            self.log.info('ENUMERATE', disks=[disk_meta(d) for d in disks])
            self._post('disks', disks)
        self._task('scanning', work)

    def _selection_changed(self, _event=None):
        selected = {int(x) for x in self.tree.selection()}
        self.selected = selected
        if self.plan and selected == {self.plan.first.number, self.plan.second.number}:
            return
        self.plan = None
        self._buttons()

    def _auto_detect(self):
        if self.mounted or self.server or len([d for d in self.disks if eligible(d)]) < 2: return
        folder = self.manifests_folder.get()
        disks = list(self.disks)
        def work():
            plan = discover_all_pairs(disks, manifests=load_optional_manifests(folder))
            self.log.info('AUTO_PAIR_DETECTED', first=disk_meta(plan.first),
                          second=disk_meta(plan.second), fat=fat_meta(plan.fat), evidence=list(plan.evidence))
            self._post('autoplan', plan)
        self._task('auto_scanning', work)

    def _detect(self):
        cards = [d for d in self.disks if d.number in self.selected]
        folder = self.manifests_folder.get()
        def work():
            plan = discover_pair(cards, manifests=load_optional_manifests(folder))
            self.log.info('ORDER_DETECTED', first=disk_meta(plan.first),
                          second=disk_meta(plan.second), fat=fat_meta(plan.fat), evidence=list(plan.evidence))
            self._post('plan', plan)
        self._task('manual_scanning', work)

    def _choose_manifest(self):
        value = filedialog.askdirectory(title=self.t('manifest_pick'))
        if value: self.manifests_folder.set(value)

    def _selected_single_inspection_disk(self):
        if self.mounted or self.server or self.active_task or len(self.selected)!=1:
            return None
        return next((d for d in self.disks if d.number in self.selected and eligible(d)),None)

    def _capture_snapshot(self):
        d=self._selected_single_inspection_disk()
        if not d:return
        path=filedialog.asksaveasfilename(parent=self.root,defaultextension='.json',
            initialfile=f'flashbridge-card-disk{d.number}.json',
            filetypes=[('JSON','*.json')],title=self.t('snapshot_save'))
        if not path:return
        def work():
            # Repeat enumeration at point of use: never read a different device after hotplug.
            fresh=next((x for x in powershell_disks() if x.number==d.number),None)
            if not fresh or fresh.size!=d.size or fresh.name!=d.name or fresh.serial!=d.serial or not eligible(fresh):
                raise RuntimeError(self.t('disks_changed',number=d.number))
            snapshot=capture_snapshot(fresh)
            Path(path).write_text(json.dumps(snapshot,indent=2,ensure_ascii=False),encoding='utf-8')
            self.log.info('INSPECTOR_SNAPSHOT',disk=d.number,size=d.size,path=str(path),
                          anchors=len(snapshot['anchors_sha256']),fat_candidates=len(snapshot['fat32_candidates']))
            self._post('inspector_result', self.t('snapshot_success',path=path,
                                     count=len(snapshot['fat32_candidates'])))
        self._task('inspecting_card',work)

    def _compare_ipod(self):
        d=self._selected_single_inspection_disk()
        if not d:return
        if not messagebox.askokcancel(self.t('compare_title'),
             self.t('compare_intro',number=d.number,size=format_bytes(d.size)),parent=self.root):return
        first=filedialog.askopenfilename(parent=self.root,title=self.t('compare_first'),
                                         filetypes=[('JSON','*.json')])
        if not first:return
        second=filedialog.askopenfilename(parent=self.root,title=self.t('compare_second'),
                                          filetypes=[('JSON','*.json')])
        if not second:return
        path=filedialog.asksaveasfilename(parent=self.root,defaultextension='.json',
            initialfile='flashbridge-ipod-comparison.json',
            filetypes=[('JSON','*.json')],title=self.t('compare_save'))
        if not path:return
        def work():
            a,b=load_snapshot(first),load_snapshot(second)
            fresh=next((x for x in powershell_disks() if x.number==d.number),None)
            if not fresh or fresh.size!=d.size or fresh.name!=d.name or fresh.serial!=d.serial or not eligible(fresh):
                raise RuntimeError(self.t('disks_changed',number=d.number))
            report=compare_live_ipod(fresh,a,b)
            Path(path).write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf-8')
            self.log.info('INSPECTOR_COMPARE',ipod_disk=d.number,path=str(path),
                 summary=[{k:v[k] for k in ('order','matches','mismatches','status')}
                          for v in report['variants']],write_authorized=False)
            best=max(report['variants'],key=lambda v:(v['matches'],-v['mismatches']))
            self._post('inspector_result',self.t('compare_success',path=path,
                order=best['order'],matches=best['matches'],mismatches=best['mismatches'],
                conclusion=report['conclusion']))
        self._task('comparing_ipod',work)

    def _install_imdisk(self):
        if self.mounted or self.server or self.active_task:return
        if is_installed():
            messagebox.showinfo('ImDisk',self.t('imdisk_already'),parent=self.root)
            return
        if not messagebox.askyesno(self.t('install_title'),self.t('install_confirm'),
                                   parent=self.root):return
        def work():
            try:
                result=prepare_and_launch()
                self.log.info('IMDISK_INSTALLER',status=result['status'])
                self._post('inspector_result',self.t('install_started'))
            except Exception as exc:
                self.log.warning('IMDISK_INSTALLER_BLOCKED',reason=str(exc))
                self._post('installer_blocked',str(exc))
        self._task('installing_imdisk',work)

    def _inspect_imdisk(self):
        def work():
            output = imdisk_list().strip()
            self.log.info('IMDISK_LIST', output=output)
            self._post('imdisk', output)
        self._task('check_imdisk', work)

    def _mount(self, writable):
        if not self.plan or self.mounted or self.server: return
        if not is_elevated():
            messagebox.showerror(self.t('owner_permission_title'), self.t('owner_permission'))
            return
        if writable and not self.plan.read_write_safe:
            messagebox.showerror(self.t('fat_mismatch_title'), self.t('fat_mismatch'))
            return
        letter = self.letter.get().upper()
        if not path_letter_free(letter):
            messagebox.showerror(self.t('letter_taken_title'), self.t('letter_taken', letter=letter))
            return
        selected_mode = self.write_mode.get()
        if writable:
            confirm = simpledialog.askstring(self.t('rw_confirm_title'), self.t('rw_confirm',
                first=self.plan.first.number, size1=format_bytes(self.plan.first.size),
                second=self.plan.second.number, size2=format_bytes(self.plan.second.size)) +
                '\n\n' + self.t('rw_policy_confirm', mode=self.t('io_fast' if selected_mode == 'fast' else 'io_verified')),
                parent=self.root)
            if confirm != self.t('rw_token'):
                return
        plan = self.plan
        def work():
            current = {d.number: d for d in powershell_disks()}
            for expected in (plan.first, plan.second):
                actual = current.get(expected.number)
                if (not actual or actual.size != expected.size or not eligible(actual)
                        or (writable and actual.readonly)):
                    raise RuntimeError(self.t('disks_changed', number=expected.number))
            fresh = discover_pair([current[plan.first.number], current[plan.second.number]])
            if (fresh.first.number != plan.first.number or fresh.second.number != plan.second.number
                    or fresh.fat != plan.fat):
                raise RuntimeError(self.t('identity_changed'))
            if writable and not fresh.read_write_safe:
                raise RuntimeError(self.t('fat_blocked'))
            previous = imdisk_units(imdisk_list())
            if previous:
                raise RuntimeError(self.t('imdisk_busy', units=str(sorted(previous))))
            if not path_letter_free(letter):
                raise RuntimeError(self.t('letter_taken_short', letter=letter))
            # Choose a fresh ephemeral localhost port for each mount, not a fixed global port.
            server = ProxyServer(fresh, writable, self.log, port=0,
                                 on_state=lambda state: self._post('server_state', state),
                                 write_mode=selected_mode)
            self.log.info('MOUNT_POLICY_SELECTED', writable=writable,
                          mode=selected_mode if writable else 'readonly')
            self.server = server
            server.start()
            if not server.started.wait(20) or not server.ready:
                server.stop()
                server.join(3)
                if not server.is_alive():
                    server.close_devices()
                    self.server = None
                raise RuntimeError(self.t('server_failed', error=server.last_error))
            code, output = imdisk_mount(fresh, letter, writable, server.port)
            self.log.info('IMDISK_MOUNT', result=code, output=output.strip(),
                          letter=letter, writable=writable, port=server.port)
            current_units = imdisk_units(imdisk_list())
            created_units = current_units - previous
            if code != 0:
                if not created_units:
                    server.stop()
                    server.join(4)
                    if not server.is_alive():
                        server.close_devices()
                        self.server = None
                self._post('mount_failed', output)
                raise RuntimeError(self.t('mount_failed', error=output.strip()))
            if len(created_units) != 1:
                self._post('mount_failed', output)
                raise RuntimeError(self.t('ambiguous_imdisk'))
            self.imdisk_unit = next(iter(created_units))
            self._post('mounted', letter, 'RW' if writable else 'RO')
        self._task('mounting', work, mode='RW' if writable else 'RO')

    def _unmount(self):
        if not self.mounted or self.active_task: return
        letter = self.mounted_letter
        unit = self.imdisk_unit
        def work():
            code, output = imdisk_unmount(letter)
            self.log.info('IMDISK_UNMOUNT', result=code, output=output.strip(), letter=letter, unit=unit)
            if code != 0:
                # If a different ImDisk process removed it meanwhile, validate
                # by *unit identity* instead of assuming an error means mounted.
                if unit not in imdisk_units(imdisk_list()):
                    self.log.info('UNMOUNT_CONFIRMED', letter=letter, unit=unit,
                                  nonzero_imdisk_exit=code)
                    self._post('unmounted')
                    return
                self.log.warning('UNMOUNT_BUSY', result=code, letter=letter, unit=unit,
                                 output=output.strip())
                self._post('unmount_error', output)
                return
            for _ in range(20):
                if unit not in imdisk_units(imdisk_list()):
                    self.log.info('UNMOUNT_CONFIRMED', letter=letter, unit=unit,
                                  nonzero_imdisk_exit=False)
                    self._post('unmounted')
                    return
                time.sleep(.5)
            details = imdisk_list()
            self.log.warning('UNMOUNT_STILL_PRESENT', unit=unit, output=details.strip())
            self._post('unmount_error', details)
        self._task('unmounting', work, letter=letter)

    def _offer_unmount_retry(self, details):
        # No process killing, no -D / -R, no forced raw-handle closure.
        if not self.mounted or self.active_task:
            return
        msg = self.t('unmount_busy_help')
        if details:
            msg += '\n\n' + self.t('unmount_diagnostic', detail=details[:500])
        if messagebox.askretrycancel(self.t('unmount_busy_title'), msg, parent=self.root):
            self.log.info('UNMOUNT_USER_RETRY', letter=self.mounted_letter, unit=self.imdisk_unit)
            self._unmount()

    def _show_help(self):
        if getattr(self, '_help_popup', None) and self._help_popup.winfo_exists():
            self._help_popup.lift()
            self._help_popup.focus_force()
            return
        popup = tk.Toplevel(self.root)
        self._help_popup = popup
        popup.title(self.t('help_title'))
        popup.geometry('840x600')
        popup.minsize(680, 450)
        popup.transient(self.root)
        notebook = ttk.Notebook(popup)
        notebook.pack(fill='both', expand=True, padx=12, pady=12)
        for key, topic in (('help_overview', 'overview'), ('help_workflow', 'workflow'),
                           ('help_unmount', 'unmount'), ('help_safety', 'safety'),
                           ('help_diagnostics', 'diagnostics'), ('help_inspector','inspector')):
            frame = ttk.Frame(notebook)
            notebook.add(frame, text=self.t(key))
            viewer = tk.Text(frame, wrap='word', font=('Segoe UI', 10), padx=16, pady=12,
                             relief='flat', background='#F6F8FB')
            scroll = ttk.Scrollbar(frame, command=viewer.yview)
            viewer.configure(yscrollcommand=scroll.set)
            scroll.pack(side='right', fill='y')
            viewer.pack(side='left', fill='both', expand=True)
            viewer.insert('1.0', self.t('help_text_'+topic, version=VERSION))
            viewer.configure(state='disabled')
        bottom = ttk.Frame(popup, padding=(12, 0, 12, 12))
        bottom.pack(fill='x')
        ttk.Button(bottom, text=self.t('open_logs'), command=self._open_logs).pack(side='left')
        ttk.Button(bottom, text=self.t('help_close'), command=popup.destroy).pack(side='right')
        popup.bind('<Escape>', lambda _event: popup.destroy())

    def _buttons(self):
        busy = self.active_task is not None
        def state(button, active): button.configure(state='normal' if active else 'disabled')
        idle = not busy and not self.mounted and not self.server
        state(self.refresh, idle)
        state(self.detect, idle and len(self.selected) == 2)
        state(self.autodetect, idle and sum(1 for d in self.disks if eligible(d)) >= 2)
        state(self.ro_button, idle and self.plan is not None)
        state(self.rw_button, idle and self.plan is not None and self.plan.read_write_safe)
        state(self.fast_radio, idle)
        state(self.verified_radio, idle)
        state(self.unmount_button, not busy and self.mounted)
        state(self.inspect_button, not busy)
        state(self.install_driver_button, idle)
        state(self.snapshot_button,idle and len(self.selected)==1)
        state(self.compare_button,idle and len(self.selected)==1)

    def _fault(self):
        return self.server is None or self.server.failed or not self.server.ready

    def _open_logs(self):
        if os.name == 'nt': os.startfile(str(self.log.log_path.parent))

    def _tick(self):
        try:
            for _ in range(80):
                item = self.event_q.get_nowait()
                if isinstance(item, tuple) and item and item[0] == 'action':
                    self._action(item[1:])
                elif isinstance(item, dict):
                    line = item['timestamp_utc']+' '+item['event']
                    extra = {k:v for k,v in item.items() if k not in ('timestamp_utc', 'event', 'seq')}
                    if extra: line += ' '+str(extra)[:380]
                    self.logtext.configure(state='normal')
                    self.logtext.insert('end', line+'\n')
                    self.logtext.see('end')
                    self.logtext.configure(state='disabled')
        except queue.Empty:
            pass
        if self.server and self.server.failed:
            self.status.set(self.t('proxy_fault', error=self.server.last_error))
        elif self.mounted and self.server:
            self.status.set(self.t('proxy_live', mode=self.mode, letter=self.mounted_letter,
                connection=self.t('connected' if self.server.active else 'waiting'),
                read=format_bytes(self.server.bytes_read),
                written=format_bytes(self.server.bytes_written),
                speed=format_bytes(self.server.rolling_write_rate()),
                active_avg=format_bytes(self.server.bytes_written / max(self.server._write_total_seconds,1e-9))
                    if self.server.write_requests else '0 B'))
        self._buttons()
        self.root.after(200, self._tick)

    def _action(self, a):
        key = a[0]
        if key == 'disks':
            self.disks = a[1]
            self.plan = None
            self.selected.clear()
            for item in self.tree.get_children(): self.tree.delete(item)
            for d in self.disks:
                if eligible(d):
                    self.tree.insert('', 'end', iid=str(d.number), values=(
                        d.number, d.name, format_bytes(d.size), d.bus,
                        self.t('read_only_media' if d.readonly else 'candidate')))
            self._explain(self.t('select_hint'))
            self.root.after(250, self._auto_detect)
        elif key == 'autoplan':
            plan = a[1]
            self.tree.selection_set([str(plan.first.number), str(plan.second.number)])
            self.selected = {plan.first.number, plan.second.number}
            self._action(('plan', plan))
        elif key == 'plan':
            self.plan = plan = a[1]
            self._explain(
                f"{self.t('first')}: {plan.first.number} — {plan.first.name} ({format_bytes(plan.first.size)})\n"
                f"{self.t('second')}: {plan.second.number} — {plan.second.name} ({format_bytes(plan.second.size)})\n"
                f"{self.t('fat_start')}: {plan.fat.offset} B; "
                f"{self.t('logical_sector')}: {plan.fat.sector_size} B; "
                f"{self.t('volume_size')}: {format_bytes(plan.volume_bytes)}\n"
                + ' | '.join(plan.evidence) + '\nRW: '
                + self.t('rw_eligible' if plan.read_write_safe else 'rw_blocked'))
        elif key == 'mounted':
            self.mounted_letter, self.mode = a[1], a[2]
            self.mounted = True
            self.status.set(self.t('mounted', mode=self.mode, letter=self.mounted_letter))
        elif key == 'mount_failed':
            self.status.set(self.t('mount_failed_status'))
        elif key == 'unmounted':
            self.mounted = False
            self.mode = None
            self.mounted_letter = None
            self.imdisk_unit = None
            if self.server:
                self.server.stop()
                # Cleanup after confirmed ImDisk removal, without blocking Tk.
                # Never close raw media while proxy thread remains live.
                self.root.after(250, self._reap_stopped_server)
            self.status.set(self.t('unmounted_ok'))
        elif key == 'unmount_error':
            self.status.set(self.t('unmount_incomplete'))
            # Keep proxy and disk handles alive. A retry requires a fresh user click.
            detail = a[1].strip() if len(a) > 1 else ''
            self.root.after(350, lambda d=detail: self._offer_unmount_retry(d))
        elif key == 'task_error':
            self.status.set(self.t('task_error', message=a[1]))
            messagebox.showerror(self.t('task_error_title'), a[1])
        elif key == 'task_finished':
            self.active_task = None
        elif key == 'inspector_result':
            self.status.set(self.t('ready'))
            messagebox.showinfo(self.t('inspector_header'),a[1],parent=self.root)
        elif key == 'installer_blocked':
            if messagebox.askyesno(self.t('install_title'),
                self.t('install_blocked',detail=a[1]),parent=self.root):
                webbrowser.open(VENDOR_PAGE)
        elif key == 'imdisk':
            messagebox.showinfo('ImDisk', a[1] or self.t('imdisk_none'))
        self._buttons()

    def _reap_stopped_server(self):
        if self.mounted or not self.server:
            return
        if self.server.is_alive():
            self.root.after(500, self._reap_stopped_server)
            return
        self.server.close_devices()
        self.server = None
        self.log.info('PROXY_HANDLES_CLOSED_AFTER_UNMOUNT')
        self._buttons()

    def _on_close(self):
        if self.active_task is not None:
            messagebox.showwarning(self.t('close_block_title'), self.t('error_shutdown'))
            return
        if self.mounted or (self.server and (self.server.is_alive() or self.server.dev)):
            messagebox.showwarning(self.t('close_block_title'), self.t('close_block'))
            return
        self.log.info('APPLICATION_EXIT')
        self.log.close()
        self.root.destroy()


def main():
    root = tk.Tk()
    try:
        style = ttk.Style()
        if 'vista' in style.theme_names():
            style.theme_use('vista')
    except Exception:
        pass
    BridgeApp(root)
    root.mainloop()


if __name__ == '__main__':
    main()
