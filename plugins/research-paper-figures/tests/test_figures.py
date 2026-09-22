"""Offline tests for the portable figure package."""

import csv
import importlib.util
import re
import sys
import tempfile
import unittest
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib as mpl
import numpy as np
from matplotlib.colors import to_rgb
from PIL import Image

SKILL = Path(__file__).resolve().parents[1] / 'skills' / 'research-paper-figures'
sys.path.insert(0, str(SKILL / 'assets'))
sys.path.insert(0, str(SKILL / 'scripts'))
from figstyle import SIGNED, WARM, cell_text_color
from build_gallery import make_contact_sheets

spec = importlib.util.spec_from_file_location('category_comparison', SKILL / 'assets' / 'category-comparison.py')
category = importlib.util.module_from_spec(spec)
spec.loader.exec_module(category)


class FigureTests(unittest.TestCase):
    def test_annotations_have_readable_contrast(self):
        def luminance(color):
            channels = np.array(to_rgb(color))
            linear = np.where(channels <= .04045, channels / 12.92, ((channels + .055) / 1.055) ** 2.4)
            return linear @ np.array([.2126, .7152, .0722])

        for cmap in (WARM, SIGNED):
            for value in np.linspace(0, 1, 256):
                background = cmap(value)
                low, high = sorted((luminance(background), luminance(cell_text_color(background))))
                self.assertGreaterEqual((high + .05) / (low + .05), 4.5)

    def test_contact_sheet_uses_discovered_fonts(self):
        with tempfile.TemporaryDirectory() as directory, mpl.rc_context({'font.serif': ['DejaVu Serif']}):
            output = Path(directory)
            entries = []
            for i in range(8):
                stem = f'figure-{i}'
                Image.new('RGB', (100, 60), 'white').save(output / f'{stem}.png')
                entries.append({'id': stem, 'title': f'Example {i}', 'backend': 'Test'})
            make_contact_sheets(output, entries)
            for name in ('gallery-1.png', 'gallery-2.png'):
                with Image.open(output / name) as image:
                    self.assertEqual(image.size, (1800, 1180))

    def test_category_rejects_duplicate_and_missing_cells(self):
        header = ['panel', 'method', 'condition', 'score', 'xlabel']
        rows = [['A', 'Method', 'Clean', '.8', 'Score'],
                ['A', 'Method', 'Shifted', '.7', 'Score'],
                ['B', 'Method', 'Clean', '.6', 'Score'],
                ['B', 'Method', 'Shifted', '.5', 'Score']]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'values.csv'
            for data in (rows + [rows[0]], rows[:-1]):
                with path.open('w', newline='') as stream:
                    writer = csv.writer(stream)
                    writer.writerow(header)
                    writer.writerows(data)
                with self.assertRaises(ValueError):
                    category.load(path)

    def test_reference_images_have_no_embedded_metadata(self):
        paths = list((SKILL / 'examples' / 'preferred').glob('*.png'))
        self.assertEqual(len(paths), 8)
        for path in paths:
            with Image.open(path) as image:
                self.assertEqual(image.info, {}, path.name)
                self.assertFalse(image.getexif(), path.name)

    def test_relative_document_links_resolve(self):
        for path in SKILL.rglob('*.md'):
            for link in re.findall(r'\]\(([^)]+)\)', path.read_text()):
                if '://' not in link and not link.startswith('#'):
                    self.assertTrue((path.parent / link.split('#')[0]).is_file(), (path.name, link))


if __name__ == '__main__':
    unittest.main()
