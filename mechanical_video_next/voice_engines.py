"""Sentence synthesis, explicit capability negotiation and a sealed speech cache."""
from contextlib import ExitStack
import json
import os
from pathlib import Path
from queue import Empty, Queue
import subprocess
from tempfile import TemporaryDirectory
from threading import Thread
from time import monotonic
import uuid
import wave

from scripts import narration
from scripts.common import ROOT, digest, filehash, writejson
from . import joint_timeline as joint
from .voice_direction import DELIVERY, EMOTIONS, finite, require_engine
from .workflow import lock

DEFAULT_MODELS = ROOT / '.voice-data/models'
DEFAULT_CACHE = ROOT / '.voice-data/cache'
WORKER = Path(__file__).with_name('voice_worker.py')
COSY_REQUIRED = ('cosyvoice3.yaml', 'llm.pt', 'flow.pt', 'hift.pt', 'campplus.onnx',
                 'speech_tokenizer_v3.onnx', 'CosyVoice-BlankEN/config.json',
                 'CosyVoice-BlankEN/model.safetensors', 'CosyVoice-BlankEN/tokenizer_config.json',
                 'CosyVoice-BlankEN/merges.txt', 'CosyVoice-BlankEN/vocab.json')
COSY_SOURCE = 'cosyvoice/cli/cosyvoice.py'


class EngineError(RuntimeError):
    pass


def load_profile(path):
    profile = json.loads(Path(path).read_text())
    engines = profile['engines']
    for name in engines:
        require_engine(name)
    fallback = profile.get('fallback_engine')
    if fallback is not None:
        require_engine(fallback)
        if fallback != 'neil' or fallback not in engines:
            raise ValueError('The fallback engine must be a configured Neil route')
    if (type(profile.get('schema_version')) is not int or profile['schema_version'] != 1
            or not all(isinstance(profile[k], str) and profile[k].strip() for k in ('id', 'description'))
            or not engines
            or profile['default_emotion'] not in EMOTIONS
            or not finite(profile['base_speaking_rate'], .8, 1.2)):
        raise ValueError('Invalid voice profile')
    minimum, maximum = profile['emotion_intensity_range']
    if not finite(minimum, 0, 1) or not finite(maximum, minimum, 1):
        raise ValueError('Invalid emotion intensity range')
    for key, maximum in (('pause_before_ms', 1500), ('pause_after_ms', 1500), ('max_emphasis_words', 5)):
        if type(profile[key]) is not int or not 0 <= profile[key] <= maximum:
            raise ValueError('Invalid profile setting: ' + key)
    return profile


def controls(segment, engine):
    require_engine(engine)
    text = segment['text']
    words = segment['emphasis_words']
    pronunciations = segment.get('pronunciations', {})
    rate = segment['speaking_rate']
    intensity = segment['emotion_intensity']
    emotion = segment['emotion']
    unsupported = []
    if engine == 'neil':
        if emotion != 'neutral' or intensity:
            unsupported.append('emotion_uses_original_neil')
        if rate != 1:
            unsupported.append('speaking_rate_uses_neil_native_1x')
        if words:
            unsupported.append('emphasis_unsupported')
        if pronunciations:
            unsupported.append('pronunciation_override_unsupported')
        return {'text': text}, unsupported
    # CosyVoice takes a performance instruction. Emotion intensity only affects its wording.
    instruction = f'用标准普通话讲解。{DELIVERY[emotion]}。'
    if intensity < .24:
        instruction += '语气轻一点，沿着句意说。'
    elif intensity >= .55:
        instruction += '让语气变化清楚一些，保持正常说话的音量。'
    if segment['delivery_style'] != DELIVERY[emotion]:
        instruction += segment['delivery_style'].rstrip('。！？') + '。'
    if words:
        instruction += '把' + '、'.join(f'“{word}”' for word in words) + '说清楚，稍作强调。'
    if pronunciations:
        unsupported.append('pronunciation_override_not_mapped_for_cosyvoice3')
    return {'text': text, 'instruction': 'You are a helpful assistant. ' + instruction + '<|endofprompt|>',
            'speed': rate}, unsupported


class LocalWorker:
    """A single model process per route. The parent never imports ML frameworks."""
    def __init__(self, config, model, log):
        # Keep the venv entry point. Resolving its symlink loses pyvenv.cfg.
        runtime = Path(config['runtime_python']).expanduser().absolute()
        source = Path(config['source_dir']).expanduser().resolve()
        if not runtime.is_file() or not (source / COSY_SOURCE).is_file():
            raise EngineError('Install the isolated CosyVoice 3 runtime and official checkout')
        self.timeout = config.get('timeout_seconds', 360)
        self.log = Path(log)
        self.log.parent.mkdir(parents=True, exist_ok=True)
        self.responses = Queue()
        self.device = config.get('device', 'cpu')
        if self.device not in ('cpu', 'cuda'):
            raise EngineError('The configured upstream runtime has no supported device path: ' + self.device)
        command = [str(runtime), '-u', str(WORKER), 'cosyvoice3', str(model), self.device]
        env = dict(os.environ, PYTHONPATH=os.pathsep.join(str(p) for p in
                    (source, source / 'third_party/Matcha-TTS')),
                   HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1')
        env.setdefault('MPLCONFIGDIR', str(self.log.parent / 'matplotlib'))
        with self.log.open('ab') as diagnostic:
            self.process = subprocess.Popen(command, cwd=source, env=env, stdin=subprocess.PIPE,
                                            stdout=subprocess.PIPE, stderr=diagnostic, text=True,
                                            encoding='utf-8')
        self.reader = Thread(target=self._read_responses, daemon=True)
        self.reader.start()

    def _read_responses(self):
        for line in self.process.stdout:
            self.responses.put(line)
        self.responses.put(None)

    def request(self, payload):
        try:
            self.process.stdin.write(json.dumps(payload, ensure_ascii=False) + '\n')
            self.process.stdin.flush()
            raw = self.responses.get(timeout=self.timeout)
            if raw is None:
                raise EngineError(f'Worker exited ({self.process.wait()}). See {self.log}')
            response = json.loads(raw)
            if 'error' in response:
                raise EngineError(f'{response["error"]}. See {self.log}')
            return response
        except (Empty, OSError, ValueError) as error:
            raise EngineError(f'{type(error).__name__} in model worker. See {self.log}') from error

    def close(self):
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait()
        self.reader.join()
        self.process.stdin.close()
        self.process.stdout.close()


def model_files(model):
    needed = [model / name for name in COSY_REQUIRED]
    missing = [str(path.relative_to(model)) for path in needed if not path.is_file() or not path.stat().st_size]
    if missing:
        raise EngineError(f'Model unavailable at {model}. Missing ' + ', '.join(missing))
    return needed


def reference_audio(spec):
    ref = spec.get('reference') or {}
    if (ref.get('usage') not in ('authorized', 'synthetic')
            or not isinstance(ref.get('evidence'), str) or not ref['evidence'].strip()):
        raise EngineError('An authorized or documented synthetic speaker reference is required')
    try:
        return joint.bound(ref)
    except (OSError, ValueError, KeyError) as error:
        raise EngineError(f'Speaker reference cannot be verified: {error}') from error


class Synthesizer:
    def __init__(self, *, cache=None, models=None, diagnostics=None):
        self.cache = Path(cache or os.getenv('MECHANICAL_VOICE_CACHE') or DEFAULT_CACHE).expanduser().resolve()
        self.models = Path(models or os.getenv('MECHANICAL_VOICE_MODELS') or DEFAULT_MODELS).expanduser().resolve()
        self.diagnostics = Path(diagnostics or self.cache / 'diagnostics').resolve()
        self.setup = {}
        self.worker = None
        self.worker_key = None
        self.resources = ExitStack()
        self.run_lock = ExitStack()
        self.local_locked = False
        self.runtime_log = uuid.uuid4().hex

    def __enter__(self):
        return self

    def __exit__(self, *error):
        self.close()

    def close(self):
        self.resources.close()
        self.worker = self.worker_key = None
        self.run_lock.close()
        self.local_locked = False

    def engine_identity(self, engine, config):
        identity = (engine, digest(config))
        if identity not in self.setup:
            model = (self.models / config.get('model_dir', engine)).resolve()
            files = model_files(model)
            reference = reference_audio(config)
            revision = config.get('runtime_revision')
            source_root = Path(config.get('source_dir', '')).expanduser()
            source = source_root / COSY_SOURCE
            if not revision or not source.is_file():
                raise EngineError(f'Configure the official source checkout and runtime revision for {engine}')
            runtime = Path(config.get('runtime_python', '')).expanduser()
            package_versions = (runtime.parent.parent / 'lib')
            metadata = sorted(package_versions.glob('python*/site-packages/*.dist-info/METADATA'))
            runtime_receipt = {
                'upstream_revision': revision, 'inference_source_sha256': filehash(source),
                'engine_source_sha256': filehash(__file__), 'worker_sha256': filehash(WORKER),
                'narration_processing_sha256': filehash(narration.__file__),
                'processing_profile_sha256': filehash(ROOT / 'config/narration-neil.json'),
                'upstream_python_tree': digest({
                    str(path.relative_to(source_root)): filehash(path) for path in source_root.rglob('*.py')
                    if not any(part.startswith('.') for part in path.relative_to(source_root).parts)
                }),
                'python_sha256': filehash(runtime) if runtime.is_file() else None,
                'packages': [item.parent.name for item in metadata],
                'model_files': {str(path.relative_to(model)): filehash(path) for path in files},
                'weights_bytes': sum(path.stat().st_size for path in model.rglob('*') if path.is_file()),
                'reference_sha256': filehash(reference), 'device': config.get('device', 'cpu'),
            }
            self.setup[identity] = model, reference, runtime_receipt
        return self.setup[identity]

    def synthesize(self, segment, voice_profile, engine):
        args, unsupported = controls(segment, engine)
        config = voice_profile['engines'][engine]
        if engine == 'neil':
            started = monotonic()
            try:
                profile = narration.effective_profile(
                    {'narration_profile': config.get('profile', 'config/narration-neil.json')})
                clip, legacy = narration.sentence(segment['text'], profile)
            except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
                raise EngineError(f'Neil synthesis unavailable: {error}') from error
            return clip, dict(engine=engine, cache_hit=legacy['processed_cache_hit'], legacy=legacy,
                              applied=args, unsupported=unsupported, elapsed_seconds=monotonic() - started)
        try:
            model, reference, runtime = self.engine_identity(engine, config)
            if not self.local_locked:
                self.run_lock.enter_context(lock(self.cache / 'local-model.lock', wait=True))
                self.local_locked = True
        except (OSError, ValueError, RuntimeError) as error:
            raise EngineError(str(error)) from error
        key = digest({'applied': args, 'voice': voice_profile['id'], 'take': segment.get('take'),
                      'engine': engine, 'runtime': {k: v for k, v in runtime.items() if k != 'weights_bytes'}})
        folder = self.cache / 'sentences' / key
        wav = folder / 'speech.wav'
        with lock(self.cache / 'locks' / (key + '.lock'), wait=True):
            if narration.valid(folder, ('speech.wav', 'receipt.json')):
                cached = json.loads((folder / 'receipt.json').read_text())
                return wav, dict(cached, cache_hit=True, unsupported=unsupported)
            folder.mkdir(parents=True, exist_ok=True)
            diag = self.diagnostics / f'{engine}-{key}-{self.runtime_log}.json'
            try:
                with TemporaryDirectory(prefix='tmp-', dir=folder) as scratch:
                    receipt = self._generate(engine, config, model, reference, args, Path(scratch), wav,
                                             key, runtime)
                writejson(folder / 'receipt.json', receipt)
                narration.seal(folder, ('speech.wav', 'receipt.json'))
            except (OSError, ValueError, RuntimeError, subprocess.SubprocessError, wave.Error) as error:
                self.close()
                writejson(diag, {'segment_id': segment['segment_id'], 'error': str(error), 'key': key})
                raise EngineError(str(error)) from error
        return wav, dict(receipt, cache_hit=False, unsupported=unsupported)

    def _generate(self, engine, config, model, reference, args, scratch, wav, key, runtime):
        worker_key = (engine, model, digest(config))
        if self.worker_key != worker_key:
            self.resources.close()
            log = self.diagnostics / f'{engine}-{self.runtime_log}.log'
            self.worker = LocalWorker(config, model, log)
            self.resources.callback(self.worker.close)
            self.worker_key = worker_key
        raw, trimmed, processed = (scratch / name for name in ('raw.wav', 'trim.wav', 'speech.wav'))
        seed = int(key[:8], 16)
        result = self.worker.request(dict(args=args, reference=str(reference), output=str(raw), seed=seed))
        profile = narration.load_profile(ROOT / 'config/narration-neil.json')
        alignment = narration.silence_trim(raw, trimmed, profile)
        levels = narration.normalize(trimmed, processed, profile)
        samples = joint.pcm_frames(processed)
        if samples <= 0:
            raise EngineError('Model produced empty speech')
        processed.replace(wav)
        return dict(engine=engine, key=key, applied=args, samples=samples, seed=seed,
                    runtime=runtime, inference=result, alignment=alignment, levels=levels)


def synthesize(segment, voice_profile, engine):
    """Synthesize one sentence. Use a Synthesizer context for multiple sentences."""
    with Synthesizer() as service:
        return service.synthesize(segment, voice_profile, engine)
