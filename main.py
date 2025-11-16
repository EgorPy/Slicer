""" Video slicer: split by human speech using webrtcvad + energy heuristics.

    - Extracts mono 16k WAV via MoviePy
    - Uses webrtcvad to detect voice activity
    - Uses RMS variability filter to reject music falsely classified as speech
    - Splits long segments (> 3 minutes) and ignores very short segments
    - Cuts final clips with ffmpeg for Windows compatibility
"""

from moviepy.video.io.VideoFileClip import VideoFileClip

import os
import subprocess
import soundfile as sf
import numpy as np
import webrtcvad
from typing import List, Tuple


def extract_audio(video_path: str, wav_path: str):
    """ Extract audio as mono 16kHz 16-bit WAV suitable for VAD """

    video = VideoFileClip(video_path)
    audio = video.audio
    audio.write_audiofile(
        wav_path,
        codec="pcm_s16le",
        fps=16000,
        ffmpeg_params=["-ac", "1"]
    )
    video.close()


def load_wav_as_float(path: str):
    """ Load WAV and return float32 numpy array in range [-1, 1] and sample rate """

    data, sr = sf.read(path, dtype='float32')
    if data.ndim > 1:
        data = data[:, 0]
    return data, sr


def frames_from_audio(audio: np.ndarray, sr: int, frame_ms: int):
    """ Yield (frame_bytes, frame_array) for VAD and feature extraction """

    frame_size = int(sr * frame_ms / 1000)
    pad = (len(audio) % frame_size)
    if pad != 0:
        audio = np.concatenate([audio, np.zeros(frame_size - pad, dtype=audio.dtype)])
    n_frames = len(audio) // frame_size
    int16 = (audio * 32767).astype(np.int16)
    for i in range(n_frames):
        start = i * frame_size
        end = start + frame_size
        chunk = int16[start:end]
        yield chunk.tobytes(), audio[start:end]


def compute_rms_array(frames_array: List[np.ndarray]):
    """ Compute RMS per frame from list of numpy arrays """

    rms = np.array([np.sqrt(np.mean(f.astype(np.float32) ** 2) + 1e-12) for f in frames_array], dtype=np.float32)
    return rms


def rolling_std(x: np.ndarray, window: int):
    """ Fast rolling std using convolution """

    if window <= 1:
        return np.zeros_like(x)
    c1 = np.convolve(x, np.ones(window, dtype=float), mode='same') / window
    c2 = np.convolve(x * x, np.ones(window, dtype=float), mode='same') / window
    var = c2 - c1 * c1
    var[var < 0] = 0.0
    return np.sqrt(var)


def vad_with_music_filter(audio: np.ndarray,
                          sr: int,
                          frame_ms: int = 30,
                          vad_mode: int = 2,
                          padding_ms: int = 1200,
                          rms_std_thresh: float = 0.002,
                          rms_mean_thresh: float = 0.01,
                          min_segment_ms: int = 300,
                          max_segment_ms: int = 180000) -> List[Tuple[int, int]]:
    """ Return list of (start_ms, end_ms) speech segments using VAD + energy filter """

    vad = webrtcvad.Vad(vad_mode)

    frame_bytes = []
    frame_arrays = []
    for b, arr in frames_from_audio(audio, sr, frame_ms):
        frame_bytes.append(b)
        frame_arrays.append(arr)

    rms = compute_rms_array(frame_arrays)
    window_frames = max(1, int(1000 / frame_ms))  # 1 second window
    rms_std = rolling_std(rms, window_frames)

    is_speech = [vad.is_speech(b, sr) for b in frame_bytes]

    adjusted = []
    for i, flag in enumerate(is_speech):
        if not flag:
            adjusted.append(False)
            continue
        if rms[i] >= rms_mean_thresh and rms_std[i] < rms_std_thresh:
            adjusted.append(False)
        else:
            adjusted.append(True)

    # collect segments with padding
    frames = len(adjusted)
    pad_frames = int(padding_ms / frame_ms)
    segments = []
    start = None
    silence_count = 0
    for i, val in enumerate(adjusted):
        if val:
            if start is None:
                start = i
            silence_count = 0
        else:
            if start is not None:
                silence_count += 1
                if silence_count > pad_frames:
                    seg_start_ms = start * frame_ms
                    seg_end_ms = (i - silence_count + 1) * frame_ms
                    if seg_end_ms - seg_start_ms >= min_segment_ms:
                        segments.append((seg_start_ms, seg_end_ms))
                    start = None
                    silence_count = 0
    if start is not None:
        seg_start_ms = start * frame_ms
        seg_end_ms = frames * frame_ms
        if seg_end_ms - seg_start_ms >= min_segment_ms:
            segments.append((seg_start_ms, seg_end_ms))

    # split long segments
    final = []
    for s, e in segments:
        length = e - s
        if length <= max_segment_ms:
            final.append((s, e))
        else:
            t = s
            while t + max_segment_ms < e:
                final.append((t, t + max_segment_ms))
                t += max_segment_ms
            final.append((t, e))

    return final


def ffmpeg_cut(video_path: str, start_s: float, end_s: float, output_path: str):
    """ Cut segment with ffmpeg (re-encode for compatibility) """

    if end_s <= start_s + 0.001:
        return
    cmd = [
        "ffmpeg",
        "-hide_banner", "-loglevel", "error",
        "-y",
        "-ss", f"{start_s:.3f}",
        "-to", f"{end_s:.3f}",
        "-i", video_path,
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-crf", "23",
        "-c:a", "aac",
        "-b:a", "160k",
        "-ac", "2",
        "-ar", "48000",
        "-movflags", "+faststart",
        output_path
    ]
    subprocess.run(cmd, check=True)


def cut_video(video_path: str, segments: List[Tuple[int, int]], output_dir: str):
    """ Cut all segments and save to output_dir """

    os.makedirs(output_dir, exist_ok=True)
    for idx, (s_ms, e_ms) in enumerate(segments, start=1):
        start_s = s_ms / 1000.0
        end_s = e_ms / 1000.0
        out = os.path.join(output_dir, f"clip_{idx:03d}.mp4")
        ffmpeg_cut(video_path, start_s, end_s, out)


def main(video_path: str, output_dir: str):
    """ Full pipeline """

    wav = "temp_audio.wav"
    extract_audio(video_path, wav)
    audio, sr = load_wav_as_float(wav)

    segments = vad_with_music_filter(
        audio,
        sr,
        frame_ms=30,
        vad_mode=3,
        padding_ms=1200,
        rms_std_thresh=0.002,
        rms_mean_thresh=0.01,
        min_segment_ms=300,
        max_segment_ms=180000
    )

    if not segments:
        print("No speech detected.")
    else:
        cut_video(video_path, segments, output_dir)

    try:
        os.remove(wav)
    except OSError:
        pass


if __name__ == "__main__":
    main(r"C:\Users\dmitry\Downloads\Family Guy S9E1.mp4", "clips")
