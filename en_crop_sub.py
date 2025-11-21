import os
import subprocess
import whisper


def transcribe_audio(video_path):
    model = whisper.load_model("large-v3")
    result = model.transcribe(video_path, language="en")
    return result["segments"]


def create_srt(segments, srt_path):
    with open(srt_path, "w", encoding="utf-8") as f:
        for i, seg in enumerate(segments, 1):
            start = seg["start"]
            end = seg["end"]
            text = seg["text"].strip()

            def fmt(t):
                h = int(t // 3600)
                m = int((t % 3600) // 60)
                s = int(t % 60)
                ms = int((t - int(t)) * 1000)
                return f"{h:02}:{m:02}:{s:02},{ms:03}"

            f.write(f"{i}\n{fmt(start)} --> {fmt(end)}\n{text}\n\n")


def convert_vertical_with_subs(video_path, output_path, srt_path):
    safe_srt = srt_path.replace("\\", "/")

    style = (
        "Alignment=2,"
        "Fontsize=22,"
        "PrimaryColour=&HFFFFFF&,"
        "OutlineColour=&H000000&,"
        "BackColour=&H000000&,"
        "BorderStyle=1,"
        "Outline=4,"
        "Shadow=0,"
        "MarginV=40"
    )

    vf = (
        "scale=720:1280:force_original_aspect_ratio=decrease,"
        "pad=720:1280:(ow-iw)/2:(oh-ih)/2,"
        f"subtitles='{safe_srt}:force_style={style}'"
    )

    cmd = [
        "ffmpeg", "-y",
        "-hide_banner", "-loglevel", "error",
        "-i", video_path,
        "-vf", vf,
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
    os.makedirs(output_folder, exist_ok=True)

    for fname in os.listdir(input_folder):
        if fname.lower().endswith((".mp4", ".mov", ".mkv", ".avi")):
            in_path = os.path.join(input_folder, fname)
            base = os.path.splitext(fname)[0]

            srt_path = os.path.join(output_folder, base + ".srt")
            out_path = os.path.join(output_folder, base + "_vertical.mp4")

            print(f"Transcribing {fname}...")
            segments = transcribe_audio(in_path)
            create_srt(segments, srt_path)

            print(f"Rendering video {fname}...")
            convert_vertical_with_subs(in_path, out_path, srt_path)

            print(f"Saved: {out_path}")


if __name__ == "__main__":
    input_folder = r"good_clips/enS9E1"
    output_folder = r"en_clips_vertical"
    process_folder(input_folder, output_folder)
