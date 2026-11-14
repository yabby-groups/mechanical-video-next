#!/usr/bin/env -S uv run python
"""Render typography on actual cached video poses, without CAD/TTS/Blender.

This local acceptance harness keeps legacy timing provenance UNKNOWN. It does
not upgrade proportional historical subtitle splits to verified alignment.
"""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from mechanical_video_next.qa_images import prepare_image, sha
from mechanical_video_next.style_lock import compare_frames, verify_lock
from mechanical_video_next.text_layout import prepare_text_props, normalize_cues


def run(args):
    subprocess.run([str(x) for x in args], check=True, capture_output=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--task', type=Path, required=True)
    ap.add_argument('--output', type=Path, required=True)
    ap.add_argument('--resume', action='store_true')
    args = ap.parse_args()
    out = args.output.resolve(); out.mkdir(parents=True, exist_ok=args.resume)
    task = args.task.resolve()
    timeline = json.loads((task/'shared/timeline.json').read_text())
    legacy = json.loads((task/'editor/original-style-text-v1/single-line-timing.v3.json').read_text())['captions']
    raw_dir = task/'animation/v9/rendered/shots'
    protected = [*raw_dir.glob('*.mp4'), * (task/'shared').glob('*.wav'),
                 *task.rglob('final.mp4'), *ROOT.glob('assets/assemblies/**/*.step'),
                 *ROOT.glob('output/**/*cover*.png')]
    hashes = {str(p):sha(p) for p in protected}
    public = ROOT/'remotion/public/cache/text-readability'; public.mkdir(parents=True, exist_ok=True)
    entries = [('opening', 1.5), ('chapter', 29.5),
               ('longest', (max(legacy, key=lambda c:len(c['text']))['start_frame']+1)/30),
               ('dense-label', 48.9), ('core-contact', 64.283), ('ending', 143.5)]
    manifest = []
    for name, time in entries:
        shot = next(s for s in timeline['shots'] if s['start'] <= time < s['end'])
        base = out/f'{name}-source.png'
        run(['ffmpeg','-v','error','-ss',time-shot['start'],'-i',raw_dir/f"{shot['shot_id']}.mp4",'-frames:v','1','-y',base])
        dest = public/base.name; shutil.copy2(base, dest)
        cue = next(c for c in legacy if c['start_frame']/30 <= time < c['end_frame']/30)
        props = dict(title='02 从送料到折脚 · 原理示意', subtitle='', shots=[dict(id=name,
            label='', note='', seconds=1,media=f'cache/text-readability/{base.name}',kind='image',
            audio='cache/text-readability/audio.wav',accent='#ffffff')],
            cues=[dict(start=0,end=1,text=cue['text'])],duration=1,fps=30,width=1920,height=1080,
            presentation='mechanism-fullframe',fullframe_caption='原理示意',
            annotations=[dict(layer='part', text='推块 / 送料 · 钉条 / 送料' if name=='chapter' else '驱动片 · 钉冠 · 钉脚 · 砧座',start=0,end=1)])
        props = prepare_text_props(props)
        (out/f'{name}.props.json').write_text(json.dumps(props,ensure_ascii=False))
        manifest.append(dict(name=name,time=time,shot_id=shot['shot_id'],source=str(base),
            props=str(out/f'{name}.props.json'),cue_text=cue['text'],
            timing_provenance='UNCHANGED_LEGACY_PROPORTIONAL_TIMING_UNVERIFIED'))
    shutil.copy2(task/'shared/s01.wav',public/'audio.wav')
    # A real moving cached shot, with its existing measured audio and cues.
    moving = next(s for s in timeline['shots'] if s['shot_id']=='s04')
    shutil.copy2(raw_dir/'s04.mp4',public/'motion.mp4')
    shutil.copy2(task/'shared/s04.wav',public/'motion.wav')
    motion_props = dict(props, duration=3, shots=[dict(props['shots'][0],seconds=3,
        media='cache/text-readability/motion.mp4',kind='video',audio='cache/text-readability/motion.wav')],
        cues=[dict(text=c['text'],start=max(0,c['start']-moving['start']),end=min(3,c['end']-moving['start']))
              for c in timeline['cues'] if c['end']>moving['start'] and c['start']<moving['start']+3],
        annotations=[dict(layer='part',text='推块 / 送料 · 钉条 / 送料',start=0,end=3)])
    motion_props=prepare_text_props(motion_props)
    (out/'motion.props.json').write_text(json.dumps(motion_props,ensure_ascii=False))
    (out/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2))
    # Bundle each real renderer once. Old entry is an exact tracked-source copy.
    old_entry=ROOT/'remotion/src/__text_legacy_qa.tsx'
    shutil.copy2(ROOT/'assets/style-reference/approved-renderer.tsx',old_entry)
    node = """const fs=require('fs');const {bundle}=require('@remotion/bundler');
const {selectComposition,renderStill,renderMedia}=require('@remotion/renderer');
(async()=>{const out=process.argv[1];const rows=JSON.parse(fs.readFileSync(out+'/manifest.json'));
for(const [tag,entry] of [['before','src/__text_legacy_qa.tsx'],['after','src/index.tsx']]){
 const url=await bundle({entryPoint:entry,publicDir:'public'});
 for(const row of rows){if(tag==='before' && fs.existsSync(out+'/'+row.name+'-before.png'))continue;const inputProps=JSON.parse(fs.readFileSync(row.props));
 const opts={serveUrl:url,id:'Mechanical',inputProps,browserExecutable:'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'};
 const composition=await selectComposition(opts);
 await renderStill({...opts,composition,output:out+'/'+row.name+'-'+tag+'.png',frame:0,imageFormat:'png'});
 }
 if(tag==='after'){
 const inputProps=JSON.parse(fs.readFileSync(out+'/motion.props.json'));
 const opts={serveUrl:url,id:'Mechanical',inputProps,browserExecutable:'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'};
 const composition=await selectComposition(opts);
 await renderMedia({...opts,composition,outputLocation:out+'/motion.mp4',codec:'h264',crf:18,concurrency:2});
 }
}})().catch(e=>{console.error(e.message);process.exit(1)})"""
    try:
        subprocess.run(['node','-e',node,str(out)],cwd=ROOT/'remotion',check=True)
    finally:
        old_entry.unlink(missing_ok=True)
    masks = [[64,38,1856,142],[64,162,1856,282],[64,288,1856,360],[90,940,1830,1040]]
    for row in manifest:
        name=row['name']
        row['non_text_regression']=compare_frames(out/f'{name}-before.png',out/f'{name}-after.png',masks)
        row['phones']=[]
        for width in (360,390,430):
            p=out/f'{name}-{width}.png'
            with Image.open(out/f'{name}-after.png') as im:
                im.resize((width,round(width*1080/1920)),Image.Resampling.LANCZOS).save(p)
            row['phones'].append(prepare_image(p,max_size=width))
    sheets=[]
    for i in range(3):
        sheet=Image.new('RGB',(1180,550),'#cccccc');draw=ImageDraw.Draw(sheet)
        for y,row in enumerate(manifest[2*i:2*i+2]):
            x=0
            for width in (360,390,430):
                with Image.open(out/f"{row['name']}-{width}.png") as im:sheet.paste(im,(x,y*275+25))
                draw.text((x+4,y*275+4),f"{row['name']} {width}px",fill='black');x+=width
        path=out/f'phone-sheet-{i+1}.png';sheet.save(path)
        sheets.append(prepare_image(path,max_size=1280))
    blocked=[]
    for i,cue in enumerate(timeline['cues']):
        try:normalize_cues([cue])
        except ValueError as error:blocked.append(dict(index=i,text=cue['text'],reason=str(error)))
    run(['ffmpeg','-v','error','-xerror','-i',out/'motion.mp4','-f','null','-'])
    report=dict(code_sha256={str(p.relative_to(ROOT)):sha(p) for p in [ROOT/'remotion/src/index.tsx',ROOT/'remotion/src/TextOverlay.tsx',ROOT/'config/text-style.json',ROOT/'mechanical_video_next/text_layout.py']},samples=manifest,sheets=sheets,motion_video=str(out/'motion.mp4'),
        motion_sha256=sha(out/'motion.mp4'),motion_full_decode='PASS',protected_files=len(hashes),
        protected_unchanged=all(sha(p)==h for p,h in hashes.items()),
        style_lock=verify_lock(ROOT/'assets/style-reference/style-lock.json'),
        historical_unsplit_cues_blocked=blocked, legacy_cues_single_line=len(legacy),
        continuous_viewing='UNKNOWN',listening='UNKNOWN',platform_ui='UNKNOWN',
        timing_alignment='UNKNOWN: existing proportional splits retained for diagnostic only',
        exact_screenshot_version='UNKNOWN',status='DIAGNOSTIC_NOT_FORMAL_ACCEPTANCE')
    (out/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
    print(json.dumps(dict(report=str(out/'report.json'),sheets=[s['qa_path'] for s in sheets])))


if __name__=='__main__':main()
