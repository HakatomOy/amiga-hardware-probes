import unittest
import build_playfield_modes_rom as probe
from tools.playfield_mode_fixture import consensus

class PlayfieldFixtureTests(unittest.TestCase):
    def test_export_requires_complete_independently_repeated_consensus(self):
        rows=[dict(zip(('kind','target','variant','phase','delay','repeat'),r),counter=0) for r in probe.trials()]
        self.assertEqual(len(consensus([rows,rows])),256)
        with self.assertRaisesRegex(ValueError,'two runs'):consensus([rows])
        with self.assertRaisesRegex(ValueError,'incomplete'):consensus([rows[:-4],rows[:-4]])
        changed=[dict(row) for row in rows];changed[0]['counter']=1
        with self.assertRaisesRegex(ValueError,'conflicting'):consensus([rows,changed])
