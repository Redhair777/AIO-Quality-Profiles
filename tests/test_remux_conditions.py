"""Regression checks for upstream group moves and required-type semantics."""
from pathlib import Path
import sqlite3
import subprocess
import tempfile
import unittest

import convert

ROOT = Path(__file__).resolve().parents[1]


class RemuxConditionsTest(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(':memory:')
        self.addCleanup(self.db.close)
        self.db.executescript('''
            PRAGMA foreign_keys = ON;
            CREATE TABLE custom_format_conditions (
                id INTEGER PRIMARY KEY, custom_format_name TEXT, name TEXT,
                type TEXT, arr_type TEXT, negate INTEGER, required INTEGER,
                UNIQUE(custom_format_name, name));
            CREATE TABLE regular_expressions (name TEXT PRIMARY KEY, pattern TEXT);
            CREATE TABLE regular_expression_tags (regular_expression_name TEXT, tag_name TEXT);
            CREATE TABLE condition_patterns (
                custom_format_name TEXT, condition_name TEXT, regular_expression_name TEXT,
                FOREIGN KEY(custom_format_name, condition_name)
                REFERENCES custom_format_conditions(custom_format_name, name)
                ON DELETE CASCADE ON UPDATE CASCADE);
            CREATE TABLE quality_profile_custom_formats (
                quality_profile_name TEXT, custom_format_name TEXT, arr_type TEXT, score INTEGER);
            CREATE TABLE quality_profiles (name TEXT PRIMARY KEY);
            INSERT INTO quality_profiles VALUES ('1080p Remux');
        ''')
        for table, columns in {
            'resolutions': 'resolution TEXT', 'sources': 'source TEXT',
            'quality_modifiers': 'quality_modifier TEXT', 'release_types': 'release_type TEXT',
            'indexer_flags': 'flag TEXT',
            'languages': 'language_name TEXT, except_language INTEGER',
            'years': 'min_year INTEGER, max_year INTEGER',
        }.items():
            self.db.execute(f'CREATE TABLE condition_{table} '
                            f'(custom_format_name TEXT, condition_name TEXT, {columns})')
        for name in ['Remux', 'SiCFoI', 'ATELiER', 'BTN']:
            self.db.execute('INSERT INTO regular_expressions VALUES (?, ?)',
                            (name, rf'\b{name}\b'))
            if name != 'Remux':
                self.db.execute('INSERT INTO regular_expression_tags VALUES (?, ?)',
                                (name, 'Release Group'))
        for tier, names in [('Remux Tier 3', ['SiCFoI', 'ATELiER']),
                            ('Remux Tier 4', ['BTN'])]:
            for name in ['Remux'] + names:
                self.db.execute('INSERT INTO custom_format_conditions '
                                '(custom_format_name,name,type,arr_type,negate,required) '
                                'VALUES (?,?,?,\'all\',0,?)',
                                (tier, name, 'release_title' if name == 'Remux' else 'release_group',
                                 int(name == 'Remux')))
                self.db.execute('INSERT INTO condition_patterns VALUES (?,?,?)', (tier, name, name))
            self.db.execute('INSERT INTO custom_format_conditions '
                            '(custom_format_name,name,type,arr_type,negate,required) '
                            'VALUES (?,\'Not DVD\',\'source\',\'all\',1,1)', (tier,))
            self.db.execute('INSERT INTO condition_sources VALUES (?,\'Not DVD\',\'dvd\')', (tier,))
            self.db.execute('INSERT INTO quality_profile_custom_formats VALUES (?,?,\'all\',?)',
                            ('1080p Remux', tier, 300 if tier.endswith('3') else 200))

    def migrate(self):
        self.db.executescript((ROOT / 'tests/fixtures/move-sicfoi.sql').read_text())

    def test_move_preserves_link_and_selects_new_tier_on_both_sides(self):
        self.migrate()
        conditions = convert.load_conditions(self.db)
        patterns = convert.load_patterns(self.db)
        regexes = convert.load_regexes(self.db)
        for side in ['radarr', 'sonarr']:
            for tier, expected in [('Remux Tier 3', False), ('Remux Tier 4', True)]:
                expr = convert.build_expression(conditions, tier, side, patterns, regexes, set(), set())
                self.assertEqual('SiCFoI' in expr, expected)
        self.assertEqual(patterns['Remux Tier 4\x00SiCFoI'], 'SiCFoI')
        # Only the conversion view changes; source data retains its original type.
        self.assertEqual(self.db.execute("SELECT type FROM custom_format_conditions WHERE "
                                        "custom_format_name='Remux Tier 4' AND name='SiCFoI'")
                         .fetchone()[0], 'release_title')

    def test_upstream_corrected_type_is_already_supported(self):
        self.migrate()
        self.db.execute("UPDATE custom_format_conditions SET type='release_group' "
                        "WHERE custom_format_name='Remux Tier 4' AND name='SiCFoI'")
        self.assertEqual(next(c for c in convert.load_conditions(self.db)['Remux Tier 4']
                              if c['name'] == 'SiCFoI')['type'], 'release_group')

    def test_future_shadowed_group_stops_conversion(self):
        self.db.execute("UPDATE custom_format_conditions SET type='release_title' "
                        "WHERE name='BTN'")
        with self.assertRaisesRegex(convert.CFError, "BTN.*ignored"):
            convert.load_conditions(self.db)

    def test_required_conditions_follow_arr_rule(self):
        # Radarr/Sonarr SpecificationMatchesGroup: no required failure and
        # at least one match. A passing required atom supplies that match.
        atoms = [
            {'required': True, 'negate': False, 'sel': 'regexMatched(BASE, "Remux")'},
            {'required': False, 'negate': False, 'sel': 'regexMatched(BASE, "SiCFoI")'},
        ]
        self.assertEqual(convert.group_expression(atoms, 'streams'),
                         'regexMatched(streams, "Remux")')

    def test_different_arr_sides_do_not_trigger_false_alarm(self):
        self.db.execute("UPDATE custom_format_conditions SET type='release_title', "
                        "arr_type='sonarr' WHERE name='BTN'")
        self.db.execute("UPDATE custom_format_conditions SET arr_type='radarr' "
                        "WHERE name='Remux'")
        convert.load_conditions(self.db)

    def test_generated_move_with_real_aiostreams_evaluator(self):
        if not (ROOT / 'tools/verify/dist/vendor/streamExpression.js').exists():
            self.skipTest('build tools/verify first to run the AIOStreams evaluator')
        self.migrate()
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory)
            stats = convert.convert_profile(
                self.db, '1080p Remux', out, convert.load_conditions(self.db),
                convert.load_patterns(self.db), convert.load_regexes(self.db), set())
            self.assertEqual(stats['skipped'], [])
            result = subprocess.run(['node', str(ROOT / 'tools/verify/verify-remux.mjs'),
                                     str(out)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_skipped_format_fails_command(self):
        self.db.execute("DELETE FROM condition_patterns WHERE condition_name='BTN'")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'snapshot.sqlite'
            snapshot = sqlite3.connect(path)
            # Commit the fixture before copying its SQLite connection.
            self.db.commit()
            self.db.backup(snapshot)
            snapshot.close()
            result = subprocess.run(
                ['python3', str(ROOT / 'convert.py'), '--db', str(path),
                 '--out', str(Path(directory) / 'profiles')], capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('refusing to sync skipped custom formats', result.stderr)


if __name__ == '__main__':
    unittest.main()
