"""Run in a separately installed upstream environment, communicating via JSON lines."""
from contextlib import redirect_stdout
import json
import platform
import resource
import sys
import time
import traceback


def initialize(model, device):
    import torch
    from cosyvoice.cli.cosyvoice import CosyVoice3

    if device != ('cuda' if torch.cuda.is_available() else 'cpu'):
        raise RuntimeError('CosyVoice 3 upstream selects CUDA or CPU automatically')
    if device == 'cpu':
        torch.set_num_threads(min(4, torch.get_num_threads()))
    return CosyVoice3(model_dir=model, load_trt=False, load_vllm=False, fp16=False)


def infer(tts, request):
    import random
    import numpy
    import torch
    import torchaudio

    seed = request['seed']
    random.seed(seed)
    numpy.random.seed(seed)
    torch.manual_seed(seed)
    args = request['args']
    with torch.inference_mode():
        chunks = [row['tts_speech'] for row in tts.inference_instruct2(
            args['text'], args['instruction'], request['reference'], stream=False, speed=args['speed']
        )]
        if not chunks:
            raise RuntimeError('CosyVoice 3 returned no speech')
        torchaudio.save(request['output'], torch.cat(chunks, dim=1), tts.sample_rate)
        reference = tts.frontend._extract_spk_embedding(request['reference'])
        generated = tts.frontend._extract_spk_embedding(request['output'])
        return {'speaker_reference_cosine': torch.nn.functional.cosine_similarity(reference, generated).item()}


def main():
    model, device = sys.argv[2:]
    tts = None
    for line in sys.stdin:
        try:
            load_time = 0.
            with redirect_stdout(sys.stderr):
                if tts is None:
                    started = time.perf_counter()
                    tts = initialize(model, device)
                    load_time = time.perf_counter() - started
                started = time.perf_counter()
                acoustic = infer(tts, json.loads(line))
                seconds = time.perf_counter() - started
            peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
            response = dict(inference_seconds=seconds, initialization_seconds=load_time,
                            process_peak_rss_bytes=peak if platform.system() == 'Darwin' else peak * 1024,
                            device=device, **acoustic)
        except Exception as error:
            traceback.print_exc(file=sys.stderr)
            response = {'error': f'{type(error).__name__}: {error}'}
        print(json.dumps(response, ensure_ascii=False), flush=True)


def recognize(model, output, inputs):
    from pathlib import Path
    from funasr import AutoModel

    recognizer = AutoModel(model=model, device='cpu', disable_update=True)
    rows = [recognizer.generate(input=path, language='zh', use_itn=True)[0]['text'] for path in inputs]
    Path(output).write_text(json.dumps(rows, ensure_ascii=False))


if __name__ == '__main__':
    if sys.argv[1] == 'sensevoice':
        model, output, *inputs = sys.argv[2:]
        recognize(model, output, inputs)
    elif sys.argv[1] == 'cosyvoice3':
        main()
    else:
        raise SystemExit('Unsupported voice worker command. Use cosyvoice3 or sensevoice.')
