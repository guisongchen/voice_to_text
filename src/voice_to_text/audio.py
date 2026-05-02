import numpy as np
import pyaudio
import soundfile as sf
import torch
import torchaudio

from .config import SAMPLE_RATE, START_BEEP_FREQ, FINISH_BEEP_FREQ, START_BEEP_DURATION, FINISH_BEEP_DURATION


class AudioPreprocessor:
    """Audio preprocessing for better transcription accuracy."""

    @staticmethod
    def preprocess(audio_path):
        try:
            data, sample_rate = sf.read(audio_path, dtype='float32')
            if data.ndim == 1:
                waveform = torch.from_numpy(data).unsqueeze(0)
            else:
                waveform = torch.from_numpy(data).t().contiguous()

            if waveform.shape[0] > 1:
                waveform = torch.mean(waveform, dim=0, keepdim=True)

            if sample_rate != 16000:
                resampler = torchaudio.transforms.Resample(
                    orig_freq=sample_rate, new_freq=16000
                )
                waveform = resampler(waveform)

            peak = torch.max(torch.abs(waveform))
            if peak > 0:
                waveform = waveform / peak * 0.891

            waveform = AudioPreprocessor._reduce_noise(waveform)

            processed_path = audio_path.replace('.wav', '_processed.wav')
            sf.write(processed_path, waveform.squeeze().numpy(), 16000)
            return processed_path

        except Exception as e:
            print(f"  Warning: Audio preprocessing failed ({e}), using original")
            return audio_path

    @staticmethod
    def _reduce_noise(waveform, n_fft=2048, hop_length=512, noise_reduction=0.7):
        try:
            audio_np = waveform.squeeze().numpy()
            stft = torch.stft(
                waveform.squeeze(),
                n_fft=n_fft, hop_length=hop_length, return_complex=True
            )
            window_size = int(0.05 * 16000)
            hop_size = window_size // 2
            num_windows = max(1, (len(audio_np) - window_size) // hop_size + 1)
            energies = np.array([
                np.sum(audio_np[i * hop_size:i * hop_size + window_size] ** 2)
                for i in range(num_windows)
            ])
            quietest_count = max(1, num_windows // 10)
            quietest_indices = np.argsort(energies)[:quietest_count]
            cols_per_window = window_size // hop_length
            hop_cols = hop_size // hop_length
            noise_cols = []
            for idx in quietest_indices:
                start = idx * hop_cols
                end = start + cols_per_window
                noise_cols.extend(range(start, min(end, stft.shape[1])))
            if noise_cols:
                noise_floor = torch.mean(torch.abs(stft[:, noise_cols]), dim=1, keepdim=True)
            else:
                noise_floor = torch.median(torch.abs(stft), dim=1, keepdim=True)[0]

            magnitude = torch.abs(stft)
            phase = torch.angle(stft)
            mask = torch.clamp((magnitude - noise_reduction * noise_floor) / (magnitude + 1e-10), 0, 1)
            mask = mask ** 0.5
            cleaned_magnitude = magnitude * mask
            cleaned_stft = cleaned_magnitude * torch.exp(1j * phase)
            cleaned = torch.istft(
                cleaned_stft, n_fft=n_fft, hop_length=hop_length, length=len(audio_np)
            )
            return cleaned.unsqueeze(0)
        except Exception:
            return waveform



class BeepPlayer:
    """Plays start/finish beep sounds."""

    def __init__(self):
        self.sample_rate = SAMPLE_RATE
        self.audio = None
        self.output_stream = None
        self._start_beep = self._generate(START_BEEP_FREQ, START_BEEP_DURATION)
        self._finish_beep = self._generate(FINISH_BEEP_FREQ, FINISH_BEEP_DURATION)
        gap_samples = int(SAMPLE_RATE * 0.08)
        self._gap = np.random.randint(-1, 2, gap_samples, dtype=np.int16)

    def _generate(self, freq, duration):
        samples = int(self.sample_rate * duration)
        t = np.linspace(0, duration, samples, False)
        wave = np.sin(2 * np.pi * freq * t)
        fade = int(SAMPLE_RATE * 0.01)
        wave[:fade] *= np.linspace(0, 1, fade)
        wave[-fade:] *= np.linspace(1, 0, fade)
        return (wave * 32767).astype(np.int16)

    def _ensure_audio(self):
        if self.audio is None:
            self.audio = pyaudio.PyAudio()
        return self.audio

    def open_stream(self):
        try:
            self._ensure_audio()
            self.output_stream = self.audio.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=self.sample_rate,
                output=True
            )
            warmup = np.random.randint(-1, 2, int(self.sample_rate * 0.1), dtype=np.int16)
            self.output_stream.write(warmup.tobytes())
        except Exception as e:
            print(f"Warning: Could not open audio output: {e}")

    def close_stream(self):
        if self.output_stream:
            try:
                self.output_stream.stop_stream()
                self.output_stream.close()
            except:
                pass
            self.output_stream = None

    def play_start(self):
        try:
            self._play(self._gap)
            self._play(self._start_beep)
            self._play(self._gap)
            self._play(self._start_beep)
        except:
            pass

    def play_finish(self):
        try:
            self._play(self._finish_beep)
        except:
            pass

    def _play(self, data):
        self._ensure_audio()
        if self.output_stream and self.output_stream.is_active():
            stream = self.output_stream
            close_after = False
        else:
            stream = self.audio.open(format=pyaudio.paInt16, channels=1,
                                     rate=self.sample_rate, output=True)
            close_after = True

        stream.write(data.tobytes())

        if close_after:
            stream.stop_stream()
            stream.close()

    def cleanup(self):
        self.close_stream()
        if self.audio:
            self.audio.terminate()
            self.audio = None
