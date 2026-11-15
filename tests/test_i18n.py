"""No GUI display, devices, ImDisk, or network required."""
import sys
from pathlib import Path
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from flashbridge_i18n import EN, CS, translate, supported_languages


class InternationalizationTests(unittest.TestCase):
    def test_english_is_primary_language(self):
        self.assertEqual(translate('refresh'), 'Refresh disks')
        self.assertEqual(supported_languages(), ('en', 'cs'))

    def test_czech_gui_is_available(self):
        self.assertEqual(translate('refresh', 'cs'), 'Obnovit disky')
        self.assertEqual(translate('rw_token', 'cs'), 'ZAPIS')
        self.assertEqual(translate('rw_token', 'en'), 'WRITE')

    def test_identical_keysets_and_matching_placeholders(self):
        from string import Formatter
        self.assertEqual(EN.keys(), CS.keys())
        for key in EN:
            eng = {f for _, f, _, _ in Formatter().parse(EN[key]) if f is not None}
            cze = {f for _, f, _, _ in Formatter().parse(CS[key]) if f is not None}
            self.assertEqual(eng, cze, key)

    def test_dynamic_values(self):
        self.assertIn('Q:', translate('letter_taken', 'en', letter='Q'))
        self.assertIn('Q:', translate('letter_taken', 'cs', letter='Q'))


if __name__ == '__main__':
    unittest.main()
