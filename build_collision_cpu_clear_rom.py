"""Kind107: beam polling versus fixed ROM instructions under bitplane DMA."""
import argparse
from pathlib import Path
import shutil

import build_irq_stage_rom as base
import build_playfield_modes_rom as modes


def trials():
    return [(107, target, dual | (fixed << 2) | (off << 3), 2, pad, repeat)
            for target in (8, 12) for fixed in range(2) for off in range(2)
            for dual in range(2) for pad in (range(4) if not fixed else (0, 3)) for repeat in range(2)]


def observer(fixed, off, pad):
    address = (0xffb400 + (off * 2 + pad // 3) * 0x200 if fixed
               else 0xffb000 + (off * 4 + pad) * 0x80)
    prefix = f"""        dcb.b ${address:x}-*,0
observer_{fixed}_{off}_{pad}:
        move.w 6(a6),d3
        move.w #${0x8200 if off else 0x8300:x},$96(a6)
"""
    if fixed:
        wait = f"""        rept {182 + pad * 4}
        nop
        endr
"""
    else:
        wait = f""".poll:
        move.w 6(a6),d0
        cmpi.w #${0x4410 + pad * 8:x},d0
        bcs.s .poll
"""
    clear = '        move.w 6(a6),14(a4)'
    return prefix + wait + clear + modes.OBSERVER.split(clear, 1)[1]


def transform(stage):
    shutil.copyfile(__file__, stage / Path(__file__).name)
    shutil.copyfile(modes.__file__, stage / Path(modes.__file__).name)
    p = stage / 'src/rom/experiment.asm'
    text = p.read_text()
    assert text.count('cmpi.w #49,(a4)') == 1
    p.write_text(text.replace('cmpi.w #49,(a4)', 'cmpi.w #107,(a4)'))
    setup = '''        moveq #0,d0
        move.w 8(a4),d0
        btst #2,5(a4)
        bne.s .fixed_address
        lsl.l #7,d0
        addi.l #$ffb000,d0
        btst #3,5(a4)
        beq.s .address_ready
        addi.l #$200,d0
        bra.s .address_ready
.fixed_address:
        tst.w d0
        beq.s .fixed_zero
        move.w #1,d0
.fixed_zero:
        lsl.l #8,d0
        add.l d0,d0
        addi.l #$ffb400,d0
        btst #3,5(a4)
        beq.s .address_ready
        addi.l #$400,d0
.address_ready:
        movea.l d0,a3
'''
    kernel = modes.KERNEL.replace('        jsr sync_beam', setup + '        jsr sync_beam')
    kernel = kernel.replace('blitter_handoff_trial:\n',
                            'blitter_handoff_trial:\n        movem.l d7/a3,-(sp)\n')
    kernel = kernel.replace('        rts', '        movem.l (sp)+,d7/a3\n        rts')
    kernel = kernel.replace('        jsr $ffb000', '        nop\n        jsr (a3)')
    (stage / 'src/rom/blitter_handoff_kernel.i').write_text(kernel)
    (stage / 'src/rom/blitter_handoff_observer.i').write_text(
        ''.join(observer(fixed, off, pad) for fixed in range(2) for off in range(2)
                for pad in (range(4) if not fixed else (0, 3))))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--vasm', required=True)
    p.add_argument('--wsl', action='store_true')
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    base.build(a.vasm, a.wsl, a.out, rows=trials(), transform=transform,
               profile=dict(kind=107, variants='bit0 DPF; bit2 fixed NOPs; bit3 DMA off',
                            fields={'12': 'observer entry', '14': 'pre-clear beam',
                                    '20': 'CLXDAT', '22': 'second CLXDAT',
                                    '26': 'pre-read beam', '34': 'post-read beam'},
                            limitations='Raw VHPOSR words; exact entry qualification; no alignment. '
                            'Two mask targets, constant plane pattern2, transparent sprite. '
                            'Polling thresholds4410/4418/4420/4428; fixed182/194 NOPs; immediate DMACON writes match original opcodes.'))
