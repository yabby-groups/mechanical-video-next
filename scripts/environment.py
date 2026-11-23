#!/usr/bin/env -S uv run python
"""Read-only environment audit; saves evidence, installs nothing."""
import importlib.util
import json
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import time
from common import ROOT, filehash, writejson

sys.path.insert(0, str(ROOT))
from mechanical_video_next.blender_runtime import run_blender

def version(args):
    try:
        p=subprocess.run(args,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,timeout=20)
        return {'command':args,'exit_code':p.returncode,'output':p.stdout[:1500]}
    except Exception as e: return {'command':args,'error':str(e)}

def main():
    started=time.perf_counter()
    value={'platform':platform.platform(),'machine':platform.machine(),'disk':shutil.disk_usage(ROOT)._asdict(),
        'tools':{name:version(args) for name,args in {
            'ffmpeg':['ffmpeg','-version'],'ffprobe':['ffprobe','-version'],
            'uv':['uv','--version'],
            'python':['uv','run','--project',str(ROOT),'python','--version'],'node':['node','--version'],'npm':['npm','--version'],'codex':['codex','--version'],
            'remotion':['node','-p',"require('./remotion/node_modules/remotion/package.json').version"],
            'voices':['say','-v','?']}.items()},
        'optional_modules':{m:importlib.util.find_spec(m) is not None for m in ['manim','build123d','FreeCAD']},
        'vendored_files':{str(p.relative_to(ROOT)):filehash(p) for p in (ROOT/'blender/vendor').rglob('*') if p.is_file() and p.suffix in ['.py','.toml','.json']}}
    blender = run_blender(['--version'], name='environment', timeout=20, allow_failure=True)
    value['tools']['blender'] = {'command': blender['command'], 'exit_code': blender['returncode'],
                                'output': Path(blender['stdout']).read_text()[:1500],
                                'report': blender['report']}
    value['elapsed_seconds']=round(time.perf_counter()-started,3)
    previous=ROOT/'output/environment.json'
    if previous.exists():
        old=json.loads(previous.read_text())
        if 'hardware_verified' in old: value['hardware_verified']=old['hardware_verified']
    writejson(previous,value)
    print('output/environment.json')

if __name__=='__main__': main()
