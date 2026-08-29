import base64
import math
from collections import deque
from typing import Optional, Tuple, Union
import numpy as np


class AudioTransientTrigger:
    """
    Audio Transient Spike & Decibel Trigger:
    - Ingests raw PCM 16-bit / base64 audio chunks.
    - Computes RMS decibel level (dBFS) across a rolling 500ms buffer.
    - Detects acoustic spikes (e.g. screams, impacts, glass breaks, gunshots, abrupt rises).
    - Returns audio_db and trigger_fired flag to force visual gatekeeper capture.
    """

    def __init__(
        self,
        sample_rate: int = 16000,
        buffer_duration_sec: float = 0.5,
        spike_db_threshold: float = -28.0,
        dynamic_sigma_k: float = 2.5,
    ):
        self.sample_rate = sample_rate
        self.buffer_size = int(sample_rate * buffer_duration_sec)
        self.spike_db_threshold = spike_db_threshold
        self.dynamic_sigma_k = dynamic_sigma_k

        self.audio_buffer: deque = deque(maxlen=self.buffer_size)
        self.baseline_rms = 0.02
        self.ambient_var = 1e-4
        self.ema_alpha = 0.05

    def decode_audio_chunk(self, audio_data: Union[str, bytes]) -> Optional[np.ndarray]:
        """Decodes raw base64 or bytes PCM 16-bit mono into float32 array in [-1.0, 1.0]."""
        if not audio_data:
            return None
        try:
            if isinstance(audio_data, str):
                if "," in audio_data:
                    audio_data = audio_data.split(",", 1)[1]
                raw_bytes = base64.b64decode(audio_data)
            else:
                raw_bytes = audio_data

            if len(raw_bytes) < 2:
                return None

            samples_16 = np.frombuffer(raw_bytes, dtype=np.int16)
            return samples_16.astype(np.float32) / 32768.0
        except Exception:
            return None

    def process_audio(
        self,
        audio_data: Optional[Union[str, bytes]],
    ) -> Tuple[bool, float, float]:
        """
        Processes audio chunk.
        Returns:
            trigger_fired (bool): True if sudden transient spike detected.
            audio_db (float): Current RMS level in dBFS (e.g. -45.2 dB).
            rms (float): Linear RMS amplitude [0.0, 1.0].
        """
        if audio_data is None:
            return False, -60.0, 0.0

        samples = self.decode_audio_chunk(audio_data)
        if samples is None or len(samples) == 0:
            return False, -60.0, 0.0

        self.audio_buffer.extend(samples)
        buf_arr = np.array(self.audio_buffer, dtype=np.float32)
        rms = float(np.sqrt(np.mean(buf_arr ** 2))) if len(buf_arr) > 0 else 0.0

        # Compute dBFS (0 dBFS is full scale, quiet room ~ -50 to -40 dB)
        audio_db = float(20.0 * math.log10(max(rms, 1e-5)))

        # Update dynamic rolling baseline
        diff = rms - self.baseline_rms
        self.baseline_rms += self.ema_alpha * diff
        self.ambient_var = (1.0 - self.ema_alpha) * self.ambient_var + self.ema_alpha * (diff ** 2)
        std_rms = math.sqrt(max(self.ambient_var, 1e-6))
        dynamic_threshold = self.baseline_rms + (self.dynamic_sigma_k * std_rms)

        # Trigger logic: Fixed absolute threshold OR dynamic statistical spike
        is_absolute_spike = audio_db >= self.spike_db_threshold
        is_dynamic_spike = (rms > dynamic_threshold) and (rms > 0.04)
        trigger_fired = bool(is_absolute_spike or is_dynamic_spike)

        return trigger_fired, round(audio_db, 1), round(rms, 4)

    def reset(self):
        self.audio_buffer.clear()
        self.baseline_rms = 0.02
        self.ambient_var = 1e-4
