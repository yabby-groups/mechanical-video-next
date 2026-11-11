#!/usr/bin/env -S uv run python
"""Register a local GLB/glTF/Blend with provenance; no unlicensed network scraping."""
import argparse
import json
from pathlib import Path
import shutil
from common import BLENDER, ROOT, digest, filehash, run, writejson

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('source',type=Path)
    ap.add_argument('--origin',required=True,help='Authoritative model URL or owned asset provenance')
    ap.add_argument('--license',required=True,help='Declared SPDX identifier; verify the actual grant yourself')
    ap.add_argument('--version',required=True)
    args=ap.parse_args()
    source=args.source.resolve(strict=True)
    if args.license.lower() in ['unknown','none','unlicensed','noassertion']:
        ap.error('Unknown license: do not import into production assets')
    if source.suffix.lower() not in ['.blend','.glb']: ap.error('Use self-contained GLB or Blend; pack external glTF buffers first')
    key=digest({'content':filehash(source),'origin':args.origin,'license':args.license,'version':args.version})
    target=ROOT/'assets/assemblies'/key
    receipt=target/'provenance.json'
    if receipt.exists():
        m=json.loads(receipt.read_text())
        if all((target/n).is_file() and filehash(target/n)==h for n,h in m['artifacts'].items()):
            print(json.dumps({'cache_hit':True,'asset':str(target)}))
            return
        raise RuntimeError('Registered asset integrity failure; preserve evidence and re-import to a new version')
    # Validation happens in work first. Failed imports never become approved assets.
    folder=ROOT/'work/imports'/key
    folder.mkdir(parents=True,exist_ok=True)
    run([BLENDER,'-b','--factory-startup','--python-exit-code','1','--python',ROOT/'blender/import_asset.py','--',source,folder/'assembly.blend'],folder/'import.log')
    target.mkdir(parents=True,exist_ok=False)
    shutil.copy2(source,target/('source'+source.suffix.lower()))
    for name in ['assembly.blend','assembly.inventory.json']: shutil.copy2(folder/name,target/name)
    writejson(target/'provenance.json',{'source':args.origin,'original_path':str(source),'sha256':filehash(source),'license_declared':args.license,'version':args.version,'scientific_acceptance':False,'artifacts':{n:filehash(target/n) for n in ['assembly.blend','assembly.inventory.json','source'+source.suffix.lower()]}})
    print(target)

if __name__=='__main__': main()
