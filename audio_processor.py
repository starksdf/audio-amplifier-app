"""
Audio batch amplify engine
Supports: MP3, WAV, FLAC, OGG, M4A, AAC, WMA, OPUS
Core: peak normalize + soft clip + RMS loudness control — no distortion
"""

import numpy as np
import os
import json
from pathlib import Path
from datetime import datetime

try:
    from pydub import AudioSegment
    HAS_PYDUB = True
except ImportError:
    HAS_PYDUB = False

try:
    import soundfile as sf
    HAS_SOUNDFILE = True
except ImportError:
    HAS_SOUNDFILE = False

SUPPORTED_EXTS = {'.mp3', '.wav', '.flac', '.ogg', '.m4a', '.aac', '.wma', '.opus'}
MAX_TRUE_PEAK_DB = -1.0
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
        """Soft clipper using tanh curve — smooth clipping, no harmonic distortion"""
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
        """Measure peak amplitude (dBFS)"""
        peak = np.max(np.abs(audio))
        if peak == 0:
            return -np.inf
        return 20 * np.log10(peak)

    @staticmethod
    def measure_rms(audio):
        """Measure RMS loudness (dBFS)"""
        rms = np.sqrt(np.mean(audio ** 2))
        if rms == 0:
            return -np.inf
        return 20 * np.log10(rms)

    # ── Amplify strategies ──────────────────────────

    def amplify_fixed(self, audio, gain_db, soft_limit=True):
        """Fixed gain amplify (dB)"""
        info = {
            'method': 'fixed_gain',
            'gain_db': gain_db,
            'peak_before_db': self.measure_peak(audio),
            'rms_before_db': self.measure_rms(audio),
        }

        gain_linear = 10 ** (gain_db / 20.0)
        amplified = audio * gain_linear

        if soft_limit:
            amplified = self.soft_clip(amplified)

        info['peak_after_db'] = self.measure_peak(amplified)
        info['rms_after_db'] = self.measure_rms(amplified)
        info['clipping'] = bool(np.any(np.abs(amplified) >= 0.99))

        return amplified, info

    def amplify_to_peak(self, audio, target_peak_db=-1.0, multiplier=None):
        """Peak normalize to target, with optional extra multiplier"""
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

    def amplify_direct(self, audio, multiplier, safe_mode=True):
        """Direct multiply amplify (most intuitive)"""
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
        """
        Smart amplify — RECOMMENDED
        1. Try direct multiply
        2. If clipping would occur, compress dynamics first then amplify
        3. Result: loudness up, quality preserved
        """
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
            # No clipping risk, direct multiply
            amplified = audio * target_multiplier
            info['strategy'] = 'direct_multiply'
        else:
            # Need compression + amplification
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

        # Final protection
        amplified = self.soft_clip(amplified)
        peak = np.max(np.abs(amplified))
        if peak > 0.98:
            amplified = amplified * (0.98 / peak)

        info['peak_after_db'] = self.measure_peak(amplified)
        info['rms_after_db'] = self.measure_rms(amplified)

        return amplified, info

    # ── File I/O ──────────────────────────────────────

    @staticmethod
    def load_audio(filepath):
        """Load audio file -> (data_float64, sample_rate, ext)"""
        ext = Path(filepath).suffix.lower()

        if HAS_PYDUB:
            seg = AudioSegment.from_file(filepath)
            samples = np.array(seg.get_array_of_samples(), dtype=np.float64)
            if seg.channels > 1:
                samples = samples.reshape(-1, seg.channels)
            max_val = float(2 ** (seg.sample_width * 8 - 1))
            samples = samples / max_val
            return samples, seg.frame_rate, ext

        if HAS_SOUNDFILE and ext in {'.wav', '.flac', '.ogg'}:
            data, sr = sf.read(filepath, dtype='float64')
            return data, sr, ext

        raise RuntimeError(f"Cannot load {ext}, install ffmpeg or soundfile")

    @staticmethod
    def save_audio(filepath, audio, sr, bitrate='192k'):
        """Save audio, auto-detect format from extension"""
        ext = Path(filepath).suffix.lower()
        audio = np.clip(audio, -1.0, 1.0)

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

        if HAS_SOUNDFILE and ext in {'.wav', '.flac', '.ogg'}:
            sf.write(filepath, audio, sr)
            return filepath

        raise RuntimeError(f"Cannot save {ext}")

    # ── Batch processing ──────────────────────────────

    def process_batch(self, input_dir, output_dir, multiplier=2.0,
                      mode='smart', output_format=None, bitrate='192k',
                      callback=None):
        """
        Batch process all audio files in a directory
        mode: 'smart' | 'direct' | 'peak' | 'fixed'
        callback(progress_float, current_file, status_msg)
        """
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

                # Process (handle stereo per-channel)
                if audio.ndim == 2:
                    processed_channels = []
                    for ch in range(audio.shape[1]):
                        ch_data = audio[:, ch]
                        ch_out, info = self._apply_mode(ch_data, mode, multiplier)
                        processed_channels.append(ch_out)
                    processed = np.column_stack(processed_channels)
                else:
                    processed, info = self._apply_mode(audio, mode, multiplier)

                # Output filename
                out_ext = f'.{output_format}' if output_format else fpath.suffix
                out_name = f"{fpath.stem}_amplified{out_ext}"
                out_file = output_path / out_name

                self.save_audio(str(out_file), processed, sr, bitrate)

                result = {
                    'input': str(fpath),
                    'output': str(out_file),
                    'status': 'success',
                    **info
                }
                self.results.append(result)

                if callback:
                    callback((i + 1) / total, fpath.name, f"Done: {fpath.name}")

            except Exception as e:
                result = {
                    'input': str(fpath),
                    'status': 'error',
                    'error': str(e)
                }
                self.results.append(result)
                if callback:
                    callback((i + 1) / total, fpath.name, f"Error: {e}")

        return self.results

    def _apply_mode(self, audio, mode, multiplier):
        """Apply the selected amplify mode"""
        if mode == 'smart':
            return self.amplify_smart(audio, multiplier)
        elif mode == 'direct':
            return self.amplify_direct(audio, multiplier)
        elif mode == 'peak':
            return self.amplify_to_peak(audio, -1.0, multiplier)
        else:  # fixed
            return self.amplify_fixed(audio, multiplier * 6)

    def cancel(self):
        self.cancelled = True

    def export_report(self, filepath):
        """Export processing report as JSON"""
        report = {
            'timestamp': datetime.now().isoformat(),
            'total': len(self.results),
            'success': sum(1 for r in self.results if r['status'] == 'success'),
            'failed': sum(1 for r in self.results if r['status'] == 'error'),
            'details': self.results
        }
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
