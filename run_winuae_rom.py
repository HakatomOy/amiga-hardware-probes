#!/usr/bin/env python3
"""Run a measurement ROM in isolated WinUAE Best Compatibility configuration."""
import argparse, hashlib, json, shutil, subprocess
from pathlib import Path
import rom_results


def _prepare_winuae_settings(out, settings_from=None):
    settings_path = out/'winuae.ini'
    if settings_from is None:
        settings_path.write_text('[WinUAE]\nDebuggerType=1\n')
        source_path = None
        source_kind = 'generated-default'
    else:
        source_path = Path(settings_from).resolve()
        if not source_path.is_file():
            raise FileNotFoundError(f'WinUAE settings file not found: {source_path}')
        shutil.copyfile(source_path, settings_path)
        source_kind = 'copied-existing-settings'
    return dict(settings_source_kind=source_kind,
                settings_source_path=str(source_path) if source_path else None,
                settings_source_sha256=hashlib.sha256(settings_path.read_bytes()).hexdigest())


def run(exe, romdir, out, settings_from=None):
    settings_from = Path(settings_from).resolve() if settings_from is not None else None
    if settings_from is not None and not settings_from.is_file():
        raise FileNotFoundError(f'WinUAE settings file not found: {settings_from}')
    out.mkdir(parents=True, exist_ok=False)
    manifest = json.loads((romdir/'manifest.json').read_text())
    shutil.copyfile(romdir/'manifest.json', out/'build-manifest.json')
    rom = out/'probe.rom'
    shutil.copyfile(romdir/'a500-timing-rom.bin', rom)
    assert hashlib.sha256(rom.read_bytes()).hexdigest() == manifest['rom_sha256']
    base, size = manifest['result_address'], manifest['result_bytes']
    fields = ['cpu_model','cpu_speed','cpu_compatible','cpu_cycle_exact',
              'cpu_memory_cycle_exact','blitter_cycle_exact','chipset',
              'chipmem_size','bogomem_size','fastmem_size','cachesize','ntsc']
    lua = f'''local frame=0
local ready=nil
local done=false
function on_uae_vsync()
 frame=frame+1
 if not ready and uae_peek_u16({base})==0x4135 and uae_peek_u16({base+62})==1 then ready=frame+3 end
 local valid=false
 if ready and frame>=ready then
  local checksum=0
  for address={base},{base+size-4},4 do checksum=(checksum+uae_peek_u16(address)*65536+uae_peek_u16(address+2))%4294967296 end
  valid=checksum==0
 end
 if not done and (valid or frame==10000) then
  done=true
  local f=assert(io.open("{out.as_posix()}/resolved.txt","w"))
'''
    for key in fields:
        lua += f'  f:write("{key}=",tostring(uae_read_config("{key}")),"\\n")\n'
    lua += f'''  f:close()
  uae_write_config('dbg "S {out.as_posix()}/capture.bin {base:x} {size:x}"')
  uae_write_config('SPC_QUIT 1')
 end
end
'''
    (out/'capture.lua').write_text(lua)
    settings_provenance = _prepare_winuae_settings(out, settings_from)
    (out/'machine.uae').write_text(f'''quickstart=a500,1
config_description=OneROM RAM probe - Best Compatibility
use_gui=no
lua={out/'capture.lua'}
warp=true
rndseed=1
gfx_api=directdraw
gfx_fullscreen_amiga=false
gfx_width_windowed=720
gfx_height_windowed=576
sound_output=interrupts
cpu_model=68000
cpu_speed=real
cpu_compatible=true
cpu_cycle_exact=true
cpu_memory_cycle_exact=true
blitter_cycle_exact=true
cachesize=0
chipset=ecs_agnus
chipmem_size=1
bogomem_size=2
fastmem_size=0
ntsc=false
nr_floppies=0
kickstart_rom_file={rom}
kickstart_ext_rom_file=
''')
    command=[str(exe),'-console','-log','-logflush','-ini',str(out/'winuae.ini'),'-f',str(out/'machine.uae'),'-G']
    startup=subprocess.STARTUPINFO();startup.dwFlags|=subprocess.STARTF_USESHOWWINDOW;startup.wShowWindow=0
    with (out/'console.bin').open('wb') as log:
        proc=subprocess.Popen(command,cwd=out,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,
            startupinfo=startup,creationflags=subprocess.CREATE_NO_WINDOW)
        try: proc.wait(timeout=240)
        finally:
            if proc.poll() is None: proc.terminate();proc.wait(timeout=20)
    invocation = dict(command=command,
                      binary_sha256=hashlib.sha256(exe.read_bytes()).hexdigest(),
                      **settings_provenance)
    (out/'invocation.json').write_text(json.dumps(invocation,indent=2))
    rom_results.extract(out/'capture.bin',out,manifest=out/'build-manifest.json')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--binary',type=Path,required=True);p.add_argument('--romdir',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    p.add_argument('--settings-from',type=Path,help='copy a previously accepted WinUAE ini into this run')
    a=p.parse_args();run(a.binary.resolve(),a.romdir.resolve(),a.out.resolve(),a.settings_from)
