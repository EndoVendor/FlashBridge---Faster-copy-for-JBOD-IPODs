"""FlashBridge Windows Tk GUI; English first, Czech selectable.

Run as administrator. Device operations are deliberately explicit and fail closed.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import queue
import threading
import time
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk

from flashbridge_i18n import translate
from flashbridge_core import (
    ProxyServer, discover_pair, discover_all_pairs, eligible, format_bytes,
    imdisk_list, imdisk_mount, imdisk_unmount, is_elevated, load_optional_manifests,
    make_logger, path_letter_free, powershell_disks, plan_missing_files,
    copy_only_missing, GIB,
)

VERSION = '0.2.0-alpha'


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
        self.stop_copy = threading.Event()
        self.copy_plan = None
        self.selected = set()
        self.letter = tk.StringVar(value='R')
        # Do not assume any user's source drive letter.
        self.source_root = tk.StringVar(value='')
        self.manifests_folder = tk.StringVar(value='')
        self.verify_copy = tk.BooleanVar(value=True)
        self.status = tk.StringVar(value=self.t('ready'))
        self.progress = tk.StringVar(value='0 B')
        self.copy_info = tk.StringVar(value=self.t('copy_unanalyzed'))
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
        if not self.mounted and not self.active_task:
            self.status.set(self.t('ready'))
        self.log.info('LANGUAGE_CHANGED', locale=self.language)

    def _build(self):
        self.root.geometry('1100x790')
        self.root.minsize(960, 705)
        outer = ttk.Frame(self.root, padding=12)
        outer.pack(fill='both', expand=True)
        top = ttk.Frame(outer)
        top.pack(fill='x', pady=(0, 8))
        ttk.Label(top, text='FlashBridge', font=('Segoe UI', 19, 'bold')).pack(side='left')
        self._widget(ttk.Label, top, 'tagline', foreground='#555').pack(side='left', padx=12)
        self.admin = ttk.Label(top, text='', foreground='#0A7A3E' if is_elevated() else '#B33')
        self.admin.pack(side='right', padx=5)
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
        self._widget(ttk.Label, mnt, 'mount_help', wraplength=1000).pack(anchor='w', padx=8, pady=(0, 7))

        copy = self._widget(ttk.LabelFrame, outer, 'copy_header')
        copy.pack(fill='x', pady=4)
        cr = ttk.Frame(copy)
        cr.pack(fill='x', padx=8, pady=6)
        self._widget(ttk.Label, cr, 'source_root').pack(side='left')
        ttk.Entry(cr, textvariable=self.source_root, width=34).pack(side='left', padx=6)
        self._widget(ttk.Button, cr, 'browse', command=self._choose_source).pack(side='left')
        self._widget(ttk.Checkbutton, cr, 'verify_sha', variable=self.verify_copy).pack(side='left', padx=14)
        cr2 = ttk.Frame(copy)
        cr2.pack(fill='x', padx=8)
        self.plan_copy_button = self._widget(ttk.Button, cr2, 'plan_copy', command=self._analyze_copy)
        self.plan_copy_button.pack(side='left')
        self.copy_button = self._widget(ttk.Button, cr2, 'start_copy', command=self._copy)
        self.copy_button.pack(side='left', padx=5)
        self.stop_copy_button = self._widget(ttk.Button, cr2, 'stop_copy', command=self._cancel_copy)
        self.stop_copy_button.pack(side='left')
        ttk.Label(cr2, textvariable=self.copy_info, wraplength=620).pack(side='left', padx=9)
        cr3 = ttk.Frame(copy)
        cr3.pack(fill='x', padx=8, pady=(5, 7))
        self.bar = ttk.Progressbar(cr3, mode='determinate', maximum=100)
        self.bar.pack(side='left', fill='x', expand=True)
        ttk.Label(cr3, textvariable=self.progress, width=25, anchor='e').pack(side='left', padx=6)

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
        self.copy_plan = None
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

    def _choose_source(self):
        value = filedialog.askdirectory(title=self.t('source_pick'))
        if value: self.source_root.set(value)

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
        if writable:
            confirm = simpledialog.askstring(self.t('rw_confirm_title'), self.t('rw_confirm',
                first=self.plan.first.number, size1=format_bytes(self.plan.first.size),
                second=self.plan.second.number, size2=format_bytes(self.plan.second.size)), parent=self.root)
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
                                 on_state=lambda state: self._post('server_state', state))
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
                self._post('unmount_error', output)
                raise RuntimeError(self.t('unmount_failed', error=output))
            for _ in range(20):
                if unit not in imdisk_units(imdisk_list()):
                    self._post('unmounted')
                    return
                time.sleep(.5)
            self._post('unmount_error', imdisk_list())
            raise RuntimeError(self.t('orphaned_imdisk', unit=unit))
        self._task('unmounting', work, letter=letter)

    def _analyze_copy(self):
        if not self.mounted or self.mode != 'RW': return
        src = self.source_root.get()
        target = self.mounted_letter + ':\\'
        def work():
            plan = plan_missing_files(src, target, self.log)
            self._post('copy_plan', plan)
        self._task('analyzing', work)

    def _copy(self):
        if not self.copy_plan or not self.mounted or self.mode != 'RW': return
        plan = self.copy_plan
        if plan.free_bytes is None:
            messagebox.showerror(self.t('free_unknown_title'), self.t('free_unknown'))
            return
        if plan.bytes_to_copy + 2*GIB > plan.free_bytes:
            messagebox.showerror(self.t('space_title'), self.t('space_short',
                needed=format_bytes(plan.bytes_to_copy), free=format_bytes(plan.free_bytes)))
            return
        if plan.differing_size_count or plan.over_fat32_limit:
            if not messagebox.askyesno(self.t('differences_title'), self.t('differences_confirm',
                different=plan.differing_size_count, oversize=plan.over_fat32_limit)):
                return
        if not messagebox.askyesno(self.t('copy_confirm_title'), self.t('copy_confirm',
            count=len(plan.entries), size=format_bytes(plan.bytes_to_copy))):
            return
        self.stop_copy.clear()
        verify = bool(self.verify_copy.get())
        def work():
            result = copy_only_missing(plan, verify=verify, log=self.log,
                stop=self.stop_copy,
                fault=lambda: self.server is None or self.server.failed or not self.server.ready,
                progress=lambda *args: self._post('copy_progress', *args))
            self._post('copy_finished', result['completed'], result['total_files'],
                       result['new_bytes'], result['cancelled'])
        self._task('copying', work)

    def _cancel_copy(self):
        self.stop_copy.set()
        self.log.warning('COPY_CANCEL_REQUESTED')
        self.status.set(self.t('copy_stop'))

    def _buttons(self):
        busy = self.active_task is not None
        def state(button, active): button.configure(state='normal' if active else 'disabled')
        idle = not busy and not self.mounted and not self.server
        state(self.refresh, idle)
        state(self.detect, idle and len(self.selected) == 2)
        state(self.autodetect, idle and sum(1 for d in self.disks if eligible(d)) >= 2)
        state(self.ro_button, idle and self.plan is not None)
        state(self.rw_button, idle and self.plan is not None and self.plan.read_write_safe)
        state(self.unmount_button, not busy and self.mounted)
        state(self.inspect_button, not busy)
        state(self.plan_copy_button, not busy and self.mounted and self.mode == 'RW' and not self._fault())
        state(self.copy_button, not busy and self.copy_plan is not None and self.mode == 'RW' and not self._fault())
        state(self.stop_copy_button, busy and self.active_task == 'copying')

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
            self.copy_plan = None
        elif self.mounted and self.server:
            self.status.set(self.t('proxy_live', mode=self.mode, letter=self.mounted_letter,
                connection=self.t('connected' if self.server.active else 'waiting'),
                read=format_bytes(self.server.bytes_read),
                written=format_bytes(self.server.bytes_written),
                speed=format_bytes(self.server.last_speed)))
        self._buttons()
        self.root.after(200, self._tick)

    def _action(self, a):
        key = a[0]
        if key == 'disks':
            self.disks = a[1]
            self.plan = None
            self.copy_plan = None
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
            self.copy_plan = None
            if self.server:
                self.server.stop()
                if not self.server.active:
                    self.server.join(5)
                    if not self.server.is_alive():
                        self.server.close_devices()
                        self.server = None
            self.status.set(self.t('unmounted_ok'))
        elif key == 'unmount_error':
            self.status.set(self.t('unmount_incomplete'))
        elif key == 'task_error':
            self.status.set(self.t('task_error', message=a[1]))
            messagebox.showerror(self.t('task_error_title'), a[1])
        elif key == 'task_finished':
            self.active_task = None
        elif key == 'imdisk':
            messagebox.showinfo('ImDisk', a[1] or self.t('imdisk_none'))
        elif key == 'copy_plan':
            self.copy_plan = p = a[1]
            self.copy_info.set(self.t('copy_summary', missing=len(p.entries),
                size=format_bytes(p.bytes_to_copy), existing=p.existing_count,
                different=p.differing_size_count, oversize=p.over_fat32_limit,
                free=format_bytes(p.free_bytes)))
        elif key == 'copy_progress':
            done, total, nbytes, all_bytes, _target = a[1:]
            self.bar['value'] = 100 * nbytes / all_bytes if all_bytes else 100
            self.progress.set(self.t('copy_progress', done=done, total=total,
                                     bytes=format_bytes(nbytes)))
        elif key == 'copy_finished':
            done, total, nbytes, cancelled = a[1:]
            self.copy_plan = None
            self.copy_info.set(self.t('copy_result', status=self.t('stopped' if cancelled else 'completed'),
                done=done, total=total, bytes=format_bytes(nbytes)))
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
