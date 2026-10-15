#!/usr/bin/env python3
"""Run exactly the measurement ROM in Copperline, stopping before RBCP."""
import argparse,base64,hashlib,json,os,socket,subprocess,time
from pathlib import Path
import rom_results
ROOT=Path(__file__).resolve().parent

def _sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def _popen_with_binary_hash(binary, command, **kwargs):
    # Capture provenance before launch: the build output can be replaced while
    # the emulator is still using the image it opened.
    binary_sha256=_sha256(binary)
    proc=subprocess.Popen(command,**kwargs)
    return proc,binary_sha256

def _write_invocation(out,binary,command,binary_sha256,wall_seconds):
    binary_changed=_sha256(binary)!=binary_sha256
    invocation=dict(command=command,binary_sha256=binary_sha256,
                    binary_changed_during_run=binary_changed,wall_seconds=wall_seconds)
    (out/'invocation.json').write_text(json.dumps(invocation,indent=2))
    if binary_changed:
        raise RuntimeError('Emulator binary changed during the run; capture rejected '
                           '(see invocation.json binary_changed_during_run).')

def run(binary,out,config=None,romdir=None):
    romdir=romdir or ROOT/'build/rom'
    out.mkdir(parents=True,exist_ok=False)
    manifest_path=out/'build-manifest.json'
    manifest_path.write_bytes((romdir/'manifest.json').read_bytes())
    manifest=json.loads(manifest_path.read_text())
    info=out/'control.json'
    command=[str(binary),'--factory','--model','A500','--cpu','68000','--chip','512K',
             '--slow','512K','--fast','0','--no-jit','--noaudio','--control',':0',
             '--control-info',str(info)]
    if config: command+=['--config',str(config)]
    command.append(str(romdir/'a500-timing-rom.bin'))
    env={k:v for k,v in os.environ.items() if not k.startswith('COPPERLINE_')}
    with (out/'run.log').open('w') as log:
        proc,binary_sha256=_popen_with_binary_hash(
            binary,command,cwd=out,env=env,stdout=log,stderr=subprocess.STDOUT)
        connection=None
        try:
            deadline=time.monotonic()+300
            while not info.exists():
                if proc.poll() is not None: raise RuntimeError('Emulator exited: '+(out/'run.log').read_text())
                if time.monotonic()>deadline: raise TimeoutError('Control server did not start')
                time.sleep(.1)
            details=json.loads(info.read_text())
            host,port=details['listen'].rsplit(':',1)
            connection=socket.create_connection((host,int(port)),timeout=300)
            stream=connection.makefile('rwb'); counter=0
            def rpc(method,params):
                nonlocal counter
                counter+=1
                stream.write((json.dumps(dict(jsonrpc='2.0',id=counter,method=method,params=params))+'\n').encode());stream.flush()
                while True:
                    line=stream.readline()
                    if not line: raise EOFError('Control connection closed')
                    response=json.loads(line)
                    if response.get('id')!=counter: continue
                    if 'error' in response: raise RuntimeError(response['error'])
                    return response['result']
            rpc('hello',dict(token=details['token']))
            started=time.monotonic()
            rpc('break.add',dict(kind='pc',addr=manifest['collection_done_pc']))
            stop=rpc('run_until',dict(seconds=500))
            (out/'stop.json').write_text(json.dumps(stop,indent=2))
            result=rpc('mem.read',dict(addr=manifest['result_address'],len=manifest['result_bytes'],encoding='base64'))
            (out/'memory-response-fields.json').write_text(json.dumps(list(result.keys())))
            data=base64.b64decode(result['data'])
            capture=out/'capture.bin';capture.write_bytes(data)
            rom_results.extract(capture,out,manifest=manifest_path)
            rpc('step',dict(count=3))
            rpc('capture.screenshot',dict(path=str(out/'screen.png')))
            _write_invocation(out,binary,command,binary_sha256,time.monotonic()-started)
            rpc('shutdown',{})
            proc.wait(timeout=20)
        finally:
            if connection: connection.close()
            if proc.poll() is None: proc.terminate();proc.wait(timeout=20)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--binary',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    p.add_argument('--config',type=Path);p.add_argument('--romdir',type=Path);a=p.parse_args();run(a.binary.resolve(),a.out.resolve(),a.config.resolve() if a.config else None,a.romdir.resolve() if a.romdir else None)
