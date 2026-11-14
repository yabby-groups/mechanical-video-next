"""Small, content-addressed pipeline utilities. No task database or agents."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]
BLENDER = os.environ.get('BLENDER', '/Applications/Blender.app/Contents/MacOS/Blender')

def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()

def filehash(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()

def codehash(*paths):
    files = []
    for p in paths:
        p = ROOT / p
        files += sorted(p.rglob('*.py')) if p.is_dir() else [p]
    hashes = {str(p.relative_to(ROOT)): filehash(p) for p in files}
    equivalence = ROOT/'config/cache-code-equivalence.json'
    if equivalence.exists():
        for name, item in json.loads(equivalence.read_text()).items():
            if hashes.get(name) == item['current_sha256']:
                hashes[name] = item['media_equivalent_sha256']
    return digest(hashes)

def writejson(path, value):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')

def run(args, log=None, cwd=ROOT):
    if log:
        Path(log).parent.mkdir(parents=True, exist_ok=True)
        with open(log, 'w') as f:
            subprocess.run([str(a) for a in args], cwd=cwd, stdout=f, stderr=subprocess.STDOUT, check=True)
    else:
        subprocess.run([str(a) for a in args], cwd=cwd, check=True)

def probe(path):
    return json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-show_format','-of','json',str(path)]))

def treebytes(path):
    # Remotion removes its temporary folders while the disk sampler is running.
    # os.walk skips vanished directories; skip files removed between listing/stat.
    total = 0
    for directory, _, files in os.walk(path, followlinks=False):
        for name in files:
            p = Path(directory) / name
            try:
                if not p.is_symlink():
                    total += p.stat().st_size
            except FileNotFoundError:
                continue
    return total

def work_budget_limit():
    """Default 2 GiB; an explicitly authorized run may supply a byte limit."""
    value = int(os.environ.get('MVN_WORK_LIMIT_BYTES', 2 * 1024**3))
    if value <= 0:
        raise ValueError('MVN_WORK_LIMIT_BYTES must be positive')
    return value

def budget():
    used = treebytes(ROOT / 'work')
    limit = work_budget_limit()
    if used > limit:
        raise RuntimeError(f'work budget exceeded: {used} > {limit}; use explicit clean command')
    if __import__('shutil').disk_usage(ROOT).free < 3 * 1024**3:
        raise RuntimeError('Less than 3 GiB free; stop before generating media')
    return used

class Metrics:
    def __init__(self, name):
        self.name = name
        self.start = time.time()
        self.rows = []
        self.peak = budget()

    def record(self, stage, start, hit=False, **extra):
        self.peak = max(self.peak, budget())
        row = dict(stage=stage, seconds=round(time.time()-start,3), cache_hit=hit, **extra)
        self.rows.append(row)
        print(json.dumps(row, ensure_ascii=False), flush=True)

    def finish(self, **extra):
        cleanup_rows = getattr(self, 'cleanup_rows', [])
        cache_report = dict(generated_temp_bytes=sum(r.get('generated_temp_bytes', 0) for r in cleanup_rows),
                            automatically_deleted_files=sum(r.get('deleted_files', 0) for r in cleanup_rows),
                            automatically_deleted_bytes=sum(r.get('deleted_bytes', 0) for r in cleanup_rows),
                            measurement_scope='Blender chunk temporary files executed in this run; other producers not measured',
                            retained_cache_bytes=treebytes(ROOT/'work/cache') + treebytes(ROOT/'work/qa-images'),
                            protected_asset_bytes=treebytes(ROOT/'assets') + treebytes(ROOT/'output'),
                            cache_hits=sum(bool(r.get('cache_hit')) for r in self.rows),
                            peak_work_sampled_bytes=self.peak,
                            failures_and_skips=[e for r in cleanup_rows for e in r.get('cleanup_errors', [])])
        value = dict(cache_cleanup=cache_report, name=self.name, started_epoch=self.start, total_seconds=round(time.time()-self.start,3),
                     stages=self.rows, temp_peak_sampled_bytes=self.peak, **extra)
        writejson(ROOT / 'output' / (self.name + '-metrics.json'), value)
        return value
