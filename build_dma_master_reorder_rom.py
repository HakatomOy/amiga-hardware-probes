"""Reorder kind113 cases without changing the original observer or kernel."""
import argparse
from pathlib import Path
import shutil

import build_dma_master_boundary_rom as master


def trials():
    rows = master.trials()
    order = {phase: slot for slot, phase in enumerate((1, 3, 0, 2))}
    return sorted(rows, key=lambda row: (row[2], order[row[3]], row[5]))


def transform(stage):
    master.transform(stage)
    shutil.copyfile(__file__, stage / Path(__file__).name)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--vasm', required=True)
    p.add_argument('--wsl', action='store_true')
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    master.base.build(a.vasm, a.wsl, a.out, rows=trials(), transform=transform,
                      profile=dict(kind=113,
                                   variants='Original1 inert write;3 COPJMP; phase order1,3,0,2',
                                   fields={'12': 'input beam', '24': 'original post-write beam',
                                           '16': 'finite Copper completion bit2'},
                                   limitations='32 original case IDs; observer and kernel unchanged. '
                                   'Only table order/source identity changes. Record-slot address and prior history '
                                   'also change; integer input is not complete CPU phase qualification.'))
