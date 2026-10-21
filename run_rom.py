#!/usr/bin/env python3
"""Run exactly the measurement ROM in Copperline, stopping before RBCP."""
import argparse,base64,hashlib,json,os,socket,struct,subprocess,time
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

def load_emulator_environment(path):
    settings = json.loads(Path(path).read_text(encoding='utf-8'))
    if not isinstance(settings, dict) or any(
            not isinstance(key, str) or not key.startswith('COPPERLINE_')
            or not isinstance(value, str) for key, value in settings.items()):
        raise ValueError('emulator environment must map COPPERLINE_* keys to strings')
    return settings


def run(binary,out,config=None,romdir=None,seconds=500,environment_json=None):
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
    if environment_json is not None:
        settings = load_emulator_environment(environment_json)
        env.update(settings)
        (out/'emulator-environment.json').write_text(json.dumps(settings,indent=2)+'\n')
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
            stop=rpc('run_until',dict(seconds=seconds))
            (out/'stop.json').write_text(json.dumps(stop,indent=2))
            result=rpc('mem.read',dict(addr=manifest['result_address'],len=manifest['result_bytes'],encoding='base64'))
            (out/'memory-response-fields.json').write_text(json.dumps(list(result.keys())))
            data=base64.b64decode(result['data'])
            capture=out/'capture.bin';capture.write_bytes(data)
            rom_results.extract(capture,out,manifest=manifest_path)
            if 'line_c_bus_data_observer' in manifest:
                addresses=manifest['line_c_bus_data_observer']['source_addresses']
                lengths=manifest['line_c_bus_data_observer']['source_lengths']
                source_checks={}
                for channel,name in (('a','A'),('b','B'),('c','C')):
                    address=addresses[channel]
                    length=lengths[channel]
                    memory=rpc('mem.read',dict(addr=address,len=length,encoding='base64'))
                    actual=base64.b64decode(memory['data'])
                    expected=bytes(length)
                    source_checks[name]=dict(address=address,expected=expected.hex(),
                                             actual=actual.hex(),matches=actual==expected)
                second_c_address=manifest['line_c_bus_data_observer']['final_verification']['c_second_word_address']
                second_c_memory=rpc('mem.read',dict(addr=second_c_address,len=2,encoding='base64'))
                second_c_actual=base64.b64decode(second_c_memory['data'])
                source_checks['C_second_word']=dict(address=second_c_address,expected='0000',
                    actual=second_c_actual.hex(),matches=second_c_actual==b'\0\0')
                verification=manifest['line_c_bus_data_observer']['final_verification']
                result_rows=json.loads((out/'results.json').read_text())['records']
                readback_spec=manifest['line_c_bus_data_observer']['postbusy_readbacks']
                result_checks={}
                for name,spec,field in (('first_d',readback_spec['first_d'],'launch_ref'),
                                        ('second_d',readback_spec['second_d'],'end_ref')):
                    failures=[dict(record=index,descriptor=manifest['trials'][index],actual=row[field])
                              for index,row in enumerate(result_rows) if row[field]!=spec['expected']]
                    result_checks[name]=dict(address=spec['address'],field=field,
                        expected=spec['expected'],record_count=len(result_rows),
                        mismatch_count=len(failures),offenders=failures[:16],
                        matches=not failures)
                scratch_checks={}
                expected_word=struct.pack('>H',verification['pattern'])
                for address in verification['scratch_addresses']:
                    memory=rpc('mem.read',dict(addr=address,len=2,encoding='base64'))
                    actual=base64.b64decode(memory['data'])
                    scratch_checks[f'0x{address:08x}']=dict(expected=expected_word.hex(),
                                                            actual=actual.hex(),
                                                            matches=actual==expected_word)
                check_report=dict(checkpoint='collection_done',descriptor=manifest['trials'][-1],
                                  source_memory=source_checks,postbusy_d_readbacks=result_checks,
                                  scratch_words=scratch_checks)
                (out/'source-memory-check.json').write_text(json.dumps(check_report,indent=2)+'\n')
                if not all(check['matches'] for check in source_checks.values()) or \
                        not all(check['matches'] for check in scratch_checks.values()) or \
                        not all(check['matches'] for check in result_checks.values()):
                    raise RuntimeError('Kind46 source/scratch-memory verification failed at collection_done')
                prime=None
            elif 'line_c_history_observer' in manifest:
                descriptor=manifest['trials'][-1]
                pattern=manifest['line_c_history_patterns'][descriptor[2]]
                presets=manifest['line_c_history_presets']
                cfirst=presets[descriptor[1]]['c_first']
                prime=manifest['line_c_history_priming']
                expected={
                    'a': struct.pack('>8H', *([pattern['a']]*8)),
                    'b': struct.pack('>8H', *([pattern['b']]*8)),
                    'c': struct.pack('>8H',cfirst,*([0]*7)),
                }
                pattern_name=pattern['name']
                failure='Kind45 source-memory verification failed at collection_done'
            elif 'line_c_activity_observer' in manifest:
                descriptor=manifest['trials'][-1]
                prime=manifest['line_c_activity_observer']['priming']
                cfirst=manifest['line_c_activity_presets'][descriptor[1]]['c_first']
                expected={
                    'a': bytes(16),
                    'b': bytes(16),
                    'c': struct.pack('>8H',cfirst,*([0]*7)),
                }
                pattern_name='kind44-zero-prime'
                failure='Kind44 source-memory verification failed at collection_done'
            else:
                prime=None
            if prime is not None:
                checks={}
                for channel,name in (('a','A'),('b','B'),('c','C')):
                    address=prime['source_addresses'][channel]
                    memory=rpc('mem.read',dict(addr=address,len=16,encoding='base64'))
                    actual=base64.b64decode(memory['data'])
                    checks[name]=dict(address=address,expected=expected[channel].hex(),
                                      actual=actual.hex(),matches=actual==expected[channel])
                check_report=dict(checkpoint='collection_done',pattern=pattern_name,
                                  descriptor=descriptor,channels=checks)
                (out/'source-memory-check.json').write_text(json.dumps(check_report,indent=2)+'\n')
                if not all(check['matches'] for check in checks.values()):
                    raise RuntimeError(failure)
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
    p.add_argument('--config',type=Path);p.add_argument('--romdir',type=Path);p.add_argument('--seconds',type=float,default=500)
    p.add_argument('--environment-json',type=Path)
    a=p.parse_args();run(a.binary.resolve(),a.out.resolve(),a.config.resolve() if a.config else None,a.romdir.resolve() if a.romdir else None,a.seconds,a.environment_json)
