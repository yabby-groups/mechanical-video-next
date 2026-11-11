#!/usr/bin/env python3
"""Author one-shot CAD diagnostics for the existing EAS scene renderer.

No Blender process, geometry generation, contact solving, or production approval.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return json.loads(path.read_text())


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--assembly', type=Path, required=True)
    ap.add_argument('--motion', type=Path, required=True)
    ap.add_argument('--section-assembly', type=Path)
    ap.add_argument('--output-prefix', type=Path, required=True)
    ap.add_argument('--manifest', type=Path, required=True)
    args = ap.parse_args()
    assembly, motion = read(args.assembly), read(args.motion)
    parts = assembly['required_parts']
    poses = {m['name']: {k: m.get(k, [0, 0, 0]) for k in ('location', 'rotation_euler')}
             for m in assembly['meshes']}
    assert set(parts) == set(poses), 'Every CAD part needs an explicit pose'
    assert assembly['units'] in ('m', 'meters', 'metres'), 'Renderer receives meters'
    # Source close/open cycle must contain a monotonic slider half-cycle.
    driver = next(t for t in motion['tracks'] if t['object'] == 'slider_lower')
    peak = max(range(len(driver['poses'])), key=lambda i: driver['poses'][i]['location'][1])
    assert 1 < peak < len(driver['poses']) - 2
    assert all(driver['poses'][i]['location'][1] <= driver['poses'][i+1]['location'][1]
               for i in range(peak))
    assert all(driver['poses'][i]['location'][1] >= driver['poses'][i+1]['location'][1]
               for i in range(peak, len(driver['poses'])-1))
    style = {'visual_profile': 'printer-ep03-studio-v1', 'camera_view': 'oblique',
             'camera_direction': [0, -0.4, 1], 'camera_roll': 90,
             'studio_lighting': {'scale_to_subject': True, 'floor_gap': 0.002}}
    shots = {'assembly': dict(style, template='overall', seconds=1)}
    # Explicit rigid offsets are a visualization layout, never claimed dismantling paths.
    exploded = []
    for name, pose in poses.items():
        end = copy.deepcopy(pose)
        loc = end['location']
        if name.startswith('tooth_'):
            loc[0] += -0.012 if '_L_' in name else 0.012
            loc[2] += 0.008
        elif name.startswith('slider_'):
            loc[2] += {'slider_lower': -0.008, 'slider_upper': 0.018,
                       'slider_wedge': 0.008, 'slider_flange_L': 0.011,
                       'slider_flange_R': 0.014}[name]
        elif name in ('pull', 'pull_pin'):
            loc[2] += 0.027 if name == 'pull' else 0.023
        exploded.append({'object': name, 'poses': [dict(progress=0, **pose), dict(progress=1, **end)]})
    frozen_meshes = []
    for track in motion.get('mesh_tracks', []):
        pose = copy.deepcopy(track['poses'][0])
        frozen_meshes.append({'object': track['object'],
                              'poses': [dict(pose, progress=0), dict(pose, progress=1)]})
    shots['exploded'] = dict(style, template='motion', seconds=3, tracks=exploded,
                            mesh_tracks=frozen_meshes,
                            scope='Exploded visualization offsets; not physical removal paths')
    for label, lo, hi in [('close', 0, peak), ('open', peak, len(driver['poses'])-1)]:
        tracks = []
        for track in motion['tracks']:
            selected = copy.deepcopy(track['poses'][lo:hi+1])
            for i, pose in enumerate(selected):
                pose['progress'] = i/(len(selected)-1)
            tracks.append({'object': track['object'], 'poses': selected})
        mesh_tracks = []
        for track in motion.get('mesh_tracks', []):
            selected = copy.deepcopy(track['poses'][lo:hi+1])
            assert len(track['poses']) == len(driver['poses']), 'Mesh and rigid samples must align'
            for i, pose in enumerate(selected):
                pose['progress'] = i/(len(selected)-1)
            mesh_tracks.append({'object': track['object'], 'poses': selected})
        # Deliberate removed-cover view: retains the real lower guide, wedge,
        # flanges and both tooth rows. It is not labeled a physical cross-section.
        removed = {'slider_upper', 'pull', 'pull_pin'}
        visible = [n for n in parts if n not in removed and not n.startswith('crown_')]
        shots[label] = dict(style, template='motion', seconds=4, tracks=tracks,
                            mesh_tracks=mesh_tracks, visible_parts=visible,
                            observation_view='Upper cover, crown and pull explicitly removed for observation',
                            scope=motion.get('scope'), source_pose_indices=[lo, hi])
    manifests = []
    for label, shot in shots.items():
        path = Path(str(args.output_prefix) + '-' + label + '.json')
        cfg = {'id': path.stem, 'asset': assembly.get('id', 'zipper-parametric-v1'),
               'assembly_config': str(args.assembly), 'title': '自主CAD拉链诊断',
               'subtitle': '原理示意 · 规定路径 · 非接触仿真 · 简化布带支撑', 'voice': 'Neil', 'channel': '视频号',
               'narration_profile': 'config/narration-neil.json',
               'render': {'width': 1920, 'height': 1080, 'fps': 30, 'video': 'h264',
                          'audio': 'aac', 'framing': 'fullframe', 'preview_native': False},
               'components': parts, 'motion_template': 'data-keyframes-v1',
               'explosion_sequence': [], 'local_preview_shots': [label], 'shots': {label: shot},
               'storyboard': [{'id': label, 'shot': label, 'seconds': shot['seconds'],
                               'narration': ['原理示意'], 'subtitles': ['原理示意']}]}
        write(path, cfg)
        manifests.append({'shot_id': label, 'config': str(path),
                          'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                          'media': None, 'status': 'CONFIG_ONLY_UNRENDERED'})
    if args.section_assembly:
        section = read(args.section_assembly)
        cfg = copy.deepcopy(cfg)
        section_pose = peak//2
        section_tracks = []
        for track in motion['tracks']:
            pose = copy.deepcopy(track['poses'][section_pose])
            section_tracks.append({'object': track['object'], 'poses': [dict(pose, progress=0), dict(pose, progress=1)]})
        section_mesh_tracks = []
        for track in motion.get('mesh_tracks', []):
            pose = copy.deepcopy(track['poses'][section_pose])
            section_mesh_tracks.append({'object': track['object'], 'poses': [dict(pose, progress=0), dict(pose, progress=1)]})
        cfg.update(id=args.output_prefix.name+'-section', asset=section['id'],
                   assembly_config=str(args.section_assembly), components=section['required_parts'],
                   local_preview_shots=['section'],
                   shots={'section': dict(style, template='motion', seconds=1,
                                          tracks=section_tracks, mesh_tracks=section_mesh_tracks,
                                          visible_parts=[n for n in section['required_parts']
                                                         if n not in ('pull', 'pull_pin') and not n.startswith('crown_')],
                                          scope='Actual CAD Boolean section; pull/pin hidden for visibility; teaching section, not a disassembly claim')},
                   storyboard=[{'id': 'section', 'shot': 'section', 'seconds': 1,
                                'narration': ['教学剖切 · 原理示意'], 'subtitles': ['教学剖切 · 原理示意']}])
        path=Path(str(args.output_prefix)+'-section.json')
        write(path,cfg)
        manifests.append({'shot_id':'section','config':str(path),
                          'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
                          'media':None,'status':'CONFIG_ONLY_UNRENDERED'})
    write(args.manifest, {'schema': 'animation-manifest-v1', 'status': 'CONFIG_ONLY_UNRENDERED',
                         'shots': manifests, 'keys': [], 'preview': None,
                         'input_hashes': {str(p): hashlib.sha256(p.read_bytes()).hexdigest()
                                          for p in [args.assembly, args.motion,
                                                    *([args.section_assembly] if args.section_assembly else []),
                                                    Path(__file__).resolve().relative_to(ROOT)]},
                         'limitations': ['No Blender run, motion or visual acceptance yet',
                                          'Prescribed transforms and tape shape samples are not contact/force simulation',
                                          'Raw scene media has no text overlays; required teaching labels must be composed before review',
                                          'Mechanical and independent animatic QA required before HD/full preview'],
                         'telemetry': {'tokens': None, 'cost': None}})


if __name__ == '__main__':
    main()
