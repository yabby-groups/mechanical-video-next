"""Run SenseVoiceSmall INT8 with the separately installed sherpa-onnx runtime."""
import json
from pathlib import Path
import subprocess
import sys


def recognize(model, output, inputs):
    import numpy
    import sherpa_onnx

    recognizer = sherpa_onnx.OfflineRecognizer.from_sense_voice(
        model=str(model / 'model.int8.onnx'), tokens=str(model / 'tokens.txt'),
        language='zh', num_threads=2,
    )
    results = []
    for source in inputs:
        raw = subprocess.check_output([
            'ffmpeg', '-nostdin', '-v', 'error', '-i', source,
            '-ar', '16000', '-ac', '1', '-f', 'f32le', '-',
        ])
        stream = recognizer.create_stream()
        stream.accept_waveform(16000, numpy.frombuffer(raw, dtype='<f4'))
        recognizer.decode_stream(stream)
        result = stream.result
        results.append(dict(text=result.text, tokens=list(result.tokens), seconds=list(result.timestamps)))
    output.write_text(json.dumps(results, ensure_ascii=False))


if __name__ == '__main__':
    model, output, *inputs = sys.argv[1:]
    recognize(Path(model), Path(output), inputs)
