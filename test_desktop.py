"""
Desktop quick test — verify audio processing without Android
Usage: python test_desktop.py [folder_or_file_path]
"""

import sys
import os
import numpy as np
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))
from audio_processor import AudioProcessor, SUPPORTED_EXTS


def test_single_file(filepath, multiplier=2.0):
    proc = AudioProcessor()
    print(f"\n{'='*50}")
    print(f"File: {Path(filepath).name}")
    print(f"{'='*50}")

    audio, sr, fmt = proc.load_audio(filepath)
    print(f"  Sample rate: {sr} Hz | Format: {fmt}")
    print(f"  Channels: {audio.shape[1] if audio.ndim == 2 else 1}")
    print(f"  Duration: {len(audio)/sr:.1f}s")
    print()

    test_audio = audio[:, 0] if audio.ndim == 2 else audio

    for name, fn in [
        ('Smart', lambda a: proc.amplify_smart(a, multiplier)),
        ('Direct', lambda a: proc.amplify_direct(a, multiplier)),
        ('Peak', lambda a: proc.amplify_to_peak(a, -1.0, multiplier)),
    ]:
        print(f"  {name}:")
        result, info = fn(test_audio)
        print(f"    Peak: {info.get('peak_before_db', 0):.1f} -> {info.get('peak_after_db', 0):.1f} dBFS")
        print(f"    RMS:  {info.get('rms_before_db', 0):.1f} -> {info.get('rms_after_db', 0):.1f} dBFS")
        if info.get('strategy'):
            print(f"    Strategy: {info['strategy']}")
        if info.get('clipping_risk'):
            print(f"    [WARN] near clipping")
        print()


def test_batch(input_dir, multiplier=2.0):
    proc = AudioProcessor()
    print(f"\nBatch: {input_dir}")
    print(f"Multiplier: {multiplier}x | Mode: smart\n")

    output_dir = os.path.join(input_dir, 'amplified_output')

    def progress_cb(pct, fname, msg):
        bar = '#' * int(pct * 30) + '-' * (30 - int(pct * 30))
        print(f"\r  [{bar}] {pct*100:5.1f}% {msg}", end='', flush=True)

    results = proc.process_batch(
        input_dir=input_dir,
        output_dir=output_dir,
        multiplier=multiplier,
        mode='smart',
        callback=progress_cb
    )

    print(f"\n\n{'='*50}")
    print(f"Done!")
    print(f"  Success: {sum(1 for r in results if r['status'] == 'success')}")
    print(f"  Failed: {sum(1 for r in results if r['status'] == 'error')}")
    print(f"  Output: {output_dir}")

    report_path = os.path.join(output_dir, 'report.json')
    proc.export_report(report_path)
    print(f"  Report: {report_path}")

    for r in results:
        name = Path(r['input']).name
        if r['status'] == 'success':
            print(f"\n  [OK] {name}")
            print(f"    Peak: {r.get('peak_before_db',0):.1f} -> {r.get('peak_after_db',0):.1f} dBFS")
        else:
            print(f"\n  [FAIL] {name}: {r.get('error')}")


def generate_test_audio(output_path, duration=5.0, sr=44100):
    t = np.linspace(0, duration, int(sr * duration), endpoint=False)
    signal = 0.3 * np.sin(2 * np.pi * 440 * t)
    signal += 0.05 * np.random.randn(len(signal))
    signal = np.clip(signal, -1, 1)
    AudioProcessor.save_audio(output_path, signal, sr)
    print(f"Generated: {output_path}")


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python test_desktop.py <folder>       # batch")
        print("  python test_desktop.py <file>          # single")
        print("  python test_desktop.py --generate      # test audio")
        sys.exit(0)

    target = sys.argv[1]
    mult = float(sys.argv[2]) if len(sys.argv) > 2 else 2.0

    if target == '--generate':
        os.makedirs('test_audio', exist_ok=True)
        generate_test_audio('test_audio/test_tone.wav')
        print("\nThen run: python test_desktop.py test_audio")
    elif os.path.isfile(target):
        test_single_file(target, mult)
    elif os.path.isdir(target):
        test_batch(target, mult)
    else:
        print(f"Not found: {target}")
