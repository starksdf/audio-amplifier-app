"""
Audio batch amplify engine
Supports: WAV (Android), MP3/WAV/FLAC/OGG/M4A (Desktop with pydub)
Core: peak normalize + soft clip — no distortion
"""

import numpy as np
import os
import json
import wave
import struct
from pathlib import Path
from datetime import datetime

# Try to import pydub (desktop, needs ffmpeg)
try:
    from pydub import AudioSegment
    HAS_PYDUB = True
except ImportError:
    HAS_PYDUB = False

SUPPORTED_EXTS = {'.wav'}
if HAS_PYDUB:
    SUPPORTED_EXTS = {'.mp3', '.wav', '.flac', '.ogg', '.m4a', '.aac', '.wma', '.opus'}

SOFT_CLIP_THRESHOLD = 0.95
SOFT_CLIP_KNEE = 0.1


class AudioProcessor:
    """Audio processor: multiple amplify strategies, distortion-free"""

    def __init__(self):
        self.results = []
        self.cancelled = False

    # ── Core algorithms ──────────────────────────────

    @staticmethod
    def soft_clip(audio, threshold=SOFT_CLIP_THRESHOLD, knee=SOFT_CLIP_KNEE):
        """Soft clipper using tanh curve"""
        above = np.abs(audio) > threshold
        if not np.any(above):
            return audio
        result = audio.copy()
        sign = np.sign(audio)
        mag = np.abs(audio)
        mask = above & (mag < threshold + knee)
        if np.any(mask):
            x = (mag[mask] - threshold) / knee
            result[mask] = sign[mask] * (threshold + knee * np.tanh(x))
        mask2 = mag >= threshold + knee
        if np.any(mask2):
            result[mask2] = sign[mask2] * (threshold + knee)
        return result

    @staticmethod
    def measure_peak(audio):
        peak = np.max(np.abs(audio))
        if peak == 0:
            return -np.inf
        return 20 * np.log10(peak)

    @staticmethod
    def measure_rms(audio):
        rms = np.sqrt(np.mean(audio ** 2))
        if rms == 0:
            return -np.inf
        return 20 * np.log10(rms)

    # ── Amplify strategies ──────────────────────────

    def amplify_direct(self, audio, multiplier, safe_mode=True):
        """Direct multiply amplify"""
        info = {
            'method': 'direct_multiply',
            'multiplier': multiplier,
            'peak_before_db': self.measure_peak(audio),
            'rms_before_db': self.measure_rms(audio),
        }
        amplified = audio * multiplier
        if safe_mode:
            amplified = self.soft_clip(amplified)
            peak = np.max(np.abs(amplified))
            if peak > 0.99:
                amplified = amplified * (0.98 / peak)
        info['peak_after_db'] = self.measure_peak(amplified)
        info['rms_after_db'] = self.measure_rms(amplified)
        info['clipping_risk'] = bool(np.any(np.abs(amplified) >= 0.98))
        return amplified, info

    def amplify_smart(self, audio, target_multiplier=2.0, max_peak_db=-1.0):
        """Smart amplify: compress if needed, then amplify"""
        info = {
            'method': 'smart_amplify',
            'target_multiplier': target_multiplier,
            'max_peak_db': max_peak_db,
            'peak_before_db': self.measure_peak(audio),
            'rms_before_db': self.measure_rms(audio),
        }
        current_peak = np.max(np.abs(audio))
        if current_peak == 0:
            return audio, info
        target_peak_linear = 10 ** (max_peak_db / 20.0)
        needed_peak = current_peak * target_multiplier
        if needed_peak <= target_peak_linear:
            amplified = audio * target_multiplier
            info['strategy'] = 'direct_multiply'
        else:
            safe_multiplier = target_peak_linear / current_peak
            ratio = target_multiplier / safe_multiplier
            threshold = 0.5
            compressed = audio.copy()
            mask = np.abs(audio) > threshold
            if np.any(mask):
                excess = np.abs(audio[mask]) - threshold
                compressed_excess = excess / ratio
                compressed[mask] = np.sign(audio[mask]) * (threshold + compressed_excess)
            amplified = compressed * safe_multiplier
            info['strategy'] = 'compress_then_multiply'
            info['compression_ratio'] = ratio
        amplified = self.soft_clip(amplified)
        peak = np.max(np.abs(amplified))
        if peak > 0.98:
            amplified = amplified * (0.98 / peak)
        info['peak_after_db'] = self.measure_peak(amplified)
        info['rms_after_db'] = self.measure_rms(amplified)
        return amplified, info

    def amplify_to_peak(self, audio, target_peak_db=-1.0, multiplier=None):
        """Peak normalize"""
        info = {
            'method': 'peak_normalize',
            'target_peak_db': target_peak_db,
            'peak_before_db': self.measure_peak(audio),
            'rms_before_db': self.measure_rms(audio),
        }
        current_peak = np.max(np.abs(audio))
        if current_peak == 0:
            info['skipped'] = True
            return audio, info
        target_peak = 10 ** (target_peak_db / 20.0)
        if multiplier is not None and multiplier > 0:
            audio = audio * multiplier
        new_peak = np.max(np.abs(audio))
        if new_peak == 0:
            return audio, info
        scale = target_peak / new_peak
        amplified = audio * scale
        amplified = self.soft_clip(amplified)
        info['peak_after_db'] = self.measure_peak(amplified)
        info['rms_after_db'] = self.measure_rms(amplified)
        return amplified, info

    # ── File I/O (works on Android without ffmpeg) ──

    @staticmethod
    def load_audio(filepath):
        """Load audio file -> (data_float64, sample_rate, ext)"""
        ext = Path(filepath).suffix.lower()

        # Try WAV with built-in wave module (works everywhere)
        if ext == '.wav':
            with wave.open(filepath, 'rb') as wf:
                sr = wf.getframerate()
                nchannels = wf.getnchannels()
                sampwidth = wf.getsampwidth()
                nframes = wf.getnframes()
                raw = wf.readframes(nframes)

            if sampwidth == 2:
                dtype = np.int16
                max_val = 32767.0
            elif sampwidth == 3:
                # 24-bit: read as bytes, convert
                raw_arr = np.frombuffer(raw, dtype=np.uint8)
                n_samples = len(raw_arr) // 3
                samples = np.zeros(n_samples, dtype=np.int32)
                for i in range(3):
                    samples |= raw_arr[i::3].astype(np.int32) << (i * 8)
                # Sign extend
                samples = np.where(samples >= 2**23, samples - 2**24, samples)
                audio = samples.astype(np.float64) / (2**23 - 1)
                if nchannels > 1:
                    audio = audio.reshape(-1, nchannels)
                return audio, sr, ext
            elif sampwidth == 4:
                dtype = np.int32
                max_val = 2147483647.0
            else:
                raise RuntimeError(f"Unsupported WAV bit depth: {sampwidth*8}-bit")

            samples = np.frombuffer(raw, dtype=dtype).astype(np.float64) / max_val
            if nchannels > 1:
                samples = samples.reshape(-1, nchannels)
            return samples, sr, ext

        # Try pydub for other formats (desktop only)
        if HAS_PYDUB:
            seg = AudioSegment.from_file(filepath)
            samples = np.array(seg.get_array_of_samples(), dtype=np.float64)
            if seg.channels > 1:
                samples = samples.reshape(-1, seg.channels)
            max_val = float(2 ** (seg.sample_width * 8 - 1))
            samples = samples / max_val
            return samples, seg.frame_rate, ext

        raise RuntimeError(
            f"Cannot load {ext} format. "
            f"Convert to WAV first, or install pydub+ffmpeg on desktop."
        )

    @staticmethod
    def save_audio(filepath, audio, sr, bitrate='192k'):
        """Save audio file"""
        ext = Path(filepath).suffix.lower()
        audio = np.clip(audio, -1.0, 1.0)

        # WAV with built-in wave module
        if ext == '.wav':
            if audio.ndim == 2:
                nchannels = audio.shape[1]
            else:
                nchannels = 1
                audio = audio.flatten()
            audio_int = (audio * 32767).astype(np.int16)
            with wave.open(filepath, 'wb') as wf:
                wf.setnchannels(nchannels)
                wf.setsampwidth(2)
                wf.setframerate(sr)
                wf.writeframes(audio_int.tobytes())
            return filepath

        # Other formats with pydub
        if HAS_PYDUB:
            audio_int = (audio * 32767).astype(np.int16)
            if audio.ndim == 2:
                channels = audio.shape[1]
            else:
                channels = 1
                audio_int = audio_int.flatten()
            seg = AudioSegment(
                audio_int.tobytes(),
                frame_rate=sr,
                sample_width=2,
                channels=channels
            )
            seg.export(filepath, format=ext.lstrip('.'), bitrate=bitrate)
            return filepath

        raise RuntimeError(f"Cannot save {ext}, use .wav format")

    # ── Batch processing ──────────────────────────────

    def process_batch(self, input_dir, output_dir, multiplier=2.0,
                      mode='smart', output_format=None, bitrate='192k',
                      callback=None):
        """Batch process all audio files"""
        self.cancelled = False
        self.results = []
        input_path = Path(input_dir)
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        files = sorted([
            f for f in input_path.iterdir()
            if f.is_file() and f.suffix.lower() in SUPPORTED_EXTS
        ])

        total = len(files)
        if total == 0:
            return self.results

        for i, fpath in enumerate(files):
            if self.cancelled:
                break
            try:
                if callback:
                    callback(i / total, fpath.name, f"Processing ({i+1}/{total})")

                audio, sr, fmt = self.load_audio(str(fpath))

                if audio.ndim == 2:
                    processed_channels = []
                    for ch in range(audio.shape[1]):
                        ch_out, info = self._apply_mode(audio[:, ch], mode, multiplier)
                        processed_channels.append(ch_out)
                    processed = np.column_stack(processed_channels)
                else:
                    processed, info = self._apply_mode(audio, mode, multiplier)

                out_ext = f'.{output_format}' if output_format else fpath.suffix
                out_name = f"{fpath.stem}_amplified{out_ext}"
                out_file = output_path / out_name

                self.save_audio(str(out_file), processed, sr, bitrate)

                self.results.append({
                    'input': str(fpath),
                    'output': str(out_file),
                    'status': 'success',
                    **info
                })
                if callback:
                    callback((i + 1) / total, fpath.name, f"Done: {fpath.name}")

            except Exception as e:
                self.results.append({
                    'input': str(fpath),
                    'status': 'error',
                    'error': str(e)
                })
                if callback:
                    callback((i + 1) / total, fpath.name, f"Error: {e}")

        return self.results

    def _apply_mode(self, audio, mode, multiplier):
        if mode == 'smart':
            return self.amplify_smart(audio, multiplier)
        elif mode == 'direct':
            return self.amplify_direct(audio, multiplier)
        elif mode == 'peak':
            return self.amplify_to_peak(audio, -1.0, multiplier)
        else:
            return self.amplify_direct(audio, multiplier)

    def cancel(self):
        self.cancelled = True

    def export_report(self, filepath):
        report = {
            'timestamp': datetime.now().isoformat(),
            'total': len(self.results),
            'success': sum(1 for r in self.results if r['status'] == 'success'),
            'failed': sum(1 for r in self.results if r['status'] == 'error'),
            'details': self.results
        }
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
