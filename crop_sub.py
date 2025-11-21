"""
Batch convert video clips to vertical 9:16 format using ffmpeg.
"""

import os
import subprocess


def convert_vertical(video_path, output_path):
    """
    Convert a horizontal video into a centered 9:16 vertical format.
    """

    cmd = [
        "ffmpeg", "-y",
        "-hide_banner", "-loglevel", "error",
        "-i", video_path,
        "-vf",
        "scale=720:1280:force_original_aspect_ratio=decrease,"
        "pad=720:1280:(ow-iw)/2:(oh-ih)/2",
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


def process_folder(input_folder, output_folder):
    """
    Process an entire folder and convert every video to vertical format.
    """

    os.makedirs(output_folder, exist_ok=True)

    for fname in os.listdir(input_folder):
        if fname.lower().endswith((".mp4", ".mov", ".mkv", ".avi")):
            in_path = os.path.join(input_folder, fname)
            out_path = os.path.join(output_folder, os.path.splitext(fname)[0] + "_vertical.mp4")
            print(f"Processing {fname}...")
            convert_vertical(in_path, out_path)
            print(f"Saved: {out_path}")


if __name__ == "__main__":
    input_folder = r"good_clips/S9E1"
    output_folder = r"clips_vertical"
    process_folder(input_folder, output_folder)
