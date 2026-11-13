"""Read-only media/evidence aggregation into version-bound growth deliverables.

Only ffprobe and single-frame ffmpeg extraction are executed. This is a report
adapter for existing QA, not another reviewer or a production renderer.
"""
import argparse
import copy
import json
from pathlib import Path
import subprocess
import tempfile
import time

from .multiroute import ROUTES, probe, sha, write
from .growth import finite

DIMENSIONS = {
    'opening_action': '开场机械动作', 'first_answer': '第一段答案',
    'information_progression': '章节知识推进', 'repeated_teasers': '无重复预告',
    'information_free_shots': '无信息空转', 'long_holds': '无不合理停留',
    'aha_moment': '核心知识顿悟', 'mechanism_proof_shot': '输入传动输出画面证明',
    'narration_only': '无仅旁白解释', 'final_payoff': '结尾知识兑现',
    'mechanical_correctness': '机械正确性', 'audiovisual_sync': '动作与解说对应',
    'subtitle_sync': '字幕同步', 'series_consistency': '系列视觉与Neil声音',
    'series_value': '系列内容价值', 'next_episode_bridge': '真实下一集承接',
    'forced_follow_request': '无生硬求关注',
}
GROUPS = {
    'retention': ('opening_action', 'first_answer', 'information_progression', 'repeated_teasers',
                  'information_free_shots', 'long_holds', 'audiovisual_sync', 'final_payoff'),
    'engagement': ('aha_moment', 'mechanism_proof_shot', 'narration_only'),
    'following': ('final_payoff', 'series_consistency', 'series_value', 'next_episode_bridge', 'forced_follow_request'),
}
ROUTE_PURPOSE = {
    '2d': ('平面运动、方向与传动关系', '空间遮挡、实体装配关系仍需检查'),
    '2.5d': ('分层结构、投影与剖面关系', '层次投影不等于真实三维接触'),
    '3d': ('装配、拆解与空间关系', '材质真实感不证明机械接触正确'),
}


def read(path):
    return json.loads(Path(path).read_text())


def task_context(data):
    # Exclude workflow state and report pointers so delivery registration does not
    # invalidate its own report. Actual facts used below remain bound.
    return {k: data.get(k) for k in ('id', 'topic', 'duration', 'voice', 'repairs', 'stages',
                                    'agent_runs', 'requested_routes', 'route_runs')}


def context_sha(data):
    import hashlib
    return hashlib.sha256(json.dumps(task_context(data), sort_keys=True).encode()).hexdigest()


def discover(task):
    """Include newly delivered QA/configs, not just files present on first run."""
    task = Path(task).resolve()
    paths = {task/'task.json', task/'shared/timeline.json', task/'shared/captions.srt',
             task/'shared/narration.wav', task/'research/creative-blueprint.json', task/'multiroute/report.json'}
    for pattern in ('handoffs/*.json', 'qa/**/*.json', 'shared/qa*.json', 'shared/*statistics*.json',
                    'full-production/**/qa/**/*.json', 'full-production/**/*statistics*.json',
                    'full-production/**/baseline*.json', 'full-production/**/*repair*.json',
                    'production-status*.json', 'producer*plan*.json', 'post-publish/*.json'):
        paths.update(task.glob(pattern))
    cfg = read(task/'task.json').get('config')
    if cfg:
        paths.add(Path(cfg).resolve())
    return sorted((p.resolve() for p in paths if p.is_file()), key=str)


def references(value):
    if isinstance(value, dict):
        if isinstance(value.get('path'), str) and isinstance(value.get('sha256'), str):
            yield value
        for v in value.values():
            yield from references(v)
    elif isinstance(value, list):
        for v in value:
            yield from references(v)


def snapshot(task):
    result = []
    for path in discover(task):
        result.append({'path': str(path), 'sha256': context_sha(read(path)) if path.name == 'task.json' else sha(path),
                       'mode': 'task-context' if path.name == 'task.json' else 'bytes'})
    return result


def documents(task):
    rows = []
    for path in discover(task):
        if path.suffix == '.json':
            data = read(path)
            if isinstance(data, dict):
                rows.append({'source': {'path': str(path), 'sha256': sha(path)}, 'data': data})
    return rows


def bound(ref):
    try:
        return Path(ref['path']).is_file() and sha(ref['path']) == ref['sha256']
    except (KeyError, OSError, TypeError):
        return False


def source_valid(doc):
    # Explicit stale subtitle/config/sample dependencies invalidate old conclusions.
    return all(bound(ref) for ref in references(doc))


def qa_views(docs, route, digest):
    rows = []
    for doc in docs:
        data = doc['data']
        if not source_valid(data):
            continue
        view = data.get('route_checks', {}).get(route)
        if isinstance(view, dict) and view.get('media', {}).get('sha256') == digest:
            rows.append((doc, view))
        media = data.get('media', [])
        if isinstance(media, dict):
            media = [media]
        if data.get('route') in (None, route) and any(m.get('sha256') == digest for m in media if isinstance(m, dict)):
            rows.append((doc, data))
    return rows


def evaluate(views, dimension, duration):
    observations = []
    for doc, view in views:
        parent = doc['data']
        independent = parent.get('independent_reviewer') is True and bool(parent.get('reviewer_thread_id'))
        for group in ('retention_checks', 'engagement_checks', 'following_checks', 'dimension_checks'):
            for row in view.get(group, []):
                if row.get('goal', row.get('dimension')) != dimension:
                    continue
                t = row.get('time_range', [])
                status = row.get('status', 'UNKNOWN')
                valid_time = len(t) == 2 and all(finite(x) for x in t) and 0 <= t[0] < t[1] <= duration
                # PASS needs exact-media provenance, time evidence, and actual
                # perceptual capabilities, never a technical-only 'checks' label.
                usable = (independent and valid_time and row.get('evidence')
                          and row.get('media_sha256') in {m.get('sha256') for m in
                              ([view['media']] if isinstance(view.get('media'), dict) else view.get('media', parent.get('media', [])))}
                          and row.get('continuous_viewing') is True
                          and row.get('listening') is True)
                observations.append({'status': status if usable and status in {'PASS','FAIL'} else 'UNKNOWN',
                                     'time_range': t, 'evidence': row.get('evidence'), 'source': doc['source'],
                                     'reviewer_thread_id': parent.get('reviewer_thread_id')})
    status = 'FAIL' if any(o['status'] == 'FAIL' for o in observations) else (
        'PASS' if observations and all(o['status'] == 'PASS' for o in observations) else 'UNKNOWN')
    return {'status': status, 'observations': observations,
            'scope': '独立实际媒体检查；缺失或仅技术/抽帧证据不构成完整验收'}


def planned_timeline(timeline, blueprint):
    shots = timeline.get('shots', []) or blueprint.get('shots', [])
    rows = []
    for s in shots:
        start = s.get('start', s.get('start_time', s.get('time_range', [None,None])[0]))
        end = s.get('end_time', s.get('time_range', [None,None])[1])
        if end is None and finite(start) and finite(s.get('seconds', s.get('duration_seconds'))):
            end = start + s.get('seconds', s.get('duration_seconds'))
        rows.append({'shot_id': s.get('shot_id', s.get('id')), 'section_id': s.get('section_id'),
                     'time_range': [start,end], 'knowledge': s.get('new_information', s.get('teaching_goal', s.get('title', s.get('knowledge_goal')))),
                     'mechanical_action': s.get('mechanical_action', s.get('action')),
                     'narration': s.get('narration'), 'scope': '脚本/实测音频时轴规划，非成片感官结论'})
    return rows


def repair_history(docs, route, media):
    """Import existing real baselines; never infer attempts from version numbers."""
    found = []
    for doc in docs:
        data = doc['data']
        baseline = data.get('baseline')
        if not isinstance(baseline, list) or not data.get('defect_key'):
            continue
        for row in baseline:
            path = Path(row.get('preserved', ''))
            if path.suffix != '.mp4' or not path.is_file() or sha(path) != row.get('sha256'):
                continue
            # A synchronized comparison is contextual evidence only, not a
            # per-route same-condition A/B. Preserve that limitation explicitly.
            found.append({'defect_key': data['defect_key'], 'original_problem': data.get('user_instruction', data.get('status')),
                          'before': {'path': str(path.resolve()), 'sha256': sha(path)}, 'after': media,
                          'scope': '历史同步对比版本；不是单路线同条件A/B' if 'compare' in path.name else '历史基线；条件可比性未验证',
                          'time_range': None, 'repair_method': None, 'observed_change': None,
                          'independent_qa': 'UNKNOWN', 'source': doc['source']})
    # Optional structured repair observations authored by existing Producer/QA.
    for doc in docs:
        for row in doc['data'].get('growth_repairs', []):
            if row.get('route') != route:
                continue
            if row.get('task_id') != media.get('task_id') or row.get('after', {}).get('sha256') != media['sha256']:
                continue
            if not bound(row.get('before', {})) or not bound(row.get('after', {})):
                continue
            found.append(dict(row, scope='真实基线；变化仅引用既有独立QA，非平台A/B', source=doc['source']))
    return {'mode': '真实历史基线，增长改善未验证' if found else '首次设计（未提供可核验修复前版本）',
            'comparisons': found, 'growth_improvement': 'UNKNOWN'}


def route_metrics(docs, route, digest):
    result = {'repair_count': None, 'production_seconds': None, 'scope': '缺少对应当前版本的运行时计量则null'}
    for doc in docs:
        d = doc['data']
        if d.get('route') == route and d.get('media_sha256') == digest:
            for target, keys in {'production_seconds': ('production_seconds','elapsed_seconds','total_seconds'), 'repair_count': ('repair_count',)}.items():
                for key in keys:
                    if finite(d.get(key)):
                        result[target] = d[key]
        for key in ('routes',):
            row = d.get(key, {}).get(route, {}) if isinstance(d.get(key), dict) else {}
            receipt = row.get('receipt', {}) if isinstance(row, dict) else {}
            if bound(receipt):
                receipt_data = read(receipt['path'])
                if digest in json.dumps(receipt_data):
                    result['production_seconds'] = row.get('elapsed_seconds')
                    result['source'] = doc['source']
    return result


def frame(path, seconds, output):
    subprocess.run(['ffmpeg','-v','error','-nostdin','-y','-ss',str(seconds),'-i',str(path),
                    '-frames:v','1','-vf','scale=640:-2','-update','1',str(output)],
                   check=True, capture_output=True)


def render_markdown(report):
    lines = ['# 视频增长目标优化报告', '', f"主题：{report['topic']}；状态：{report['status']}",
             '', '本报告评价制作目标落实情况，不证明完播率、点赞率或关注率提升。抽帧不代替连续观看或听审。',
             '', '## 原始设计与知识结构', '', '```json', json.dumps(report['design'],ensure_ascii=False,indent=2), '```']
    for route, data in report['routes'].items():
        lines += ['', f'## {route}', '', f"视频：{data['media']['path']}", f"SHA256：`{data['media']['sha256']}`",
                  f"实际时长：{data['duration_seconds']}秒；修复次数：{data['metrics']['repair_count']}；制作耗时：{data['metrics']['production_seconds']}秒（null表示未知）",
                  '', '|检查维度|状态|', '|---|---|']
        lines += [f"|{label}|{data['dimensions'][key]['status']}|" for key,label in DIMENSIONS.items()]
        lines += ['', '时间点（设计时点与媒体观察分开）：', '```json',json.dumps(data['timing'],ensure_ascii=False,indent=2),'```',
                  '', '知识推进（脚本依据）：','```json',json.dumps(report['timeline'],ensure_ascii=False,indent=2),'```',
                  '', '实际媒体QA观察与问题：','```json',json.dumps(data['qa_observations'],ensure_ascii=False,indent=2),'```',
                  '', '修复前后：','```json',json.dumps(data['repairs'],ensure_ascii=False,indent=2),'```']
    lines += ['', '封面交付：cover/cover-report.md（两种比例；独立视觉检查见cover-qa.json）。']
    lines += ['', '## 结论', ''] + [f'{i}. {s}' for i,s in enumerate(report['conclusions'],1)]
    lines += ['', '## 发布后真实数据', '', '```json',json.dumps(report['post_publish'],ensure_ascii=False,indent=2),'```',
              '', '证据和完整维度时间码见 growth-report.json 与 growth-evidence/manifest.json。']
    return '\n'.join(lines)+'\n'


def comparison_markdown(report):
    lines = ['# 三版本对比与推荐', '', '|版本|表达用途（非已验收优势）|限制|已知制作秒数|', '|---|---|---|---|']
    for route,data in report['routes'].items():
        purpose,limit = ROUTE_PURPOSE[route]
        lines.append(f"|{route}|{purpose}|{limit}|{data['metrics']['production_seconds']}|")
        lines += []
    for route,data in report['routes'].items():
        lines += ['', f'## {route}', '', f"文件：{data['media']['path']}；SHA256：`{data['media']['sha256']}`",
                  '', '实际可观察差异与覆盖范围：','```json',json.dumps(data['qa_observations'],ensure_ascii=False,indent=2),'```',
                  '', '主要缺陷：','```json',json.dumps(data['issues'],ensure_ascii=False,indent=2),'```']
    lines += ['', '## 发布建议', '', report['recommendation']['reason'],
              '', '无证据支持某条路线一定优于其他路线或更容易爆款。成本来自既有日志，未计量保持null。']
    return '\n'.join(lines)+'\n'


def paths_for(task):
    data = read(Path(task)/'task.json')
    paths = {}
    for route in ROUTES:
        ref = data.get('route_runs', {}).get(route, {}).get('outputs', {})
        paths[route] = Path(ref.get('path', Path(task)/('2_5d' if route=='2.5d' else route)/'final.mp4')).resolve()
    return paths


def generate(task, paths=None, comparison=None):
    task = Path(task).resolve()
    task_data = read(task/'task.json')
    paths = paths or paths_for(task)
    comparison = Path(comparison or task/'multiroute/compare.mp4').resolve()
    missing = [str(paths.get(r)) for r in ROUTES if not paths.get(r) or not Path(paths[r]).is_file()]
    if missing or not comparison.is_file():
        raise ValueError('Growth report BLOCKED: missing actual media: '+', '.join(missing+[str(comparison)]))
    from .covers import generate as generate_covers, validate as validate_covers
    if (task / "cover-plan.json").is_file():
        generate_covers(task, paths)
    covers = validate_covers(task, paths=paths)
    before = snapshot(task)
    docs = documents(task)
    blueprint = next((d['data'] for d in docs if Path(d['source']['path']).name == 'creative-blueprint.json'), {})
    timeline = read(task/'shared/timeline.json') if (task/'shared/timeline.json').is_file() else {}
    for doc in reversed(docs):
        if doc['data'].get('payload', {}).get('growth_goals'):
            blueprint = doc['data']['payload']; break
    rows = planned_timeline(timeline,blueprint)
    goals = blueprint.get('growth_goals', {})
    report = {'schema_version':1,'task_id':task_data.get('id',task.name),'topic':task_data['topic'],
              'generated_epoch':time.time(),'status':'CANDIDATE_UNACCEPTED','routes':{},
              'comparison':{'path':str(comparison),'sha256':sha(comparison)},
              'design':{'core_question':blueprint.get('core_question'),'growth_goals':goals,
                        'scope':'设计目标，不代表媒体已实现；历史蓝图缺失字段保持null'},
              'timeline':rows,'sources':before,'generator_sha256':sha(__file__),
              'post_publish':{'status':'NOT_PROVIDED','observations':[], 'hypotheses':[],
                              'scope':'没有发布后数据，不计算虚假增长；不把异平台或异流量当严格A/B'}}
    evidence_dir = task/'growth-evidence'; evidence_dir.mkdir(exist_ok=True)
    evidence = []
    for route in ROUTES:
        path = Path(paths[route]).resolve(); digest = sha(path)
        duration = float(probe(path)['format']['duration'])
        media = {'path':str(path),'sha256':digest,'task_id':report['task_id']}
        views = qa_views(docs,route,digest)
        dimensions = {key:evaluate(views,key,duration) for key in DIMENSIONS}
        timing = {}
        for key in ('opening_action','first_answer','aha_moment'):
            planning = next((group[key] for group in goals.values() if isinstance(group,dict) and key in group),None)
            sid = planning.get('shot_id') if isinstance(planning,dict) else None
            planned = next((r['time_range'] for r in rows if r['shot_id']==sid),None)
            if key=='opening_action' and planned is None and rows: planned=rows[0]['time_range']
            timing[key] = {'status':dimensions[key]['status'],'planned_time_range':planned,
                           'observed_time_ranges':[o['time_range'] for o in dimensions[key]['observations'] if o['status'] in {'PASS','FAIL'}]}
        observation_rows = []
        issues = []
        for doc,view in views:
            observation_rows.append({'source':doc['source'],'checks':view.get('checks',{}),
                'scope':view.get('scope',doc['data'].get('scope')),
                'requirements':view.get('requirements',view.get('requirements_to_evidence',[])),
                'capabilities':doc['data'].get('capabilities',{}),
                'visual_differences':doc['data'].get('comparison_checks',{}).get('observable_visual_differences')})
            issues.extend({'source':doc['source'],'issue':i} for i in doc['data'].get('issues',[]))
        entry = {'media':media,'duration_seconds':duration,'timing':timing,'dimensions':dimensions,
                 'qa_observations':observation_rows,'issues':issues,'metrics':route_metrics(docs,route,digest),
                 'repairs':repair_history(docs,route,media)}
        report['routes'][route]=entry
        # Small, content-addressed samples. Extraction is not perceptual review.
        samples = [0.0, max(0,duration-1)]
        samples += [r['time_range'][0] for r in rows if finite(r['time_range'][0]) and 0 <= r['time_range'][0] < duration]
        for seconds in sorted(set(samples)):
            target=evidence_dir/f'{route}-{digest[:16]}-{seconds:.6f}.jpg'
            frame(path,seconds,target)
            evidence.append({'path':str(target),'sha256':sha(target),'route':route,'media_sha256':digest,
                             'seconds':seconds,'scope':'EXTRACTED_FRAME_NOT_REVIEWED'})
    # Bind even referenced historical evidence/frames/configs; missing references
    # are recorded, never silently treated as current QA acceptance.
    dependencies = {}
    for doc in docs:
        for ref in references(doc['data']):
            p=str(Path(ref['path']).resolve())
            dependencies[p]={'path':p,'sha256':sha(p) if Path(p).is_file() else None}
    report['dependencies']=list(dependencies.values())
    evidence_manifest={'schema_version':1,'task_id':report['task_id'],'frames':evidence,'timeline':rows,
                       'routes':{r:d['media'] for r,d in report['routes'].items()},'qa_sources':[d['source'] for d in docs if 'qa' in d['source']['path']]}
    write(evidence_dir/'manifest.json',evidence_manifest)
    report['recommendation']={'route':None,'reason':'科学正确性、内容清晰度或完整视听质量尚未可靠验证，不能作出确定的发布推荐。'}
    all_pass=all(d['status']=='PASS' for r in report['routes'].values() for d in r['dimensions'].values())
    if all_pass:
        report['status']='QA_VERIFIED_DELIVERY'
        report['recommendation']['reason']='三版现有独立媒体检查均通过；缺少可比优劣证据，不强行指定单一版本。'
    report['covers'] = {'path': str(task/'cover/cover-report.json'), 'sha256': sha(task/'cover/cover-report.json')}
    report['recommendation'] = {'route': covers['recommended_route'], 'reason': covers['rationale']['recommendation_reason'], 'scope': 'Producer editorial recommendation; not publication approval'}
    try:
        validate_covers(task, require_pass=True, paths=paths)
    except (ValueError, FileNotFoundError):
        report['status'] = 'CANDIDATE_UNACCEPTED'
    report['conclusions']=[
        '完播：依据原始蓝图与章节时轴记录开场、早期答案、信息推进；实际落实以每路线媒体QA为准，未知项不宣称改善。',
        '点赞：核心顿悟及一句话收获见growth_goals.engagement；缺失时不从旁白推断画面已证明。',
        '吸粉：本集兑现及具体下一集计划见following；无真实计划证据则UNKNOWN。',
        '三版用途、实际观察、缺陷与成本分别列出；路线名称不代表质量排序。',
        report['recommendation']['reason'],
        '关键未验证项：'+('无（仅限已提供QA覆盖范围）' if all_pass else '至少一个内容、机械或感官维度仍为UNKNOWN/FAIL；见逐版检查。'),
        '下次可复用：保留输入—传动—输出的可见证明、实测音频时轴及版本绑定证据；具体策略须经独立媒体检查，发布后数据另行验证。']
    if snapshot(task)!=before:
        raise ValueError('Growth report inputs changed while generating; retry with stable inputs')
    for entry in report['routes'].values():
        if not bound(entry['media']): raise ValueError('Media changed while generating report')
    md=task/'growth-report.md'; comparison_md=task/'version-comparison.md'
    md.write_text(render_markdown(report)); comparison_md.write_text(comparison_markdown(report))
    report['artifacts']=[{'path':str(p),'sha256':sha(p)} for p in (md,comparison_md,evidence_dir/'manifest.json')]+evidence
    write(task/'growth-report.json',report)
    return report


def validate(task):
    task=Path(task).resolve(); report=read(task/'growth-report.json')
    from .covers import validate as validate_covers
    if not bound(report.get('covers', {})):
        raise ValueError('Growth report STALE: covers changed or missing')
    validate_covers(task)
    if report['generator_sha256']!=sha(__file__) or report['sources']!=snapshot(task):
        raise ValueError('Growth report STALE: inputs/QA/subtitles/config or generator changed')
    for ref in [report['comparison'],*[d['media'] for d in report['routes'].values()],*report['artifacts']]:
        if not bound(ref): raise ValueError('Growth report STALE: media/evidence/report changed: '+ref['path'])
    for ref in report['dependencies']:
        current=sha(ref['path']) if Path(ref['path']).is_file() else None
        if current!=ref['sha256']: raise ValueError('Growth report STALE: referenced evidence changed')
    return report


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('task',type=Path);p.add_argument('--validate',action='store_true')
    a=p.parse_args(); r=validate(a.task) if a.validate else generate(a.task)
    print(json.dumps({'status':r['status'],'report':str(a.task/'growth-report.json')},ensure_ascii=False))


if __name__=='__main__':
    main()
