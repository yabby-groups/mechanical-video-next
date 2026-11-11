#!/usr/bin/env python3
"""Sentence WAV cache, measured FFmpeg timing, loudnorm and user-confirmed voice default.

HTTP synthesis never retries. An uncertain submitted request is never resubmitted.
Only audition/activation CLI calls use this module; importing it performs no I/O.
"""
import argparse
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import time
import urllib.error
import urllib.request
from common import ROOT, budget, codehash, digest, filehash, probe, run, writejson

STORE = ROOT/'assets/audio/narration'
DEFAULTS = ROOT/'config/narration-default.json'


def load_env(path):
    """Read only endpoint/key settings. Never execute a dotenv file or log secret values."""
    if not path:
        return
    for line in Path(path).read_text().splitlines():
        line=line.strip()
        if line.startswith('export '): line=line[7:]
        if '=' not in line or line.startswith('#'): continue
        k,v=line.split('=',1)
        if k.strip() in ['OPENAI_API_KEY','OPENAI_BASE_URL']:
            os.environ.setdefault(k.strip(),v.strip().strip('\"\''))


def load_profile(path):
    p=json.loads(Path(path).read_text())
    if p['model']!='qwen3-tts-flash' or p['voice'] not in {'Kai','Neil'}:
        raise ValueError('Verified profiles support qwen3-tts-flash with Kai or Neil')
    rate=p['target_speed']
    if not math.isfinite(rate) or abs(rate-1)>min(0.05,p['max_post_speed_delta'])+1e-9:
        raise ValueError('Post-synthesis speed adjustment must remain within 0.95–1.05')
    return p


def profile_hash(profile):
    return digest(profile)


def effective_profile(config):
    """Return an approved profile, or None so existing explicit legacy voice stays intact."""
    settings=json.loads(DEFAULTS.read_text())
    path=config.get('narration_profile')
    if path is None and config.get('channel')=='视频号': path=settings['default_profile']
    if path is None: return None
    p=load_profile(ROOT/path)
    if settings.get('status')!='approved' or settings.get('approved_profile_sha256')!=profile_hash(p):
        raise RuntimeError('Narration audition has not been confirmed for this exact profile')
    receipt=ROOT/settings['approved_audition']
    m=json.loads(receipt.read_text())
    if filehash(receipt)!=settings['approved_audition_sha256'] or filehash(receipt.parent/'audition.wav')!=m['audio_sha256']:
        raise RuntimeError('Approved audition integrity mismatch')
    return p


def valid(folder, names):
    manifest=folder/'complete.json'
    if not manifest.exists(): return False
    try:
        m=json.loads(manifest.read_text())
        return set(names)<=set(m) and all((folder/n).is_file() and filehash(folder/n)==h for n,h in m.items())
    except (KeyError,ValueError,OSError): return False


def seal(folder, names):
    writejson(folder/'complete.json',{n:filehash(folder/n) for n in names})


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs): return None


def request_payload(text, profile):
    if not text.strip() or len(text)>600: raise ValueError('Speech text must contain 1–600 characters')
    return {'model':profile['model'],'voice':profile['voice'],'input':text,'response_format':'wav'}


def raw_sentence(text, profile):
    payload=request_payload(text,profile)
    base=os.environ.get('OPENAI_BASE_URL') or profile['base_url']
    if not base.startswith('https://'):
        raise ValueError('Use an HTTPS speech endpoint')
    endpoint=base.rstrip('/')+'/audio/speech'
    key=digest({'endpoint':endpoint,'payload':payload})
    folder=STORE/'raw'/key
    if valid(folder,['source.wav','request.json','response.json']):
        return folder/'source.wav',True,key
    token=os.environ.get(profile['api_key_env'],'').strip()
    if not token: raise RuntimeError('Configure OPENAI_API_KEY or pass --env-file; never paste keys into chat')
    budget()
    folder.mkdir(parents=True,exist_ok=True)
    marker=folder/'submitted.json'
    # O_EXCL prevents concurrent or uncertain duplicate billed requests.
    try:
        with marker.open('x') as f:
            json.dump({'status':'submitted','time':time.time(),'request_sha256':digest(payload)},f)
    except FileExistsError:
        raise RuntimeError('Previous synthesis is unresolved; inspect submitted.json before any explicit recovery') from None
    writejson(folder/'request.json',{'endpoint':endpoint,'payload':payload})
    req=urllib.request.Request(endpoint,json.dumps(payload,ensure_ascii=False).encode(),headers={
        'Authorization':'Bearer '+token,'Content-Type':'application/json','Accept':'audio/wav'},method='POST')
    try:
        with urllib.request.build_opener(NoRedirect()).open(req,timeout=120) as response:
            data=response.read(32*1024**2+1)
            info={'http_status':response.status,'content_type':response.headers.get('Content-Type'),
                  'request_id':response.headers.get('X-Request-ID')}
    except urllib.error.HTTPError as e:
        writejson(folder/'response.json',{'http_status':e.code,'state':'failed_no_retry'})
        raise RuntimeError(f'Speech provider HTTP {e.code}; no retry was submitted') from None
    except Exception:
        raise RuntimeError('Speech provider completion uncertain; submitted marker retained, no retry') from None
    if not data or len(data)>32*1024**2: raise RuntimeError('Invalid or oversized speech response; no retry')
    source=folder/'source.wav'
    source.write_bytes(data)
    p=probe(source)
    audio=next(s for s in p['streams'] if s['codec_type']=='audio')
    if 'wav' not in p['format']['format_name'] or float(p['format']['duration'])<=0.15:
        raise RuntimeError('Provider must return a nonempty WAV; do not silently relabel compressed audio')
    info.update(codec=audio['codec_name'],sample_rate=audio['sample_rate'],bytes=len(data),duration=float(p['format']['duration']))
    writejson(folder/'response.json',info)
    seal(folder,['source.wav','request.json','response.json'])
    writejson(marker,{'status':'complete','request_sha256':digest(payload)})
    return source,False,key


def loudnorm_filter(p, measured=None):
    q=p['loudness']
    text=f'loudnorm=I={q["integrated_lufs"]}:TP={q["true_peak_dbtp"]}:LRA={q["lra"]}'
    if measured:
        text+=':'+':'.join(f'{key}={measured[value]}' for key,value in [
            ('measured_I','input_i'),('measured_TP','input_tp'),('measured_LRA','input_lra'),
            ('measured_thresh','input_thresh'),('offset','target_offset')])+':linear=true'
    return text+':print_format=json'


def measure_loudness(path, profile):
    command=['ffmpeg','-hide_banner','-nostats','-i',str(path),'-af',loudnorm_filter(profile),'-f','null','-']
    p=subprocess.run(command,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,text=True,check=True)
    match=re.search(r'\{\s*"input_i".*?\}',p.stderr,re.S)
    if not match: raise RuntimeError('FFmpeg did not return loudnorm measurements')
    values=json.loads(match.group())
    if not all(math.isfinite(float(values[k])) for k in ['input_i','input_tp','input_lra','input_thresh','target_offset']):
        raise RuntimeError('Invalid loudness measurement / silent audio')
    return values


def normalize(source, output, profile):
    measured=measure_loudness(source,profile)
    run(['ffmpeg','-v','error','-y','-i',source,'-af',loudnorm_filter(profile,measured),
         '-ar',profile['sample_rate'],'-ac',profile['channels'],'-c:a',profile['format'],output],output.with_suffix('.normalize.log'))
    after=measure_loudness(output,profile)
    target=profile['loudness']
    correction=target['integrated_lufs']-float(after['input_i'])
    applied=0.0
    # Very short speech may miss loudnorm's integrated target during its analysis window.
    # One bounded correction only, with a guarded sample limiter and another true-peak measurement.
    if 1.0<abs(correction):
        correction=max(-2.0,min(2.0,correction))
        limit=10**((target['true_peak_dbtp']-0.3)/20)
        corrected=output.with_suffix('.corrected.wav')
        run(['ffmpeg','-v','error','-y','-i',output,'-af',f'volume={correction}dB,alimiter=limit={limit}:level=false:latency=true',
             '-ar',profile['sample_rate'],'-ac',profile['channels'],'-c:a',profile['format'],corrected],output.with_suffix('.correction.log'))
        corrected.replace(output)
        applied=correction
        after=measure_loudness(output,profile)
    result={'before':measured,'after':after,'bounded_gain_correction_db':applied}
    result['strategy']='two-pass-loudnorm'
    if abs(float(after['input_i'])-target['integrated_lufs'])>1.0 or float(after['input_tp'])>target['true_peak_dbtp']+0.2:
        # A second, distinct strategy for sub-window speech / high crest factor.
        # Gently condition transients, then use measured static gain; no repeated normalization loop.
        conditioned=output.with_suffix('.conditioned.wav')
        run(['ffmpeg','-v','error','-y','-i',source,'-af','acompressor=threshold=0.125:ratio=2:attack=5:release=100:makeup=1',
             '-ar',profile['sample_rate'],'-ac',profile['channels'],'-c:a',profile['format'],conditioned],output.with_suffix('.conditioning.log'))
        conditioned_levels=measure_loudness(conditioned,profile)
        gain=target['integrated_lufs']-float(conditioned_levels['input_i'])
        if abs(gain)>20: raise RuntimeError('Abnormally quiet/loud source; refuse excessive normalization gain')
        limit=10**((target['true_peak_dbtp']-0.3)/20)
        run(['ffmpeg','-v','error','-y','-i',conditioned,'-af',f'volume={gain}dB,alimiter=limit={limit}:level=false:latency=true',
             '-ar',profile['sample_rate'],'-ac',profile['channels'],'-c:a',profile['format'],output],output.with_suffix('.static-normalize.log'))
        after=measure_loudness(output,profile)
        conditioned.unlink()
        result.update(strategy='peak-conditioning-measured-static-gain',after=after,
                      conditioned_measurement=conditioned_levels,static_gain_db=gain,strategy_attempts=[1,1])
    writejson(output.with_suffix('.loudness.json'),result)
    if abs(float(after['input_i'])-target['integrated_lufs'])>1.0 or float(after['input_tp'])>target['true_peak_dbtp']+0.2:
        raise RuntimeError('Normalized audio failed loudness / true-peak tolerance')
    if abs(float(probe(source)['format']['duration'])-float(probe(output)['format']['duration']))>1/profile['sample_rate']+1e-6:
        raise RuntimeError('Loudness processing unexpectedly changed audio duration')
    return result


def silence_trim(source, output, profile):
    # Boundary observations only; no ASR or phoneme/semantic alignment claims.
    cmd=['ffmpeg','-hide_banner','-nostats','-i',str(source),'-af','silencedetect=noise=-48dB:d=0.04','-f','null','-']
    proc=subprocess.run(cmd,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,text=True,check=True)
    duration=float(probe(source)['format']['duration'])
    events=re.findall(r'silence_(start|end):\s*([0-9.]+)',proc.stderr)
    leading=0.0; trailing=duration; open_start=None
    for kind,v in events:
        t=float(v)
        if kind=='start': open_start=t
        elif open_start is not None:
            if open_start<0.02: leading=max(0,t-0.06)
            if t>=duration-0.03: trailing=min(duration,open_start+0.10)
            open_start=None
    if open_start is not None: trailing=min(duration,open_start+0.10)
    if trailing-leading<0.15: raise RuntimeError('No measurable speech interval')
    speed=profile['target_speed']
    filters=[f'atrim=start={leading}:end={trailing}','asetpts=PTS-STARTPTS']
    if abs(speed-1)>1e-9: filters.append(f'atempo={speed}')
    run(['ffmpeg','-v','error','-y','-i',source,'-af',','.join(filters),'-ar',profile['sample_rate'],
         '-ac',profile['channels'],'-c:a',profile['format'],output],output.with_suffix('.trim.log'))
    return {'trim_start':leading,'trim_end':trailing,'source_duration':duration,'post_speed_factor':speed,
            'alignment':'FFmpeg silence boundaries with consonant guard; not forced phoneme alignment'}


def sentence(text, profile):
    raw,hit,rawkey=raw_sentence(text,profile)
    key=digest({'raw':rawkey,'profile':profile,'processing':codehash('scripts/narration.py')})
    folder=STORE/'sentences'/key
    files=['narration.wav','processing.json']
    processed_hit=valid(folder,files)
    if not processed_hit:
        folder.mkdir(parents=True,exist_ok=True)
        temp=folder/'trimmed.wav'
        alignment=silence_trim(raw,temp,profile)
        levels=normalize(temp,folder/'narration.wav',profile)
        writejson(folder/'processing.json',{'raw_key':rawkey,'alignment':alignment,'loudness':levels})
        temp.unlink()
        seal(folder,files)
    return folder/'narration.wav',{'raw_cache_hit':hit,'processed_cache_hit':processed_hit,'raw_key':rawkey,'key':key}


def synthesize_shot(shot, profile):
    key=digest({'narration':shot['narration'],'seconds':shot.get('seconds'),'profile':profile,'processing':codehash('scripts/narration.py')})
    folder=STORE/'shots'/key
    if valid(folder,['narration.wav','cues.json','audio.m4a','processing.json']):
        return folder/'audio.m4a',json.loads((folder/'cues.json').read_text()),key,True
    folder.mkdir(parents=True,exist_ok=True)
    inputs=[]; filters=[]; cues=[]; records=[]
    cursor=profile['leading_silence_seconds']
    for i,text in enumerate(shot['narration']):
        clip,receipt=sentence(text,profile)
        seconds=float(probe(clip)['format']['duration'])
        inputs+=['-i',clip]
        filters.append(f'[{i}:a]adelay={round(cursor*1000)}:all=1[a{i}]')
        cues.append({'start':round(cursor,3),'end':round(cursor+seconds,3),'text':text})
        records.append(receipt)
        cursor+=seconds+profile['pause_between_sentences_seconds']
    needed=cursor-profile['pause_between_sentences_seconds']+profile['trailing_silence_seconds']
    duration=shot.get('seconds',needed)
    if needed>duration:
        writejson(folder/'overrun.json',{'needed_seconds':needed,'shot_seconds':duration,'action':'Shorten this narration or extend only this shot; never auto-speed-fit'})
        raise RuntimeError(f'{profile["voice"]} speech needs {needed:.3f}s, shot allows {duration}s; no automatic acceleration')
    filters.append(''.join(f'[a{i}]' for i in range(len(cues)))+f'amix=inputs={len(cues)}:normalize=0,apad[out]')
    mixed=folder/'mixed.wav'
    run(['ffmpeg','-v','error','-y',*inputs,'-filter_complex',';'.join(filters),'-map','[out]','-t',duration,
         '-ar',profile['sample_rate'],'-ac',profile['channels'],'-c:a',profile['format'],mixed],folder/'mix.log')
    levels=normalize(mixed,folder/'narration.wav',profile)
    mixed.unlink()
    run(['ffmpeg','-v','error','-y','-i',folder/'narration.wav','-c:a','aac','-b:a','160k',folder/'audio.m4a'],folder/'aac.log')
    writejson(folder/'cues.json',cues)
    writejson(folder/'processing.json',{'sentences':records,'loudness':levels,'seconds':duration,'target_speed':profile['target_speed']})
    seal(folder,['narration.wav','cues.json','audio.m4a','processing.json'])
    return folder/'audio.m4a',cues,key,False


def srt_time(seconds):
    n=round(seconds*1000)
    return f'{n//3600000:02}:{n//60000%60:02}:{n//1000%60:02},{n%1000:03}'


def audition(config_path):
    cfg=json.loads(Path(config_path).read_text());profile=load_profile(ROOT/cfg['profile'])
    folder=ROOT/'output/narration-audition'/cfg['id']
    folder.mkdir(parents=True,exist_ok=True)
    clips=[]; cues=[]; offset=0; timeline=[]
    for shot in cfg['shots']:
        _,sc,key,hit=synthesize_shot(shot,profile)
        source=STORE/'shots'/key/'narration.wav'
        name=shot['id']+'.wav'
        shutil.copy2(source,folder/name)
        duration=float(probe(source)['format']['duration'])
        cues.extend(dict(c,start=round(c['start']+offset,3),end=round(c['end']+offset,3),shot=shot['id']) for c in sc)
        timeline.append({'shot':shot['id'],'start':offset,'duration':duration,'cache_hit':hit,'key':key})
        clips.append(name);offset+=duration
    (folder/'concat.txt').write_text(''.join(f"file '{n}'\n" for n in clips))
    joined=folder/'joined.wav'
    run(['ffmpeg','-v','error','-y','-f','concat','-safe','1','-i',folder/'concat.txt','-c:a','copy',joined],folder/'join.log')
    levels=normalize(joined,folder/'audition.wav',profile);joined.unlink()
    run(['ffmpeg','-v','error','-i',folder/'audition.wav','-f','null','-'],folder/'decode.log')
    (folder/'audition.srt').write_text('\n\n'.join(f'{i+1}\n{srt_time(c["start"])} --> {srt_time(c["end"])}\n{c["text"]}' for i,c in enumerate(cues))+'\n')
    receipt={'status':'AWAITING_USER_AUDITION_CONFIRMATION','profile':cfg['profile'],'profile_sha256':profile_hash(profile),
             'audio_sha256':filehash(folder/'audition.wav'),'duration':float(probe(folder/'audition.wav')['format']['duration']),
             'shots':timeline,'cues':cues,'loudness':levels,'model':profile['model'],'voice':profile['voice'],'target_speed':profile['target_speed'],
             'native_speed_control_used':False,'native_style_control_used':False,'post_speed_factor':profile['target_speed'],
             'unverified':['Human listening acceptance of warmth, emphasis, documentary style and pronunciation','Provider internal model identity is not independently observable'],
             'alignment':'Utterance-level FFprobe durations + FFmpeg silence boundaries, no ASR or phoneme forced alignment'}
    writejson(folder/'audition.json',receipt)
    print(json.dumps({'audition':str(folder.relative_to(ROOT)),'seconds':receipt['duration'],'shot_cache_hits':[s['cache_hit'] for s in timeline]},ensure_ascii=False))
    return folder/'audition.json'


def activate(receipt_path, approval_basis='listened'):
    """Call after explicit listening confirmation or an explicit default-voice selection."""
    if approval_basis not in {'listened','explicit_reference_voice_selection'}:
        raise ValueError('Unknown approval basis')
    receipt_path=Path(receipt_path).resolve()
    receipt=json.loads(receipt_path.read_text())
    profile=load_profile(ROOT/receipt['profile'])
    if receipt['profile_sha256']!=profile_hash(profile) or filehash(receipt_path.parent/'audition.wav')!=receipt['audio_sha256']:
        raise RuntimeError('Audition/profile changed; listen to the new version before activation')
    # Immutable approval evidence: ordinary cache replays may update audition.json's hit counters.
    approved=receipt_path.with_name(f'approved-{profile_hash(profile)[:12]}-{receipt["audio_sha256"][:12]}.json')
    if not approved.exists():
        writejson(approved,dict(receipt,status='APPROVED_VOICE_SELECTION',approval_basis=approval_basis))
    writejson(DEFAULTS,{'channel':'视频号','default_profile':receipt['profile'],'candidate_profile':receipt['profile'],
        'status':'approved','approved_profile_sha256':profile_hash(profile),'approved_audition':str(approved.relative_to(ROOT)),
        'approved_audition_sha256':filehash(approved),'approved_at_epoch':time.time(),'approval_basis':approval_basis})


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('command',choices=['audition','activate'])
    ap.add_argument('--config',type=Path,default=ROOT/'config/narration-audition.json')
    ap.add_argument('--env-file',type=Path)
    ap.add_argument('--receipt',type=Path)
    ap.add_argument('--confirmed-listened',action='store_true',help='Use activation only after explicit user listening confirmation')
    ap.add_argument('--confirmed-selection',action='store_true',help='Use after an explicit user instruction to set the selected reference voice as default; does not assert listening')
    args=ap.parse_args();load_env(args.env_file)
    if args.command=='audition': audition(args.config)
    elif not (args.confirmed_listened or args.confirmed_selection) or not args.receipt: ap.error('Activation requires explicit user confirmation/selection and exact --receipt')
    else: activate(args.receipt,'explicit_reference_voice_selection' if args.confirmed_selection else 'listened')

if __name__=='__main__': main()
