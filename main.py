""" Video slicer: split by human speech using Silero VAD (torch + torchaudio).

    - Extracts mono 16k WAV via MoviePy
    - Uses Silero VAD to detect voice activity (accurate speech/music separation)
    - Splits long segments (> 3 minutes) and ignores very short segments
    - Cuts final clips with ffmpeg for Windows compatibility
"""

from silero_vad import load_silero_vad, get_speech_timestamps
from moviepy.video.io.VideoFileClip import VideoFileClip
from typing import List, Tuple
import soundfile as sf
import subprocess
import torchaudio
import os


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


def vad_silero(
        audio_path: str,
        min_segment_s: float = 10,
        max_segment_s: float = 1800.0,
        left_padding_s: float = 0.5,
        right_padding_s: float = 1.5,
        silence_timeout_s: float = 0.8
) -> List[Tuple[int, int]]:
    """
    Return list of (start_ms, end_ms) speech segments using Silero VAD with:
        - padding_s: добавляет паузу перед и после сегмента
        - silence_timeout_s: объединяет сегменты, разделённые короткой тишиной
    """

    model = load_silero_vad()
    waveform, sr = torchaudio.load(audio_path)
    if waveform.shape[0] > 1:
        waveform = waveform[0]
    waveform = waveform.squeeze()

    speech_ts = get_speech_timestamps(waveform, model, sampling_rate=sr, return_seconds=True)

    merged_segments = []
    for ts in speech_ts:
        start_s = ts['start']
        end_s = ts['end']
        if merged_segments and start_s - merged_segments[-1][1] <= silence_timeout_s:
            merged_segments[-1] = (merged_segments[-1][0], end_s)
        else:
            merged_segments.append((start_s, end_s))

    final_segments = []
    for s, e in merged_segments:
        s = max(s - left_padding_s, 0.0)
        e = e + right_padding_s
        if e - s >= min_segment_s:
            t = s
            while t + max_segment_s < e:
                final_segments.append((int(t * 1000), int((t + max_segment_s) * 1000)))
                t += max_segment_s
            final_segments.append((int(t * 1000), int(e * 1000)))

    return final_segments


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
    if sr != 16000:
        raise RuntimeError(f"Expected 16 kHz WAV, got {sr}")

    segments = vad_silero(wav)

    if not segments:
        print("No speech detected.")
    else:
        cut_video(video_path, segments, output_dir)

    try:
        os.remove(wav)
    except OSError:
        pass


if __name__ == "__main__":
    main(
        r"C:\Users\dmitry\Downloads\Family Guy S9E1.mp4",
        "clips"
    )
