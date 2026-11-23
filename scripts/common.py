"""Small, content-addressed pipeline utilities. No task database or agents."""
from contextlib import contextmanager
from contextvars import ContextVar
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import threading
import time

ROOT = Path(__file__).resolve().parents[1]
input_hashes = ContextVar('input_hashes', default=None)
active_budget = ContextVar('active_budget', default=None)


class CleanupBusy(RuntimeError):
    """Optional cleanup overlaps active production or rendering."""


def hashed_inputs(path, sha256):
    observed = input_hashes.get()
    if observed is None:
        return
    path = str(Path(path).resolve())
    if observed.setdefault(path, sha256) != sha256:
        raise ValueError('Production dependency changed during stage validation: ' + path)

def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()

def filehash(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    result = h.hexdigest()
    hashed_inputs(path, result)
    return result

def codehash(*paths, equivalents=True, render_media=False):
    files = []
    for p in paths:
        p = ROOT / p
        files += sorted(p.rglob('*.py')) if p.is_dir() else [p]
    hashes = {str(p.relative_to(ROOT)): filehash(p) for p in files}
    equivalence = ROOT/'config/cache-code-equivalence.json'
    if (equivalents or render_media) and equivalence.exists():
        for name, item in json.loads(equivalence.read_text()).items():
            runtime = item.get('render_orchestration')
            if render_media and runtime and hashes.get(name) == runtime['current_sha256']:
                hashes[name] = runtime['previous_sha256']
            if equivalents and hashes.get(name) == item['current_sha256']:
                hashes[name] = item['media_equivalent_sha256']
    return digest(hashes)

def writejson(path, value):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')

def execute(args, **options):
    """Run a child with cancellable process-group ownership during production."""
    guard = active_budget.get()
    if guard is None:
        return subprocess.run(args, **options)
    guard.sample()
    check = options.pop('check', False)
    with subprocess.Popen(args, process_group=0, **options) as process:
        try:
            while True:
                try:
                    stdout, stderr = process.communicate(timeout=0.25)
                    break
                except subprocess.TimeoutExpired:
                    guard.check()
        except BaseException as error:
            from mechanical_video_next.blender_runtime import stop_process_group
            previous = process.poll()
            if previous not in (None, 0):
                error.add_note(f'Child exited with status {previous} before cancellation')
            for detail in stop_process_group(process):
                error.add_note(detail)
            raise
        result = subprocess.CompletedProcess(args, process.returncode, stdout, stderr)
        if check:
            result.check_returncode()
        guard.sample()
        return result


def check_output(args, **options):
    return execute(args, stdout=subprocess.PIPE, check=True, **options).stdout


def run(args, log=None, cwd=ROOT):
    if log:
        Path(log).parent.mkdir(parents=True, exist_ok=True)
        with open(log, 'w') as f:
            execute([str(a) for a in args], cwd=cwd, stdout=f, stderr=subprocess.STDOUT, check=True)
    else:
        execute([str(a) for a in args], cwd=cwd, check=True)

def probe(path):
    return json.loads(check_output(['ffprobe','-v','error','-show_streams','-show_format','-of','json',str(path)]))

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

class BudgetExceeded(RuntimeError):
    def __init__(self, message, **observation):
        super().__init__(message)
        self.observation = observation


def sample_budget():
    used = treebytes(ROOT / 'work')
    limit = work_budget_limit()
    free = shutil.disk_usage(ROOT).free
    minimum = 3 * 1024**3
    observation = dict(work_bytes=used, work_limit_bytes=limit,
                       free_disk_bytes=free, minimum_free_disk_bytes=minimum)
    if used > limit:
        raise BudgetExceeded(f'work budget exceeded: {used} > {limit}; use explicit clean command', **observation)
    if free < minimum:
        raise BudgetExceeded('Less than 3 GiB free; stop before generating media', **observation)
    return used


def budget():
    guard = active_budget.get()
    return guard.sample() if guard else sample_budget()


def check_budget():
    guard = active_budget.get()
    if guard is not None:
        guard.check()


class StageBudget:
    def __init__(self, metrics):
        self.metrics = metrics
        self.error = None
        self.mutex = threading.Lock()

    def check(self):
        with self.mutex:
            if self.error is not None:
                if isinstance(self.error, BudgetExceeded):
                    raise BudgetExceeded(str(self.error), **self.error.observation)
                raise RuntimeError(str(self.error)) from self.error

    def sample(self):
        self.check()
        try:
            used = sample_budget()
        except Exception as error:
            with self.mutex:
                self.error = self.error or error
                if isinstance(error, BudgetExceeded):
                    self.metrics.peak = max(self.metrics.peak, error.observation['work_bytes'])
            raise
        with self.mutex:
            self.metrics.peak = max(self.metrics.peak, used)
        self.check()
        return used

    def monitor(self, stopped):
        while not stopped.wait(0.5):
            try:
                self.sample()
            except Exception:
                return


@contextmanager
def budgeted_stage(metrics):
    guard = StageBudget(metrics)
    token = active_budget.set(guard)
    stopped = threading.Event()
    thread = threading.Thread(target=guard.monitor, args=(stopped,), daemon=True)
    thread.start()
    failure = None
    try:
        guard.sample()
        yield
    except BaseException as error:
        failure = error
        if isinstance(error, BudgetExceeded):
            with guard.mutex:
                guard.error = guard.error or error
        raise
    finally:
        stopped.set()
        thread.join()
        try:
            try:
                guard.sample()
            except Exception:
                if failure is None:
                    raise
        finally:
            metrics.budget_error = guard.error
            active_budget.reset(token)

class Metrics:
    def __init__(self, name, *, defer_budget=False):
        self.name = name
        self.start = time.time()
        self.rows = []
        self.peak = 0 if defer_budget else budget()
        self.budget_error = None

    def record(self, stage, start, hit=False, **extra):
        used = budget()
        if active_budget.get() is None:
            self.peak = max(self.peak, used)
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
