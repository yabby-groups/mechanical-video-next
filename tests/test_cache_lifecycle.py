"""Isolated safety tests; real FFmpeg, no Blender/CAD render or production mutations."""
import ast
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
import clean


class LifecycleTests(unittest.TestCase):
    def test_qa_references_and_protected_media_and_idempotence(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            protected = ['assets/original.step', 'work/cache/audio/voice.wav',
                         'output/2d.mp4', 'output/2.5d.mp4', 'output/3d.mp4',
                         'output/cover-3x4.jpg', 'output/cover-4x3.jpg', 'output/growth.json']
            for name in protected:
                p = root/name; p.parent.mkdir(parents=True, exist_ok=True); p.write_bytes(b'protected')
            for digit in ('a', 'b'):
                folder = root/'work/qa-images'; folder.mkdir(parents=True, exist_ok=True)
                image = folder/(digit*64+'.webp'); image.write_bytes(digit.encode())
                marker = image.with_suffix('.json')
                marker.write_text(json.dumps({'qa_path':str(image), 'qa_sha256':hashlib.sha256(image.read_bytes()).hexdigest()}))
                for p in (image, marker): os.utime(p, (1,1))
            (root/'output/qa.json').write_text(json.dumps({'qa_path':str(folder/('a'*64+'.webp'))}))
            with patch.object(clean, 'ROOT', root):
                rows = clean.cleanup(0, apply=True)
                self.assertEqual(sum(r['bytes'] for r in rows if r['delete']), 1+len(json.dumps({'qa_path':str(folder/('b'*64+'.webp')), 'qa_sha256':hashlib.sha256(b'b').hexdigest()})))
                self.assertEqual(clean.cleanup(0, apply=True), [])
            self.assertTrue((folder/('a'*64+'.webp')).exists())
            for name in protected: self.assertEqual((root/name).read_bytes(), b'protected')

    def test_scene_geometry_camera_and_motion_functions_unchanged(self):
        old = subprocess.check_output(['git', 'show', 'HEAD:blender/scene.py']).decode()
        current = Path('blender/scene.py').read_text()
        def visual_tree(source):
            tree = ast.parse(source)
            return {n.name: ast.dump(n) for n in tree.body if isinstance(n, ast.FunctionDef)
                    and n.name not in {'render_chunked', 'savejson'}}
        self.assertEqual(visual_tree(old), visual_tree(current))

    def chunk_function(self):
        source = Path('blender/scene.py').read_text()
        tree = ast.parse(source)
        node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'render_chunked')
        namespace = dict(json=json, time=time, subprocess=subprocess, os=os, hashlib=hashlib, Path=Path,
                         savejson=lambda p,d: Path(p).write_text(json.dumps(d)))
        exec(compile(ast.Module(body=[node], type_ignores=[]), 'chunk-test', 'exec'), namespace)
        return namespace

    def run_chunk(self, root, fail=False):
        ns = self.chunk_function()
        scene = SimpleNamespace(render=SimpleNamespace(filepath=None), frame_set=lambda f: None)
        ns['bpy'] = SimpleNamespace(ops=SimpleNamespace(render=SimpleNamespace(render=lambda **kw: Image.new('RGB',(32,32),'blue').save(scene.render.filepath))))
        args = SimpleNamespace(chunk_frames=2, video_output=root/'video.mp4', out=root/'frames', fps=30, width=32, height=32)
        if fail:
            with patch.object(subprocess, 'run', side_effect=subprocess.CalledProcessError(1,'ffmpeg')):
                with self.assertRaises(subprocess.CalledProcessError): ns['render_chunked'](scene, range(1,5), args)
        else:
            ns['render_chunked'](scene, range(1,5), args)
        return args

    def test_real_encoding_removes_only_owned_frames_and_chunks(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); original=root/'original.png'; original.write_bytes(b'original')
            args=self.run_chunk(root)
            self.assertEqual(list(args.out.rglob('*.png')), [])
            self.assertEqual(list(args.out.rglob('chunk-*.mp4')), [])
            report=json.loads((args.out/'chunk-result.json').read_text())
            self.assertEqual(report['status'], 'PASS')
            self.assertEqual(report['deleted_files'], 7)
            self.assertGreater(report['deleted_bytes'], 0)
            self.assertEqual(original.read_bytes(), b'original')
            subprocess.run(['ffmpeg','-v','error','-xerror','-i',str(args.video_output),'-f','null','-'], check=True)

    def test_resume_reuses_verified_chunk_after_later_encode_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ns = self.chunk_function()
            scene = SimpleNamespace(render=SimpleNamespace(filepath=None), frame_set=lambda f: None)
            renders = []
            def render(**kw):
                renders.append(scene.render.filepath)
                Image.new('RGB', (32,32), 'blue').save(scene.render.filepath)
            ns['bpy'] = SimpleNamespace(ops=SimpleNamespace(render=SimpleNamespace(render=render)))
            args = SimpleNamespace(chunk_frames=2, video_output=root/'video.mp4', out=root/'frames', fps=30, width=32, height=32)
            real_run = subprocess.run
            encodes = []
            def fail_second(argv, **kwargs):
                if '-framerate' in argv:
                    encodes.append(argv)
                    if len(encodes) == 2:
                        raise subprocess.CalledProcessError(1, argv)
                return real_run(argv, **kwargs)
            with patch.object(subprocess, 'run', side_effect=fail_second):
                with self.assertRaises(subprocess.CalledProcessError):
                    ns['render_chunked'](scene, range(1,5), args)
            ns['render_chunked'](scene, range(1,5), args)
            self.assertEqual(len(renders), 6)  # first successful block never rerendered
            self.assertEqual(json.loads((args.out/'chunk-result.json').read_text())['status'], 'PASS')

    def test_encoding_failure_retains_frames_for_recovery(self):
        with tempfile.TemporaryDirectory() as tmp:
            args=self.run_chunk(Path(tmp), fail=True)
            self.assertEqual(len(list(args.out.rglob('*.png'))), 2)
            report=json.loads(next(args.out.rglob('report.json')).read_text())
            self.assertEqual(report['status'],'FAIL')

    def test_housekeeping_change_preserves_scene_cache_identity(self):
        import common
        equivalence=json.loads(Path('config/cache-code-equivalence.json').read_text())['blender/scene.py']
        self.assertEqual(common.filehash(Path('blender/scene.py')), equivalence['current_sha256'])
        self.assertEqual(common.codehash('blender/scene.py'), common.digest({'blender/scene.py':equivalence['media_equivalent_sha256']}))
