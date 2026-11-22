"""One-film revision; uses the existing Blueprint, locked Blender and Remotion.

No scheduler, agent, solver or shared renderer changes. All dimensions and motion
come from the preserved Sanford Fig 1–4C repair, never from an imagined product.
"""
import argparse
import copy
import importlib.util
import json
import math
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'scripts')]
from common import Metrics, filehash, run
from clean import production_lock, retain_shot_export
from produce import expose, make_shot
from mechanical_video_next.blender_runtime import run_blender

OUT = ROOT / 'output/correction-tape-remake'
TASK = ROOT / 'output/tasks/workflow-acceptance-20261118'
REPAIR = TASK / 'repairs'
BASELINE = ROOT / 'output/audience-film/neil-revision-final.mp4'
CANDIDATE = ROOT / 'output/camera-study/correction-tape-camera-candidate.mp4'
ASSEMBLY = REPAIR / 'repair-assembly.v2.json'
MODEL = ROOT / 'work/cache/assets/249fccc0ceb05ea37fe46e86eab37e076b7fc3b5e387fea02d08d9a5c2ece5af/assembly.blend'
CHANGED = ['route', 'radii', 'equal_length', 'fixed_ratio', 'nominal_comparison',
           'slip', 'force', 'radial_spring', 'relief', 'return_reset']
CORE = ['fixed_ratio', 'nominal_comparison', 'slip', 'force']
FINAL_DIR = 'final-v2'
FINAL_BLUEPRINT = 'creative-blueprint.final-v2.json'
FINAL_CONFIG = 'production-config.final-v2.json'


def writejson(path, value):
    """Compact task-local geometry records; avoid indenting millions of vertices."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary=path.with_suffix(path.suffix+'.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, separators=(',', ':'))+'\n')
    temporary.replace(path)


def read(path):
    return json.loads(Path(path).read_text())


def ref(path, position=None):
    result = dict(path=str(Path(path).resolve()), sha256=filehash(path))
    if position:
        result['position'] = position
    return result


def source():
    path = REPAIR / 'repair_geometry_motion.v1.py'
    assert filehash(path) == 'fb867c4ea9a214bd93e821903d1108745cc2a342004f792b750cc89b2cfd9a8c'
    spec = importlib.util.spec_from_file_location('preserved_correction_motion', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def path(keys, direction=(.10, -.48, 1)):
    return [dict(progress=t, target=c, direction=list(direction), width=w) for t, c, w in keys]


def finish_style(shot, family):
    palettes = {'warm': [.27, .30, .32], 'contact': [.075, .105, .14], 'spring': [.22, .27, .30]}
    shot['studio_lighting'].update(
        floor_color=palettes[family], world_strength=.38, key_strength=1.35,
        fill_strength=.45, rim_strength=1.7, key_size=.65, rim_size=.48,
        render_samples=8, camera_push=False)
    colors = {
        'Supply_core': ([.18, .29, .36], .25, .29),
        'Supply_drive_rim': ([.17, .30, .39], .6, .27),
        'Takeup_core': ([.12, .40, .38], .2, .32),
        'Takeup_rim': ([.12, .42, .40], .5, .28),
        'Supply_winding': ([.72, .57, .35], 0, .55),
        'Takeup_winding': ([.37, .63, .64], .05, .36),
        'Friction_loop': ([.025, .035, .045], 0, .62),
        'Radial_spring': ([.95, .40, .10], .35, .28),
        'Supply_axle': ([.66, .73, .80], .75, .2),
        'Takeup_axle': ([.66, .73, .80], .75, .2),
        'Housing_back': ([.20, .25, .30], .12, .55),
        'Belt_witness': ([1, .20, .015], 0, .3),
        'Supply_witness': ([.01, .65, 1], 0, .25),
        'Coated_ribbon': ([.88, .82, .66], 0, .45),
        'Return_film': ([.24, .64, .68], .08, .35),
    }
    shot['studio_lighting']['material_overrides'].update({
        name: dict(color=c, metallic=m, roughness=r) for name, (c, m, r) in colors.items()})


def radius_guides(shot):
    shot['science']['guides'] = []
    for axle, coil, color in [('Supply_axle', 'Supply_winding', [1, .57, .20]),
                               ('Takeup_axle', 'Takeup_winding', [.10, .94, .80])]:
        shot['science']['guides'].append(dict(kind='dashed', color=color, width=.00013,
            points=[dict(object=axle, local=[0, 0, 9.35]),
                    dict(object=coil, vertex=2, local=[0, 0, .00305])]))
        shot['science']['guides'].append(dict(kind='marker', color=color, width=.00045,
            points=[dict(object=coil, vertex=2, local=[0, 0, .00305])]))


def note(text, seconds, y=812, end=None):
    return dict(type='note', text=text, box=[80, y, 1840, y+92], time=[0, end or seconds])


def prepare():
    OUT.mkdir(parents=True, exist_ok=True)
    cfg = read(REPAIR / 'production-config.v6.json')
    props = read(ROOT / 'output/audience-film/neil-revision-final.props.json')
    blueprint = read(ROOT / 'output/camera-study/creative-blueprint.candidate.json')
    gen = source()
    model_matching = copy.deepcopy(cfg['shots']['slip']['visual']['matching'])
    model_matching['receipt_shot'] = 'slip'
    descriptions = {
        'route': ('沿同一条带路认清供卷、压头和收卷', '从完整装配缓推，保持两卷和压头同框；材质区分涂层带与回收膜', '压头动作接到透明回程，再接两卷的半径差'),
        'radii': ('同一输带量让供卷变细、收卷变粗', '两卷同框；半径线和端点直接跟随卷材网格；不夸大半径变化', '承接带路；下一镜同视角观察两卷转角'),
        'equal_length': ('同一长度通过，小卷转角更大', '两条径向色线随真实累计转角运动；转速由同一输带量计算', '保持轴心位置；随后移开卷材以看清下层轮缘'),
        'fixed_ratio': ('固定轮缘通过环带连接，理想不滑时标记同行', '先见两个完整轮缘，再推进共用接触弧；两标记保持同角位置', '同侧接触面进入无滑动对照，再回整体'),
        'nominal_comparison': ('卷材半径变化而传动轮缘半径固定', '同一运动的真实卷材与轮缘同框；两行小数值附着画面，公式不占主画面', '由轮缘整体返回两卷，再转入同一接触面滑动'),
        'slip': ('两个接触表面的标记出现相对位移', '先完整装配定位，再锁定接触弧；整段同步慢放；末尾回到两卷', '方向、两色标记和轮缘不换边；回退兑现收卷仍继续'),
        'force': ('给定阻力矩下，小半径需要更大切向拉力', '保留同一供卷和动态半径线；条件与数值靠近实际机构', '从传力接触回到卷材力臂，再进入卷芯弹指'),
        'radial_spring': ('固定轴不动，弹指弯曲而卷芯径向偏移', '铜色弹指、浅色固定轴、蓝色卷芯；保留有依据的透视显示与固定参照', '从两卷进入供卷芯；末尾退回环带和两轴'),
        'relief': ('卷芯保持偏移，环带形状与接触条件改变', '同一已加载状态继续规定输带；固定轴参照保持不变', '严格承接加载末状态，后接仅径向回位'),
        'return_reset': ('撤去拉动后径向回位，底膜不倒转', '固定轴和卷芯同框，保持原有释放轨道，不添加弹簧或反转', '承接保持状态；随后返回纸面真实应用动作'),
    }
    for sid in CHANGED:
        if sid in ['radii', 'equal_length', 'nominal_comparison', 'force']:
            shot = copy.deepcopy(cfg['shots']['slip'])
            window = {'radii': (0, .73), 'equal_length': (.73, .81),
                      'nominal_comparison': (0, .73), 'force': (0, .73)}[sid]
            phase = json.loads(json.dumps(gen.sample_motion('motion', *window), default=gen.json_default))
            for key in ['tracks', 'mesh_tracks', 'visible_parts']:
                shot[key] = phase[key]
            shot['science']['constraints'] = []
            shot['science']['scope'] = phase['scope']
            shot['visible_parts'] = [n for n in phase['visible_parts'] if n not in ['Belt_witness', 'Supply_witness']]
            cfg['shots'][sid] = shot
        shot = cfg['shots'][sid]
        shot['scene_artifact_dir'] = str(OUT / 'scenes')
        spec = shot['science']
        for key in ['camera_rig', 'camera_clip', 'camera_framing', 'camera_path_follow']:
            spec.pop(key, None)
        finish_style(shot, 'contact' if sid in ['fixed_ratio', 'slip'] else 'spring' if sid in ['radial_spring','relief','return_reset'] else 'warm')
        seconds = shot['seconds']
        if sid == 'route':
            spec['camera_path'] = path([(0, [.003, 0, .005], .139), (.55, [.012, 0, .005], .125), (1, [.009, 0, .005], .123)])
        elif sid in ['radii', 'equal_length', 'nominal_comparison', 'force']:
            shot['seconds'] = next(s['seconds'] for s in props['shots'] if s['id'] == sid)
            seconds = shot['seconds']
            spec['camera_path'] = path([(0, [-.007, 0, .006], .097), (1, [-.007, 0, .006], .091)], (.06, -.36, 1))
            radius_guides(shot)
            if sid == 'force':
                spec['camera_path'] = path([(0, [-.007, 0, .006], .091), (.3, [-.018, 0, .006], .060), (1, [-.018, 0, .006], .060)], (.06, -.36, 1))
        elif sid == 'fixed_ratio':
            spec['camera_path'] = path([(0, [-.008, 0, .008], .086), (.30, [-.018, -.018, .0085], .022), (.82, [-.018, -.018, .0085], .022), (1, [-.008, 0, .008], .086)], (0, -.55, 1))
            spec['time_map'] = [[0,0],[.30,0],[.82,1],[1,1]]
        elif sid == 'slip':
            spec['camera_path'] = path([(0, [-.002, 0, .006], .128), (.16, [-.018, -.018, .0085], .019), (.86, [-.018, -.018, .0085], .019), (1, [-.002, 0, .006], .128)], (0, -.55, 1))
            spec['time_map'] = [[0,0],[.18,0],[.84,1],[1,1]]
        elif sid == 'radial_spring':
            spec['camera_path'] = path([(0, [-.008, 0, .006], .083), (.20, [-.0176, 0, .005], .037), (.72, [-.0176, 0, .005], .037), (1, [-.008, 0, .006], .083)], (.04, -.26, 1))
        else:
            spec['camera_path'] = path([(0, [-.008, 0, .006], .083), (1, [-.008, 0, .006], .083)], (.04, -.26, 1))
        spec['basis'].append(ref(REPAIR/'repair_geometry_motion.v1.py', 'Same bounded roll law and exact source-compatible material motion; no physical solver'))
        writejson(OUT/'shots'/f'{sid}.json', shot)
    for row in blueprint['shots']:
        sid = row['shot_id']
        if row['render_engine']=='blender':
            row['asset']=cfg['asset']
        if sid not in CHANGED:
            continue
        goal, action, link = descriptions[sid]
        row.update(template='state_transition', render_engine='blender', existing_shot=sid,
                   asset=cfg['asset'], visual_type='annotated_detail', mechanical_action=action,
                   visual_action=action, visual_focus=goal, knowledge_goal=goal,
                   information=[], generation_required=True, reuse_decision='REUSE_MODEL')
        row.pop('graphic', None)
        row['camera'] = dict(scale='close', angle='same source assembly oblique', preset='establish', settings={})
        row['direction'].update(why_visual=goal, composition=action,
            lighting='按镜头区分暖灰、深蓝灰和冷灰背景；铜色弹指、青色收卷与蓝色轮缘保持身份', continuity=link)
        row['transition'] = dict(kind='cut', link=link)
        row['overlays'] = []
        row['assets'] = [str(ASSEMBLY), str(MODEL)]
        row['selected_asset'] = ref(MODEL)
        row['matching'] = copy.deepcopy(model_matching)
        row['comprehension']['product_parts'] = ['Supply_winding','Takeup_winding','Supply_drive_rim','Friction_loop'] if sid in ['radii','equal_length','nominal_comparison','force'] else row['comprehension']['product_parts']
        row['evidence'] = copy.deepcopy(cfg['shots'][sid]['science']['basis'])
        from mechanical_video_next.visual_narrative import design_fields
        cfg['shots'][sid]['visual'] = design_fields(row)
    blueprint.update(status='DRAFT', presentation_style='natural_science')
    blueprint.pop('production_config', None)
    blueprint['revision_basis'] = [ref(BASELINE), ref(CANDIDATE), ref(ASSEMBLY)]
    writejson(OUT/'base-config.json', cfg)
    writejson(OUT/'creative-blueprint.json', blueprint)
    compile_plan()


def compile_plan():
    from mechanical_video_next.blueprint import compile_config
    cfg=read(OUT/'base-config.json')
    blueprint=read(OUT/'creative-blueprint.json')
    for row in blueprint['shots']:
        if row['render_engine']=='blender':row['asset']=cfg['asset']
    for sid in ['radii','equal_length','nominal_comparison','force']:
        radius_guides(cfg['shots'][sid])
    writejson(OUT/'base-config.json',cfg)
    writejson(OUT/'creative-blueprint.json',blueprint)
    del cfg, blueprint
    compile_config(OUT/'creative-blueprint.json', OUT/'base-config.json', OUT/'production-config.json', draft=True)
    writejson(OUT/'source-lock.json', dict(implementation='Sanford US8746316B2 Figs 1–4C',
        sources=[ref(REPAIR/'repair_geometry_motion.v1.py'),ref(ASSEMBLY),ref(MODEL),
                 ref(ROOT/'output/tasks/production-1794969915231117000/research/US8746316.pdf')],
        previous=[ref(BASELINE),ref(CANDIDATE)], changed=CHANGED,
        preserved=['hook','transfer','return_answer'],
        limits=['Prescribed kinematics; no measured slip rate, force, spring law or physical friction simulation',
                'All interacting rigid and mesh tracks share the same monotone time map',
                'Continuous viewing/listening and independent acceptance UNKNOWN']))


def final_plan():
    """Bind the actual moving animatic and its editorial choices before final shots."""
    import mechanical_video_next.blueprint as compiler
    assert (OUT/'full-dynamic-animatic.mp4').is_file()
    audit=read(OUT/'preview/slip.render.scene-audit.json')
    assert audit['relative_phase']['both_centers_in_frame_all_frames']
    cfg=read(OUT/'base-config.coils.json')
    blueprint=read(OUT/'creative-blueprint.coils.json')
    props=read(OUT/'preview.props.json')
    rows={s['id']:s for s in props['shots']}
    from mechanical_video_next.visual_narrative import design_fields
    for row in blueprint['shots']:
        sid=row['shot_id']
        if sid not in CHANGED:continue
        row['information']=copy.deepcopy(rows[sid].get('information',[]))
        row['overlays']=[i['text'] for i in row['information'] if i['type']=='note']
        row['assets']=[str(ASSEMBLY),str(MODEL)]
        row['comprehension']['visual_evidence']=row['visual_action']
        cfg['shots'][sid]['studio_lighting']['render_samples']=24
        cfg['shots'][sid]['studio_lighting'].update(key_strength=.90,world_strength=.25,rim_strength=1.2)
        if sid in ['slip','fixed_ratio']:
            cfg['shots'][sid]['science']['camera_clip']=[29.9,30.1]
        if sid=='slip':
            cfg['shots'][sid]['science']['time_map']=[[0,0],[.18,0],[1,1]]
            cfg['shots'][sid]['science']['camera_path'][2]['progress']=.78
            row['direction']['continuity']+='；正式尺寸版本在回到整体的最后22%继续输带，取消末尾静止保持；源位移范围不变'
        cfg['shots'][sid]['visual']=design_fields(row)
    blueprint['animatic_basis']=ref(OUT/'full-dynamic-animatic.mp4')
    blueprint['editorial_basis']=ref(OUT/'preview.props.json')
    blueprint['version_note']='Final native samples 24; full dynamics generated; sensory QA UNKNOWN'
    writejson(OUT/FINAL_BLUEPRINT,blueprint)
    writejson(OUT/'base-config.final-v2.json',cfg)
    del cfg,blueprint
    # Only JSON whitespace changes. All existing compilation/validation remains active.
    original=compiler.writejson
    compiler.writejson=writejson
    try:
        compiler.compile_config(OUT/FINAL_BLUEPRINT,OUT/'base-config.final-v2.json',OUT/FINAL_CONFIG,draft=True)
    finally:
        compiler.writejson=original
    writejson(OUT/'core-quality-gate.json',dict(technical='SUPPORTED',sensory='UNKNOWN',
        core=ref(OUT/('core-dynamic-preview-coils.mp4' if (OUT/'core-dynamic-preview-coils.mp4').exists() else 'core-dynamic-preview.mp4')),animatic=ref(OUT/'full-dynamic-animatic.mp4'),
        native_audit=ref(OUT/'preview/slip.render.scene-audit.json'),
        continuation='Supported full workprint permitted; no acceptance or quality score asserted'))


def reveal_coils():
    """Remove only an observed visual obstruction; retain all source motion."""
    import mechanical_video_next.blueprint as compiler
    from mechanical_video_next.visual_narrative import design_fields
    cfg=read(OUT/'base-config.json')
    blueprint=read(OUT/'creative-blueprint.json')
    for row in blueprint['shots']:
        sid=row['shot_id']
        if sid not in ['radii','equal_length','nominal_comparison','force']:continue
        shot=cfg['shots'][sid]
        shot['visible_parts']=[n for n in shot['visible_parts'] if n not in ['Supply_drive_rim','Takeup_rim']]
        row['direction']['composition']+='；仅在本比较中隐藏遮住卷材的上层传动轮盘，直接露出同一带卷；不是物理拆装'
        row['mechanical_action']=row['visual_action']=row['direction']['composition']
        row['visual_focus']='可见的供卷和收卷带材、同源半径线与转角'
        row['overlays']=[]
        shot['visual']=design_fields(row)
    blueprint['revision_note']='Observed winding occlusion repaired by editorial visibility only; contact and slip rims unchanged'
    writejson(OUT/'base-config.coils.json',cfg)
    writejson(OUT/'creative-blueprint.coils.json',blueprint)
    del cfg,blueprint
    original=compiler.writejson
    compiler.writejson=writejson
    try:
        compiler.compile_config(OUT/'creative-blueprint.coils.json',OUT/'base-config.coils.json',OUT/'production-config.coils.json',draft=True)
    finally:compiler.writejson=original


def render_shots(phase, selected):
    version=FINAL_DIR if phase in ['final','final-keys'] else 'coils' if (OUT/'production-config.coils.json').exists() else None
    config_path=OUT/(f'production-config.{version}.json' if version else 'production-config.json')
    blueprint_path=OUT/(f'creative-blueprint.{version}.json' if version else 'creative-blueprint.json')
    cfg = read(config_path)
    metrics = Metrics('correction-tape-remake-'+phase)
    size = (1920,1080) if phase in ['final','final-keys'] else (960,540)
    with production_lock():
        for sid in selected:
            shot = copy.deepcopy(cfg['shots'][sid])
            if phase=='final':
                shot['studio_lighting']['render_samples']=24
            media, _, key = make_shot(shot, 'keys' if phase.endswith('keys') else 'final', MODEL,
                metrics, dict(width=size[0],height=size[1],fps=30,framing='fullframe',preview_native=True,chunk_frames=3), ASSEMBLY)
            receipt = dict(shot_id=sid, key=key, checks=ref(media.parent/'checks.json'),
                           blueprint=ref(blueprint_path), config=ref(config_path))
            directory=FINAL_DIR if phase=='final' else 'preview-coils' if phase=='preview' and version=='coils' and sid in ['radii','equal_length','nominal_comparison','force'] else phase
            if not phase.endswith('keys'):
                target=OUT/directory/(sid+'.mp4')
                target.parent.mkdir(parents=True,exist_ok=True)
                shutil.copy2(media,target)
                receipt['media'] = ref(target)
            writejson(OUT/directory/(sid+'.render.json'),receipt)
            if phase=='final' and sid=='slip':
                run_blender(['--factory-startup','--python-exit-code','1',
                             '--python',OUT/'audit_scenes.py','--',OUT/directory/(sid+'.render.json')],
                            log=OUT/directory/'slip-every-frame-audit.log', name='scene-audit')
            if phase=='final':
                writejson(OUT/directory/(sid+'.cache-archive.json'),retain_shot_export(media.parent,target,apply=True))
            print(sid, phase, key, flush=True)
    metric_name=FINAL_DIR+'-'+selected[0] if phase=='final' else 'preview-coils' if phase=='preview' and version=='coils' else phase
    writejson(OUT/(metric_name+'-metrics.json'),metrics.finish(tokens=None,cost=None))


def compose(phase, core_only=False):
    from mechanical_video_next.remotion_build import render
    props = read(ROOT/'output/audience-film/neil-revision-final.props.json')
    gen = source()
    for row in props['shots']:
        sid = row['id']
        if sid not in (CORE if core_only else CHANGED):
            continue
        directory=FINAL_DIR if phase=='final' else 'preview-coils' if phase=='preview' and (OUT/'preview-coils'/(sid+'.mp4')).exists() else phase
        row.pop('graphic',None)
        row['media']=expose(OUT/directory/(sid+'.mp4'), filehash(OUT/directory/(sid+'.mp4')))
        row['information']=[]
        row['scienceLabel']=None
        if sid in ['radii','equal_length','nominal_comparison','force']:
            row['scienceLabel']='隐去上层轮盘'
        checks=read(Path(read(OUT/directory/(sid+'.render.json'))['checks']['path']))
        row['screenAnchors']=checks.get('screen_anchors')
        secs=row['seconds']
        if sid in ['radii','equal_length']:
            row['information']=[note('橙：供带卷半径   青：收带卷半径',secs)]
        elif sid=='fixed_ratio':
            row['information']=[note('先看不滑的情况：两色标记同行',secs)]
        elif sid=='nominal_comparison':
            basis=ref(REPAIR/'repair_geometry_motion.v1.py','radii(s), same source length as rendered mesh')
            row['scienceLabel']='简化条件 · 隐去轮盘'
            row['information']=[dict(type='value',prefix='所需转速比 ',digits=2,unit='',
                time=[0,secs],box=[80,812,940,910],basis=basis,
                samples=[[i/40,gen.radii(250*.73*i/40)[0]/gen.radii(250*.73*i/40)[1]] for i in range(41)]),
                dict(type='note',text='不滑时轮缘比 2.36',box=[980,812,1840,910],time=[0,secs])]
        elif sid=='slip':
            row['information']=[note('同步慢放 · 蓝色轮缘标记与橙色环带标记逐渐错开',secs)]
        elif sid=='force':
            row['information']=[note('只比较同一阻力矩：半径变小，所需拉力变大',secs)]
        elif sid in ['radial_spring','relief','return_reset']:
            # Projection is exported by the actual new camera, never reused from the old one.
            projection=checks.get('screen_anchors',{})
            row['screenAnchors']=projection
            row['information']=[dict(type='label',text='固定轴',anchor='shaft_fixed',box=[80,170,480,270],time=[0,secs]),
                                dict(type='label',text='卷芯',anchor='core_edge',box=[1370,170,1770,270],time=[0,secs])]
            if sid=='relief':row['information'].append(note('保持偏移继续输带 · 接触段慢放',secs))
    props['text_layout_items']=[x for x in props.get('text_layout_items',[]) if x.get('layer')!='subtitle']
    props['presentation_style']='natural_science'
    blueprint_path=OUT/(FINAL_BLUEPRINT if phase=='final' else 'creative-blueprint.coils.json' if (OUT/'creative-blueprint.coils.json').exists() else 'creative-blueprint.json')
    if phase=='final':
        planned={s['shot_id']:s for s in read(blueprint_path)['shots']}
        for row in props['shots']:
            if row['id'] in CHANGED:row['information']=planned[row['id']]['information']
    props['title']='修正带 · 两卷如何配合'
    props['fullframe_credit']='结构依据：US8746316B2 图1–4C · 尺寸与运动为简化取值'
    label='core-preview' if core_only else phase
    writejson(OUT/(label+'.props.json'),props)
    target=OUT/('core-dynamic-preview-coils.mp4' if core_only and (OUT/'preview-coils').exists() else 'core-dynamic-preview.mp4' if core_only else 'correction-tape-remade.mp4' if phase=='final' else 'full-dynamic-animatic.mp4')
    rendered=target if core_only else target.with_name(target.stem+'.remotion.mp4')
    with production_lock():
        render(OUT/(label+'.props.json'),rendered,OUT/(label+'-composition.log'),preview=phase!='final',
               encode_profile=None if phase!='final' else 'progression-witness-v1',visual=True,progression=True,
               frame_range=[1615,3072] if core_only else None)
        if not core_only:
            run(['ffmpeg','-v','error','-y','-i',rendered,'-i',BASELINE,'-map','0:v:0','-map','1:a:0',
                 '-c','copy','-movflags','+faststart',target],OUT/(label+'-original-audio.log'))
    writejson(target.with_suffix('.build.json'),dict(output=ref(target),props=ref(OUT/(label+'.props.json')),
        blueprint=ref(blueprint_path),status='WORKPRINT_QA_PENDING',
        note='Reused measured Neil and exact existing cues; no speech synthesis or speed change'))


def package():
    """Actual media comparisons and existing cover layout, with honest QA limits."""
    from mechanical_video_next.media_revision import compare
    from mechanical_video_next.production_contract import review_media_identity
    from mechanical_video_next.covers import compose as cover_compose, SIZES, font_path as cover_font_path
    from mechanical_video_next.qa_images import prepare_image, visual_packet
    from PIL import Image, ImageDraw, ImageFont
    import glob
    selected_font=next((p for pattern in read(ROOT/'config/text-style.json')['font_candidates']
                        for p in glob.glob(pattern) if Path(p).is_file()),None) or cover_font_path()
    film=OUT/'correction-tape-remade.mp4'
    for name,media,start,end in [('core-55-95',film,55,95),('core-complete-action',film,1615/30,3073/30),
                                 ('old-neil-core-55-95',BASELINE,55,95)]:
        target=OUT/(name+'.mp4')
        run(['ffmpeg','-v','error','-y','-i',media,'-filter_complex',
             f'[0:v]trim=start_frame={round(start*30)}:end_frame={round(end*30)},setpts=PTS-STARTPTS[v];'
             f'[0:a]atrim=start={start}:end={end},asetpts=PTS-STARTPTS[a]',
             '-map','[v]','-map','[a]','-c:v','libx264','-preset','fast','-crf','18',
             '-c:a','aac','-b:a','192k','-movflags','+faststart',target],OUT/(name+'.log'))
    for name,old in [('candidate',OUT/'old-candidate-core-55-95.mp4'),('neil',OUT/'old-neil-core-55-95.mp4')]:
        strip=Image.new('RGB',(1920,100),'#22313d');draw=ImageDraw.Draw(strip)
        font=ImageFont.truetype(selected_font,42)
        draw.text((35,22),'旧候选' if name=='candidate' else '历史基线',font=font,fill='white')
        draw.text((995,22),'本次新版 · 同一时间与知识段',font=font,fill='white')
        strip.save(OUT/(name+'-comparison-heading.png'))
        run(['ffmpeg','-v','error','-y','-i',old,'-i',OUT/'core-55-95.mp4','-i',OUT/(name+'-comparison-heading.png'),
             '-filter_complex','[0:v]scale=960:540,setsar=1[l];[1:v]scale=960:540,setsar=1[r];'
             '[l][r]hstack=inputs=2,pad=1920:640:0:100[stack];[stack][2:v]overlay=0:0[v]',
             '-map','[v]','-map','1:a:0','-c:v','libx264','-crf','19','-preset','fast','-c:a','copy',
             '-movflags','+faststart',OUT/('comparison-'+name+'-vs-new.mp4')],OUT/('comparison-'+name+'.log'))
    blueprint=read(OUT/FINAL_BLUEPRINT)
    claims=[dict(shot_id=s['shot_id'],defect_key='V-'+s['shot_id'],knowledge_target=s['knowledge_goal'],
                 previous_range=s['time_range'],current_range=s['time_range'],comparison_region=[0,.15,1,.50])
            for s in blueprint['shots'] if s['shot_id'] in CHANGED]
    writejson(OUT/'revision-claims.json',claims)
    for name,old in [('candidate',CANDIDATE),('neil',BASELINE)]:
        writejson(OUT/('decoded-comparison-'+name+'.json'),compare(old,film,claims))
    identities={name:review_media_identity(ref(media)) for name,media in [('baseline',BASELINE),('candidate',CANDIDATE),('new',film)]}
    writejson(OUT/'audio-video-identities.json',identities)
    assert identities['new']['audio_pcm_sha256']==identities['baseline']['audio_pcm_sha256']
    shutil.copy2(ROOT/'output/audience-film/neil-revision.srt',OUT/'correction-tape-remade.srt')
    run(['ffmpeg','-v','error','-y','-i',film,'-vn','-c:a','copy',OUT/'Neil-original.m4a'],OUT/'extract-neil.log')
    covers=OUT/'covers';covers.mkdir(exist_ok=True)
    frames=[]
    for name,time,crop in [('whole',28,(0,155,1920,930)),('contact',85,(0,155,1920,810))]:
        original=covers/(name+'-source.png')
        run(['ffmpeg','-v','error','-y','-ss',str(time),'-i',film,'-frames:v','1','-update','1',original],covers/(name+'.log'))
        with Image.open(original) as image:image.crop(crop).save(covers/(name+'.png'))
        frames.append(dict(time=time,original=ref(original),crop=list(crop),derived=ref(covers/(name+'.png'))))
    plan=dict(title=['没有电机','两卷为什么能配合？'],series='日常机械 · 修正带',
              font_path=selected_font,image_alignment=dict(portrait='top',landscape='center'),portrait_detail_label='同一接触面，两色标记逐渐错开')
    artifacts=[]
    for name,size in SIZES.items():
        target=covers/name
        layout=cover_compose(covers/'whole.png',target,size,plan,[.04,.04,.96,.96],
                             detail=(covers/'contact.png',[.05,.05,.95,.95]) if size[1]>size[0] else None)
        artifacts.append(dict(**ref(target),size=list(size),layout=layout))
    writejson(covers/'manifest.json',dict(film=ref(film),source_frames=frames,artifacts=artifacts,independent_qa='UNKNOWN'))
    writejson(covers/'qa-images.json',visual_packet([prepare_image(covers/name) for name in SIZES]))
    media_files=[film,OUT/'full-dynamic-animatic.mp4',OUT/'core-55-95.mp4',OUT/'core-complete-action.mp4',
                 OUT/'comparison-candidate-vs-new.mp4',OUT/'comparison-neil-vs-new.mp4']
    for media in media_files:
        run(['ffmpeg','-v','error','-xerror','-i',media,'-f','null','-'],media.with_suffix('.decode.log'))
    writejson(OUT/'delivery-manifest.json',dict(status='COMPLETE_MEDIA_WORKPRINT_QA_PENDING',
        media=[ref(p) for p in media_files],audio=ref(OUT/'Neil-original.m4a'),subtitles=ref(OUT/'correction-tape-remade.srt'),
        blueprint=ref(OUT/FINAL_BLUEPRINT),config=ref(OUT/FINAL_CONFIG),sources=ref(OUT/'source-lock.json'),
        covers=ref(covers/'manifest.json'),continuous_viewing='UNKNOWN',listening='UNKNOWN',formal_acceptance='UNKNOWN'))
    reports()


def reports():
    from common import budget,work_budget_limit,probe
    from mechanical_video_next.production_contract import DIMENSIONS
    film=OUT/'correction-tape-remade.mp4'
    media=ref(film)
    bp=read(OUT/FINAL_BLUEPRINT)
    props=read(OUT/'final.props.json')
    records=[]
    for shot in props['shots']:
        sid=shot['id']
        clip=ROOT/'remotion/public'/shot['media']
        record=dict(shot_id=sid,source_media=ref(clip),duration=shot['seconds'],source_type='PROJECT_NATIVE_3D')
        if sid in CHANGED:
            native=read(OUT/FINAL_DIR/(sid+'.render.json'))
            checks=read(native['checks']['path'])
            for field in ['scene_artifact','source_shot']:
                assert filehash(checks[field]['path'])==checks[field]['sha256']
            record.update(render_receipt=ref(OUT/FINAL_DIR/(sid+'.render.json')),
                          scene=checks['scene_artifact'],executable_shot=checks['source_shot'],checks=native['checks'])
        else:
            record['reuse_basis']=ref(ROOT/'output/audience-film/neil-revision-final.props.json')
        records.append(record)
    writejson(OUT/'media-provenance.json',dict(media=media,shots=records,
        composition=ref(OUT/'final.props.json'),remotion_build=ref(film.with_suffix('.build.json')),
        assembly=ref(ASSEMBLY),native_asset=ref(MODEL),source_lock=ref(OUT/'source-lock.json'),
        audio=ref(OUT/'Neil-original.m4a'),decoded_audio=read(OUT/'audio-video-identities.json'),
        scope='Inspectable project-native 3D and original annotations; no historical 3D-only acceptance asserted',
        external_creator_footage_used=False))
    observations={
        'scientific_accuracy':'Same patent implementation and bounded roll law retained; source/numeric checks recorded. Full independent audiovisual scientific review unavailable.',
        'mechanical_motion':'Saved scenes, source tracks and every-frame slip audit provided. These verify prescribed kinematics, not real friction or perceptual clarity.',
        'visual_expression':'Four standalone diagrams replaced with visible native windings; contact shot has larger surface marks and contextual entrance/return. Continuous independent viewing unavailable.',
        'narrative_comprehension':'Original measured Neil/cues retained. Whether viewers understand the causal chain without formulas remains untested.',
        'originality_copyright':'Inherited project-owned geometry, original narration and annotations, located patent research and original rights records retained. No independent new rights review performed.',
        'av_delivery':'Full decoding, actual specs, exact baseline decoded audio and unchanged SRT checked. Complete listening and audiovisual synchronization perception unavailable.'}
    qa=dict(media=media,independent_reviewer=False,reviewer_thread_id=None,
        full_video_reviewed=False,full_audio_listened=False,review_observations=[],
        quality_dimensions={name:dict(status='UNKNOWN',media_sha256=media['sha256'],observation=observations[name]) for name in DIMENSIONS},
        technical_evidence=[ref(OUT/'science-numeric-audit.json'),ref(OUT/FINAL_DIR/'slip.render.scene-audit.json'),
                            ref(OUT/'audio-video-identities.json'),ref(OUT/'decoded-comparison-candidate.json')],
        capability_boundary='Producer document/numeric/decoded-media and sampled-frame checks only. No continuous viewing/listening or independent reviewer was available; zero new agents dispatched.',
        formal_acceptance='UNKNOWN')
    writejson(OUT/'qa-six-dimensions.json',qa)
    question_targets=[('relative_slip','两个相邻表面的错位是否更容易直接看出？'),
        ('radius_speed','同一输带量与不同卷径/转角是否更清楚？'),('less_formula','是否减少对文字和公式的依赖？'),
        ('spatial_layers','空间层次是否明显改善？'),('camera_purpose','镜头进入和退回是否帮助理解？'),
        ('causal_chain','输入、传动与收卷输出是否连成因果链？')]
    writejson(OUT/'comparison-review.json',dict(previous=ref(CANDIDATE),current=media,
        dynamic_comparison=ref(OUT/'comparison-candidate-vs-new.mp4'),
        conclusions={key:dict(question=q,status='UNKNOWN',reason='Requires independent continuous observation of the actual comparison MP4; no score inferred from pixel change') for key,q in question_targets}))
    metrics=[]
    for name in ['core-preview-metrics.json','preview-metrics.json','preview-coils-metrics.json',FINAL_DIR+'-slip-metrics.json',FINAL_DIR+'-route-metrics.json']:
        if (OUT/name).exists():metrics.append(ref(OUT/name))
    resources=dict(work_bytes=budget(),work_limit_bytes=work_budget_limit(),free_disk_bytes=shutil.disk_usage(ROOT).free,
                   minimum_free_disk_bytes=3*1024**3,scope='Final snapshot; not a continuously measured peak')
    writejson(OUT/'production-report.json',dict(media=media,task_id='workflow-acceptance-20261118',
        changed_shots=[dict(shot_id=s['shot_id'],time_range=s['time_range'],goal=s['knowledge_goal']) for s in bp['shots'] if s['shot_id'] in CHANGED],
        retained_shots=['hook','transfer','return_answer'],native_render_metrics=metrics,resources=resources,
        new_agents=0,new_schedulers=0,new_shared_modules=0,tts_requests=0,voice='Reused actual Neil',
        tokens=None,cost=None,interventions=None,producer_native_thread_id=None,
        actual_native_role_model_telemetry=None,formal_acceptance='UNKNOWN',publication='NONE',
        renderer='Blender 5.2.3 EEVEE; native final samples 24, existing Remotion and FFmpeg',
        boundaries=['Prescribed motion, not real friction/tension/spring-force simulation',
                    'Four comparison shots hide upper drive plates editorially to expose the same windings',
                    'Final slip continues transport through the return to the complete assembly; 7.5 mm source range unchanged',
                    'Color and finishes identify components, not a claim of real material composition',
                    'Continuous independent visual/audio/narrative acceptance remains UNKNOWN']))
    writejson(OUT/'growth-report.json',dict(media=media,blueprint=ref(OUT/FINAL_BLUEPRINT),
        covers=ref(OUT/'covers/manifest.json'),standalone_graphic_shots_before=4,standalone_graphic_shots_after=0,
        goals={key:dict(status='UNKNOWN',observed_platform_metrics=None) for key in ['retention','like','save','comment','follow']},
        audience_takeaway='同一条带需要匹配线速度；固定轮缘传动通过允许相对滑动与径向让位协调变化的卷径。',
        limitation='No publication, audience test or invented performance score'))
    task_path=TASK/'task.json';task=read(task_path)
    task.setdefault('audience_visual_revision',{}).update(status='COMPLETE_MEDIA_QA_PENDING',media=media,
        blueprint=ref(OUT/FINAL_BLUEPRINT),manifest=ref(OUT/'delivery-manifest.json'),
        qa=ref(OUT/'qa-six-dimensions.json'),formal_acceptance='UNKNOWN')
    writejson(task_path,task)
    lines=['# 修正带新版交付（完整工作片，待独立视听验收）','',
        f'完整影片：`correction-tape-remade.mp4`，SHA256 `{media["sha256"]}`。',
        '147.233333秒、4417帧、1920×1080/30fps、H.264/AAC。实际媒体全量解码通过；Neil音频的解码PCM与历史基线完全一致。','',
        '- [完整影片](correction-tape-remade.mp4)',
        '- [新版00:55–01:35核心段](core-55-95.mp4) / [含完整动作与条件说明的核心段](core-complete-action.mp4)',
        '- [旧候选与新版同步动态对照，左旧右新](comparison-candidate-vs-new.mp4)',
        '- [历史Neil基线与新版动态对照](comparison-neil-vs-new.mp4)',
        '- [完整动态Animatic](full-dynamic-animatic.mp4)',
        '- [实际Neil音轨](Neil-original.m4a) / [同步字幕](correction-tape-remade.srt)',
        '- [3:4封面](covers/portrait_cover_3x4.png) / [4:3封面](covers/landscape_cover_4x3.png)',
        f'- [完整Blueprint]({FINAL_BLUEPRINT}) / [来源与原生渲染证据](media-provenance.json)',
        '- [六维QA边界](qa-six-dimensions.json) / [生产记录](production-report.json) / [增长报告](growth-report.json)','',
        '主要改动为00:19.233–02:16.133的10镜，重点为00:53.833–01:42.433。四段整页图表改为实际3D卷材及跟随半径线；滑动段从整体进接触面，在同一画面观察蓝橙表面标记错位，再在继续收卷时返回整体。开头、压头与结尾的真实应用镜头保留。','',
        '模型、卷径规律、弹指和运动关系仍来自同一US8746316B2图1–4C。四段比较中上层轮盘只作编辑隐藏，并非真实拆装；接触与滑动镜头保留完整轮缘。正式尺寸版提高采样、减弱过曝高光，并让滑动镜头的收卷动作持续到回退结束；预览及失败记录保留。','',
        '尚未解决：没有连续视听能力，也没有本轮独立评审身份。科学、机械、视觉、叙事、权利与视听六维正式结论均为UNKNOWN；不能用逐帧数据、抽帧和解码通过代替看完听完。本片尺寸、弹指偏移及滑移量是原有规定运动和简化取值，不是实测或物理仿真。透明部件残余颗粒、连续镜头节奏和实际理解效果仍需观看当前确切MP4核实。没有评分、发布或正式DELIVERED登记。','']
    (OUT/'DELIVERY.md').write_text('\n'.join(lines))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('phase',choices=['prepare','compile','reveal-coils','final-plan','keys','final-keys','preview','final','core-preview','compose-preview','compose-final','package'])
    p.add_argument('--shots',nargs='+')
    a=p.parse_args()
    if a.phase=='prepare':prepare()
    elif a.phase=='compile':compile_plan()
    elif a.phase=='final-plan':final_plan()
    elif a.phase=='reveal-coils':reveal_coils()
    elif a.phase=='core-preview':compose('preview',core_only=True)
    elif a.phase=='package':package()
    elif a.phase.startswith('compose-'):compose(a.phase.split('-')[1])
    else:render_shots(a.phase,a.shots or CHANGED)
