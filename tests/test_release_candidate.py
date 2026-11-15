"""Release-candidate regression guards; no physical disks or GUI display needed."""
from pathlib import Path
from unittest.mock import patch
import unittest
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import flashbridge_gui as gui
from flashbridge_i18n import EN, CS, translate

class Recorder:
    def __init__(self): self.events = []
    def info(self,*args,**kw): self.events.append(('info',args,kw))
    def warning(self,*args,**kw): self.events.append(('warning',args,kw))

class ReleaseCandidateTests(unittest.TestCase):
    def _app(self):
        obj = gui.BridgeApp.__new__(gui.BridgeApp)
        obj.active_task = None
        obj.mounted = True
        obj.mounted_letter = 'R'
        obj.imdisk_unit = 0
        obj.log = Recorder()
        obj.received = []
        obj._post = lambda *args: obj.received.append(args)
        obj._task = lambda _label, fn, **_kw: fn()
        return obj

    def test_refused_normal_unmount_preserves_virtual_device(self):
        app = self._app()
        with patch.object(gui,'imdisk_unmount',return_value=(5,'in use')) as command,\
             patch.object(gui,'imdisk_list',return_value=r'\Device\ImDisk0'):
            app._unmount()
        command.assert_called_once_with('R')
        self.assertEqual(app.received,[('unmount_error','in use')])
        self.assertTrue(app.mounted)
        self.assertTrue(any(e[1][0] == 'UNMOUNT_BUSY' for e in app.log.events))

    def test_normal_unmount_success_requires_absent_original_unit(self):
        app = self._app()
        with patch.object(gui,'imdisk_unmount',return_value=(0,'success')) as command,\
             patch.object(gui,'imdisk_list',return_value=''):
            app._unmount()
        command.assert_called_once_with('R')
        self.assertEqual(app.received,[('unmounted',)])

    def test_nonzero_exit_but_unit_absent_can_still_signal_success(self):
        app = self._app()
        with patch.object(gui,'imdisk_unmount',return_value=(2,'not found')),\
             patch.object(gui,'imdisk_list',return_value=''):
            app._unmount()
        self.assertEqual(app.received,[('unmounted',)])

    def test_copy_wizard_not_exposed_in_gui(self):
        source = (Path(gui.__file__)).read_text(encoding='utf-8')
        self.assertNotIn('plan_missing_files', source)
        self.assertNotIn('copy_only_missing', source)
        self.assertNotIn('plan_copy_button', source)
        self.assertNotIn("'copy_header'", source)

    def test_help_is_localized_and_calls_out_unmount_blockers(self):
        self.assertEqual(EN.keys(),CS.keys())
        for lang in ('en','cs'):
            for name in ('overview','workflow','unmount','safety','diagnostics'):
                text=translate('help_text_'+name,lang,version='0.3.3-rc1')
                self.assertGreater(len(text),120)
            self.assertIn('C:',translate('unmount_busy_help',lang))

if __name__=='__main__': unittest.main()
