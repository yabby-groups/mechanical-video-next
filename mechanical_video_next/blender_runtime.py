"""Run Blender in the caller's login session and retain evidence per invocation."""

from contextlib import contextmanager
import fcntl
from functools import lru_cache
import json
import math
import os
from pathlib import Path
import platform
import re
import shutil
import signal
import subprocess
import tempfile
import time

from scripts.common import ROOT, writejson


DEFAULT_BLENDER = '/Applications/Blender.app/Contents/MacOS/Blender'
DIAGNOSTICS = ROOT / 'output/render-diagnostics'
SANITIZED = {'LD_LIBRARY_PATH', 'LD_PRELOAD', 'LD_AUDIT', 'VIRTUAL_ENV',
             '__PYVENV_LAUNCHER__'}
GRAPHICS_GUIDANCE = (
    'Run the same command from the logged-in macOS desktop with access to Metal. '
    'In Codex use the authorized native execution route if this executor cannot see Metal. '
    'An Aqua bootstrap domain alone does not establish Metal access.'
)


class BlenderFailure(subprocess.CalledProcessError):
    def __init__(self, result):
        super().__init__(result['returncode'], result['command'])
        self.result = result

    def __str__(self):
        row = self.result
        message = f"{row['classification']} ({row['signal'] or row['status']}), see {row['report']}"
        if row['classification'] == 'GRAPHICS_INIT_ERROR' and row['environment']['system'] == 'Darwin':
            message += '. ' + GRAPHICS_GUIDANCE
        if row.get('fallback_report'):
            message += '. Fallback review: ' + row['fallback_report']
        return message


def blender_executable():
    value = os.environ.get('BLENDER', DEFAULT_BLENDER)
    candidate = shutil.which(os.path.expanduser(value))
    if not candidate:
        raise FileNotFoundError(f'Blender executable missing or not executable: {value}')
    return Path(candidate).resolve(strict=True)


def blender_version_output():
    executable = blender_executable()
    return _read_version(executable, executable.stat().st_mtime_ns)


@lru_cache(maxsize=4)
def _read_version(executable, mtime_ns):
    result = run_blender(['--version'], name='blender-version', background=False, timeout=20)
    return Path(result['stdout']).read_text()


def execution_environment():
    env = os.environ.copy()
    removed = sorted(key for key in env if key in SANITIZED or key.startswith(('PYTHON', 'DYLD_')))
    for key in removed:
        env.pop(key)
    system = platform.system()
    info = {'system': system, 'release': platform.release(), 'architecture': platform.machine(),
            'uid': os.getuid(), 'removed_variables': removed,
            'gui_domain_available': None, 'console_uid': None, 'bootstrap_manager': None,
            'parent_pid': os.getppid(), 'tty': os.isatty(0)}
    if system == 'Darwin':
        info['macos_version'] = platform.mac_ver()[0]
        try:
            info['console_uid'] = Path('/dev/console').stat().st_uid
            for name, args in (
                ('bootstrap_manager', ['managername']),
                ('gui_domain_available', ['print', f'gui/{os.getuid()}']),
            ):
                probe = subprocess.run(['/bin/launchctl', *args], env=env, capture_output=True,
                                       text=True, timeout=3)
                info[name] = (probe.stdout.strip() or None) if name == 'bootstrap_manager' else probe.returncode == 0
                if probe.returncode:
                    info[name + '_error'] = probe.stderr.strip()
        except (OSError, subprocess.TimeoutExpired) as exc:
            info['session_probe_error'] = str(exc)
    return env, info


@contextmanager
def blender_slot():
    # Production already holds production.lock at stage level. This lock also
    # covers stand-alone Blender callers without reacquiring the stage lock.
    path = ROOT / 'work/blender-render.lock'
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a') as handle:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield handle


def stop_process_group(process, *, grace=2):
    errors = []
    for sig in (signal.SIGTERM, signal.SIGKILL):
        try:
            os.killpg(process.pid, sig)
        except ProcessLookupError:
            break
        except PermissionError as exc:
            errors.append(f'Process group {sig.name}: {exc}')
            try:
                process.send_signal(sig)
            except PermissionError as direct_error:
                errors.append(f'Blender PID {sig.name}: {direct_error}')
        if sig == signal.SIGTERM and grace:
            try:
                process.wait(timeout=grace)
            except subprocess.TimeoutExpired:
                pass
    try:
        process.wait(timeout=grace)
    except subprocess.TimeoutExpired:
        errors.append('Blender PID did not exit after cleanup signals')
    return errors


def _tail(path):
    with path.open('rb') as stream:
        stream.seek(max(0, path.stat().st_size - 2_000_000))
        return stream.read().decode('utf-8', errors='replace')


def _native_crash_reports(destination, pid, started, stdout, stderr, system):
    reports = []
    # Blender reports its own crash file in the log. Copy before another
    # process can reuse the default crash filename.
    for filename in re.findall(r'(?:Writing:|Writing crash report to:)\s*"?([^\n"]+?\.crash\.txt)', stdout + '\n' + stderr):
        source = Path(filename)
        if source.is_absolute() and source.is_file() and source.stat().st_mtime >= started - 1:
            reports.append(shutil.copy2(source, destination / source.name))
    if system != 'Darwin' or pid is None:
        return reports
    directory = Path.home() / 'Library/Logs/DiagnosticReports'
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline:
        for source in directory.glob('*Blender*.ips'):
            try:
                if source.stat().st_mtime < started - 2:
                    continue
                raw = source.read_text(errors='replace')
                _, _, body = raw.partition('\n')
                if json.loads(body).get('pid') == pid:
                    reports.append(shutil.copy2(source, destination / source.name))
                    return reports
            except (OSError, ValueError):
                continue
        time.sleep(.15)
    return reports


def render_crash_report(result, directory, started, stdout, stderr):
    """Classify from specific emitted evidence, independent of signal status."""
    directory = Path(directory)
    rows = [stdout, stderr, result.get('launch_error') or '']
    if result['process_crash']:
        try:
            reports = _native_crash_reports(directory, result['pid'], started, stdout, stderr,
                                            result['environment']['system'])
            for report in reports:
                rows.append(Path(report).read_text(errors='replace'))
            result['crash_logs'] = [str(p) for p in reports]
        except OSError as exc:
            result['crash_log_collection_error'] = str(exc)
    lines = '\n'.join(rows)

    def match(pattern):
        return re.search(pattern, lines, re.IGNORECASE)

    rules = (
        ('ENVIRONMENT_ERROR', r'PermissionError: [^\n]+|Operation not permitted|Permission denied|dyld[^\n]*Library not loaded|FileNotFoundError: [^\n]*ffmpeg'),
        ('RESOURCE_ERROR', r'No space left on device|Insufficient work budget[^\n]*|Out of memory|cannot allocate memory|std::bad_alloc|MemoryError|Disk quota exceeded'),
        ('GRAPHICS_INIT_ERROR', r'RuntimeError: MVN_GRAPHICS_INIT_ERROR: [^\n]+|Could not initialize (?:Metal|Vulkan|OpenGL)[^\n]*|no default Metal device available|(?:failed|unable) to create (?:an? )?(?:GPU|offscreen|Metal|OpenGL|Vulkan) (?:context|device)|(?:Metal|GPU) initialization failed'),
        ('ENGINE_ERROR', r'MVN_ENGINE_UNSUPPORTED: [^\n]+|MVN_RENDER_ERROR: [^\n]+|CUDA (?:error|device not found)[^\n]*|HIP error[^\n]*|Error (?:opening|compiling) Metal[^\n]*|no compatible (?:Cycles|Metal) device[^\n]*|(?:Eevee|Cycles)[^\n]*(?:is not supported|not supported on this)'),
        ('SCENE_ERROR', r'MVN_SCENE_ERROR: [^\n]+|Cannot read (?:blend|file)[^\n]*|File (?:format )?is not supported[^\n]*|No camera found[^\n]*|Error: Cannot open file[^\n]*'),
    )
    if result.get('launch_error'):
        result.update(classification='ENVIRONMENT_ERROR', evidence=[result['launch_error']])
    elif result['status'] == 'TIMEOUT':
        result.update(classification='RESOURCE_ERROR', evidence=[f"Wall-clock timeout {result['timeout_seconds']:g}s"])
    else:
        graphics_stack = 'WM_init_gpu_offscreen' in lines and (
            'GHOST_SystemCocoa' in lines or 'gpu::metal' in lines
        )
        if graphics_stack and result['process_crash']:
            result.update(classification='GRAPHICS_INIT_ERROR',
                          evidence=['Native stack contains WM_init_gpu_offscreen and Cocoa/Metal initialization'])
        for category, pattern in rules:
            found = match(pattern)
            if found:
                result.setdefault('classification', category)
                result.setdefault('evidence', []).append(found.group(0))
        result.setdefault('classification', 'UNKNOWN_CRASH')
        result.setdefault('evidence', ['No specific cause established by logs'])
    writejson(directory / 'render_crash_report.json', result)


def _markers(stdout):
    rows = []
    for line in stdout.splitlines():
        if line.startswith('MVN_RENDER '):
            try:
                rows.append(json.loads(line.removeprefix('MVN_RENDER ')))
            except ValueError:
                continue
    return rows


def run_blender(args, *, name='blender', log=None, directory=None, timeout=None,
                cwd=ROOT, background=True, allow_failure=False, engine=None):
    """Return a persisted attempt receipt. Negative exits retain the raw signal."""
    if timeout is None:
        timeout = float(os.environ.get('MVN_BLENDER_TIMEOUT_SECONDS', '3600'))
    if not math.isfinite(timeout) or timeout <= 0:
        raise ValueError('Blender timeout must be positive and finite')
    if directory is None:
        DIAGNOSTICS.mkdir(parents=True, exist_ok=True)
        directory = Path(tempfile.mkdtemp(prefix=f'{name}-', dir=DIAGNOSTICS))
    else:
        directory = Path(directory).resolve()
        directory.mkdir(parents=True, exist_ok=False)
    stdout, stderr = directory / 'stdout.log', directory / 'stderr.log'
    env, environment = execution_environment()
    command = [str(a) for a in args]
    if background:
        command[:0] = ['-b']
    configured = os.environ.get('BLENDER', DEFAULT_BLENDER)
    command.insert(0, configured)
    started, monotonic = time.time(), time.monotonic()
    process = None
    returncode, launch_error, timed_out = None, None, False
    cleanup_errors = []
    with stdout.open('wb') as out, stderr.open('wb') as err:
        try:
            command[0] = str(blender_executable())
            with blender_slot() as slot:
                # setpgid retains the parent login session while allowing
                # Blender and its helpers to be reaped as one process group.
                process = subprocess.Popen(command, cwd=cwd, env=env, stdin=subprocess.DEVNULL,
                                           stdout=out, stderr=err, process_group=0,
                                           pass_fds=(slot.fileno(),))
                try:
                    returncode = process.wait(timeout=timeout)
                except subprocess.TimeoutExpired:
                    timed_out = True
                finally:
                    if process.returncode != 0:
                        cleanup_errors = stop_process_group(process)
                        returncode = process.returncode
        except BlockingIOError:
            launch_error = 'Another Blender invocation holds work/blender-render.lock'
        except OSError as exc:
            launch_error = str(exc)

    output, errors = _tail(stdout), _tail(stderr)
    # Large renders can push the version and initial marker out of the tail.
    with stdout.open('rb') as stream:
        header = stream.read(64_000).decode('utf-8', errors='replace')
    markers = _markers(header)
    if stdout.stat().st_size > 64_000:
        markers.extend(row for row in _markers(output) if row not in markers)
    version = re.search(r'\bBlender (\d+\.\d+[^\s(]*)', output + '\n' + header)
    native_signal = signal.Signals(-returncode).name if returncode is not None and returncode < 0 else None
    probe = next((m for m in markers if m.get('phase') == 'preflight_start'), {})
    result = dict(name=name, command=command, pid=process.pid if process else None,
                  status='TIMEOUT' if timed_out else 'PASS' if returncode == 0 else 'FAIL',
                  returncode=returncode, signal=native_signal, process_crash=bool(native_signal and not timed_out),
                  duration_seconds=round(time.monotonic() - monotonic, 3), timeout_seconds=timeout,
                  blender_version=next((m.get('version') for m in markers if m.get('version')),
                                       version.group(1) if version else None),
                  engine=probe.get('engine', engine), events=markers, environment=environment,
                  launch_error=launch_error, stdout=str(stdout), stderr=str(stderr),
                  process_reaped=process.returncode is not None if process else None,
                  cleanup_errors=cleanup_errors,
                  report=str(directory / 'result.json'))
    if result['status'] != 'PASS':
        render_crash_report(result, directory, started, output, errors)
    writejson(result['report'], result)
    if log is not None:
        log = Path(log)
        log.parent.mkdir(parents=True, exist_ok=True)
        with log.open('a') as handle:
            handle.write(json.dumps({k: result.get(k) for k in ('status', 'classification', 'report', 'stdout', 'stderr')}) + '\n')
    if result['status'] != 'PASS' and not allow_failure:
        raise BlenderFailure(result)
    return result
