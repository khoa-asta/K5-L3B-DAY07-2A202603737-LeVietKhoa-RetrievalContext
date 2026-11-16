"""Regression checks for repeat preparation; no embedding dependencies needed."""
import json
from contextlib import closing
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'starter'))
from day6_retriever import prepare_store


class PrepareTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.day6, self.snapshot = root / 'day6', root / 'snapshot'
        source = self.day6 / 'starter/.chroma'
        source.mkdir(parents=True)
        with closing(sqlite3.connect(source / 'chroma.sqlite3')) as db:
            db.execute('CREATE TABLE example (id INTEGER)')
            db.execute('INSERT INTO example VALUES (1)')
            db.commit()
        (source / 'index.bin').write_bytes(b'original index')
        result = self.day6 / 'results/baseline'
        result.mkdir(parents=True)
        (result / 'run.json').write_text(json.dumps({'signature': 'original'}), encoding='utf-8')
        (result / 'strategy_stats.json').write_text('{}', encoding='utf-8')

    def test_repeated_prepare_preserves_existing_snapshot(self):
        self.assertEqual(prepare_store(self.day6, self.snapshot), 'created')
        before = {p.name: p.read_bytes() for p in self.snapshot.iterdir()}
        self.assertEqual(prepare_store(self.day6, self.snapshot), 'reused')
        self.assertEqual(before, {p.name: p.read_bytes() for p in self.snapshot.iterdir()})
        with closing(sqlite3.connect(self.snapshot / 'chroma.sqlite3')) as db:
            self.assertEqual(db.execute('SELECT id FROM example').fetchall(), [(1,)])

    def test_incomplete_snapshot_is_preserved_and_rejected(self):
        self.snapshot.mkdir()
        marker = self.snapshot / 'partial.bin'
        marker.write_bytes(b'preserve')
        with self.assertRaisesRegex(ValueError, 'Incomplete snapshot'):
            prepare_store(self.day6, self.snapshot)
        self.assertEqual(marker.read_bytes(), b'preserve')

    def test_changed_day6_run_requires_new_snapshot(self):
        prepare_store(self.day6, self.snapshot)
        run = self.day6 / 'results/baseline/run.json'
        run.write_text(json.dumps({'signature': 'changed'}), encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'differs from the Day 6 run'):
            prepare_store(self.day6, self.snapshot)
        self.assertEqual(json.loads((self.snapshot / 'run.json').read_text(encoding='utf-8')),
                         {'signature': 'original'})


if __name__ == '__main__':
    unittest.main()
