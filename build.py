#!/usr/bin/env python3
"""Build the bare-metal A500 IRQ measurement disk. Python 3.9+, vasm required."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import struct
import subprocess

ROOT = Path(__file__).resolve().parent
ADF_BYTES = 80 * 2 * 11 * 512
PROGRAM_BYTES = 32768
RESULT_SECTOR = 1536
RESULT_BYTES = 65536
RECORD_BYTES = 64
RECORD_COUNT = 4 * 6 * 16 * 2
VASM_REVISION = "a13e7e728a3dd5a9ba468bf479119e0bc23e70fd"

# Original 5x7 glyphs; no host fonts or binary assets required.
FONT = {
    ' ': [0]*7, 'A':[14,17,17,31,17,17,17], 'B':[30,17,17,30,17,17,30],
    'C':[14,17,16,16,16,17,14], 'D':[30,17,17,17,17,17,30],
    'E':[31,16,16,30,16,16,31], 'F':[31,16,16,30,16,16,16],
    'G':[14,17,16,23,17,17,15], 'H':[17,17,17,31,17,17,17],
    'I':[31,4,4,4,4,4,31], 'J':[7,2,2,2,18,18,12],
    'K':[17,18,20,24,20,18,17], 'L':[16,16,16,16,16,16,31],
    'M':[17,27,21,21,17,17,17], 'N':[17,25,21,19,17,17,17],
    'O':[14,17,17,17,17,17,14], 'P':[30,17,17,30,16,16,16],
    'Q':[14,17,17,17,21,18,13], 'R':[30,17,17,30,20,18,17],
    'S':[15,16,16,14,1,1,30], 'T':[31,4,4,4,4,4,4],
    'U':[17,17,17,17,17,17,14], 'V':[17,17,17,17,17,10,4],
    'W':[17,17,17,21,21,21,10], 'X':[17,17,10,4,10,17,17],
    'Y':[17,17,10,4,4,4,4], 'Z':[31,1,2,4,8,16,31],
    '0':[14,17,19,21,25,17,14], '1':[4,12,4,4,4,4,14],
    '2':[14,17,1,2,4,8,31], '3':[30,1,1,14,1,1,30],
    '4':[2,6,10,18,31,2,2], '5':[31,16,16,30,1,1,30],
    '6':[14,16,16,30,17,17,14], '7':[31,1,2,4,8,8,8],
    '8':[14,17,17,14,17,17,14], '9':[14,17,17,15,1,1,14],
}


def bitmap(lines):
    out = bytearray(40 * 64)
    for row, line in enumerate(lines):
        x = (40 - len(line)) // 2
        for column, char in enumerate(line):
            for y, bits in enumerate(FONT[char]):
                out[(8 + row * 12 + y) * 40 + x + column] = bits << 2
    return out


def boot_checksum(block):
    total = 0
    for offset in range(0, 1024, 4):
        if offset != 4:
            total += struct.unpack_from('>I', block, offset)[0]
            total = (total & 0xffffffff) + (total >> 32)
    return (~total) & 0xffffffff


def make_image(boot, program):
    if len(boot) > 1024 or len(program) > PROGRAM_BYTES:
        raise ValueError('Boot block or program exceeds its reserved region')
    if 1024 + PROGRAM_BYTES > RESULT_SECTOR * 512:
        raise ValueError('Program overlaps results')
    block = bytearray(boot.ljust(1024, b'\0'))
    struct.pack_into('>I', block, 4, boot_checksum(block))
    image = bytearray(ADF_BYTES)
    image[:1024] = block
    image[1024:1024+len(program)] = program
    # The empty region has deliberately no valid result magic.
    return image


def source_id():
    digest = hashlib.sha256()
    for path in sorted((ROOT / 'src').glob('*.asm')) + [ROOT / 'build.py']:
        digest.update(path.name.encode('ascii') + b'\0')
        digest.update(path.read_bytes().replace(b'\r\n', b'\n'))
    return digest.digest()


def build(assembler, wsl=False):
    output = ROOT / 'build'
    output.mkdir(exist_ok=True)
    layout = dict(PROGRAM_BYTES=PROGRAM_BYTES, RESULT_OFFSET=RESULT_SECTOR*512,
                  RESULT_BYTES=RESULT_BYTES, RECORD_BYTES=RECORD_BYTES,
                  RECORD_COUNT=RECORD_COUNT)
    (output / 'layout.i').write_text(''.join(f'{key} equ {value}\n' for key, value in layout.items()), encoding='ascii')
    (output / 'source-id.bin').write_bytes(source_id())
    for name, lines in {
        'testing': ['A500 IRQ PROBE', 'COLLECTING MEASUREMENTS', 'PLEASE WAIT'],
        'writing': ['A500 IRQ PROBE', 'WRITING RESULTS TO DISK', 'DO NOT REMOVE USB'],
        'verifying': ['A500 IRQ PROBE', 'READING RESULTS BACK', 'DO NOT REMOVE USB'],
        'success': ['A500 IRQ PROBE', 'RESULTS SAVED AND VERIFIED', 'WAIT FOR GOTEK TO BE IDLE'],
        'error': ['A500 IRQ PROBE', 'ERROR OR UNSUPPORTED MACHINE', 'CHECK INSTRUCTIONS'],
    }.items():
        (output / f'{name}.bin').write_bytes(bitmap(lines))
    for name in ('boot', 'probe'):
        options = ['-Fbin', '-m68000', '-no-opt', '-Ibuild', '-L', f'build/{name}.lst',
                   '-o', f'build/{name}.bin', f'src/{name}.asm']
        command = ['wsl', '-d', 'Ubuntu-24.04', '--exec', assembler] + options if wsl else [assembler] + options
        subprocess.run(command, cwd=ROOT, check=True)
    image = make_image((output/'boot.bin').read_bytes(), (output/'probe.bin').read_bytes())
    (output/'a500-irq-probe.adf').write_bytes(image)
    manifest = dict(layout, adf_sha256=hashlib.sha256(image).hexdigest(),
                    source_id=source_id().hex(), assembler=assembler,
                    recommended_vasm_revision=VASM_REVISION,
                    program_size=(output/'probe.bin').stat().st_size)
    (output/'manifest.json').write_text(json.dumps(manifest, indent=2)+'\n', encoding='utf-8')
    print(f"Built {output/'a500-irq-probe.adf'} ({len(image)} bytes)")
    print(f"Source ID: {manifest['source_id']}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--vasm', default=shutil.which('vasmm68k_mot') or 'vasmm68k_mot')
    parser.add_argument('--wsl', action='store_true', help='Run a Linux assembler in Ubuntu-24.04 WSL')
    args = parser.parse_args()
    build(args.vasm, args.wsl)


if __name__ == '__main__':
    main()
