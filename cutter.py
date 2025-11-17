""" Manual cutter: split by given list of video times.

    - Splits long segments (> 3 minutes) and ignores very short segments
    - Cuts final clips with ffmpeg for Windows compatibility
"""

from typing import List, Tuple
import subprocess
import os


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


def main(video_path: str, output_dir: str, segments: List[Tuple[int, int]]):
    """ Full pipeline """

    cut_video(video_path, segments, output_dir)


if __name__ == "__main__":
    main(
        r"C:\Users\dmitry\Downloads\Family Guy S9E1.mp4",
        "clips",
        [
            (5500, 57000),
            (4 * 60000 + 10000, 4 * 60000 + 23000),
        ]
    )
