""" Pygame cutter: playback, precise timestamps, keyboard editing and instant ffmpeg export """

from moviepy.video.io.VideoFileClip import VideoFileClip
import subprocess
import threading
import pygame
import json
import time
import os


def ffmpeg_cut(video_path: str, start_s: float, end_s: float, output_path: str):
    """ Cuts video segment using ffmpeg """

    if end_s <= start_s:
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


def export_clip_thread(video_path: str, start_s: float, end_s: float, output_path: str, on_done=None):
    """ Runs ffmpeg export in a background thread """

    try:
        ffmpeg_cut(video_path, start_s, end_s, output_path)
    finally:
        if on_done:
            try:
                on_done(output_path)
            except Exception:
                pass


def format_time(ms: int) -> str:
    """ Formats milliseconds to H:MM:SS.mmm """

    s, msr = divmod(ms, 1000)
    m, s = divmod(s, 60)
    h, m = divmod(m, 60)
    return f"{h}:{m:02d}:{s:02d}.{msr:03d}"


def run_interactive(video_path: str, output_dir: str):
    """ Plays video with pygame, supports keyboard-based editing and instant exports """

    os.makedirs(output_dir, exist_ok=True)
    clip = VideoFileClip(video_path)
    duration = clip.duration
    fps = clip.fps or 25
    width, height = clip.size
    audio = clip.audio
    temp_wav = "_temp_audio.wav"
    if os.path.exists(temp_wav):
        try:
            os.remove(temp_wav)
        except Exception:
            pass
    audio.write_audiofile(temp_wav, fps=48000, nbytes=2, codec="pcm_s16le")
    pygame.init()
    try:
        pygame.mixer.init(frequency=48000)
    except Exception:
        pygame.mixer.init()
    pygame.mixer.music.load(temp_wav)
    screen = pygame.display.set_mode((width, height))
    pygame.display.set_caption("Cutter - C start/end  Backspace cancel  Space pause  ←/→ 5s  ↑/↓ 10s  S save")
    font = pygame.font.SysFont(None, 36)
    small_font = pygame.font.SysFont(None, 30)
    clock = pygame.time.Clock()
    segments = []
    exporting = []
    start_ms = None
    clip_index = 1
    paused = False
    play_pos = 0.0
    last_tick = time.time()
    pygame.mixer.music.play(start=0.0)
    running = True

    def on_export_done(path: str):
        """ On export done """

        try:
            exporting.remove(path)
        except Exception:
            pass

    while running:
        now = time.time()
        dt = now - last_tick
        last_tick = now
        if not paused:
            play_pos += dt
            if play_pos > duration:
                play_pos = duration
                paused = True
                pygame.mixer.music.stop()
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_q:
                    running = False
                if event.key == pygame.K_SPACE:
                    if paused:
                        paused = False
                        try:
                            pygame.mixer.music.play(start=play_pos)
                        except Exception:
                            pygame.mixer.music.play()
                    else:
                        paused = True
                        pygame.mixer.music.pause()
                if event.key == pygame.K_c:
                    ms = int(play_pos * 1000)
                    if start_ms is None:
                        start_ms = ms
                    else:
                        end_ms = ms
                        if end_ms <= start_ms + 10:
                            start_ms = None
                        else:
                            start_s = start_ms / 1000.0
                            end_s = end_ms / 1000.0
                            out = os.path.join(output_dir, f"clip_{clip_index:03d}.mp4")
                            exporting.append(out)
                            th = threading.Thread(target=export_clip_thread,
                                                  args=(video_path, start_s, end_s, out, on_export_done), daemon=True)
                            th.start()
                            segments.append((start_ms, end_ms, out))
                            clip_index += 1
                            start_ms = None
                if event.key == pygame.K_BACKSPACE:
                    start_ms = None
                if event.key == pygame.K_s:
                    save_path = os.path.join(output_dir, "segments.json")
                    tosave = [{"start_ms": s, "end_ms": e, "file": f} for s, e, f in segments]
                    with open(save_path, "w", encoding="utf-8") as fh:
                        json.dump(tosave, fh, indent=2)
                if event.key == pygame.K_LEFT:
                    play_pos = max(0.0, play_pos - 5.0)
                    try:
                        if not paused:
                            pygame.mixer.music.play(start=play_pos)
                    except Exception:
                        pygame.mixer.music.stop()
                        pygame.mixer.music.play()
                if event.key == pygame.K_RIGHT:
                    play_pos = min(duration, play_pos + 5.0)
                    try:
                        if not paused:
                            pygame.mixer.music.play(start=play_pos)
                    except Exception:
                        pygame.mixer.music.stop()
                        pygame.mixer.music.play()
                if event.key == pygame.K_UP:
                    play_pos = min(duration, play_pos + 10.0)
                    try:
                        if not paused:
                            pygame.mixer.music.play(start=play_pos)
                    except Exception:
                        pygame.mixer.music.stop()
                        pygame.mixer.music.play()
                if event.key == pygame.K_DOWN:
                    play_pos = max(0.0, play_pos - 10.0)
                    try:
                        if not paused:
                            pygame.mixer.music.play(start=play_pos)
                    except Exception:
                        pygame.mixer.music.stop()
                        pygame.mixer.music.play()
        t = max(0.0, min(duration, play_pos))
        try:
            frame = clip.get_frame(t)
            surf = pygame.surfarray.make_surface(frame.swapaxes(0, 1))
            screen.blit(surf, (0, 0))
        except Exception:
            screen.fill((0, 0, 0))
        time_text = format_time(int(t * 1000))
        txt = font.render(f"Time: {time_text}  {'PAUSED' if paused else 'PLAYING'}", True, (255, 255, 255))
        screen.blit(txt, (8, 8))
        if start_ms is None:
            status = "Start: NOT SET (press C)"
        else:
            status = f"Start: {format_time(start_ms)} (press C to set end or Backspace to cancel)"
        status_surf = small_font.render(status, True, (255, 0, 0))
        screen.blit(status_surf, (8, 36))
        seg_y = 64
        list_title = small_font.render("Saved segments:", True, (255, 255, 255))
        screen.blit(list_title, (8, seg_y))
        seg_y += 20
        for i, (s, e, fname) in enumerate(reversed(segments[-10:])):
            line = f"{len(segments) - i}: {format_time(s)} → {format_time(e)}"
            line_surf = small_font.render(line, True, (255, 255, 255))
            screen.blit(line_surf, (8, seg_y))
            seg_y += 18
        exporting_y = height - 24
        if exporting:
            exp_txt = small_font.render(f"Exporting: {len(exporting)} clip(s)...", True, (255, 0, 0))
            screen.blit(exp_txt, (8, exporting_y))
        hints = small_font.render("C start/end  Space pause  ←/→ 5s  ↑/↓ 10s  Backspace cancel start  S save JSON  Q quit", True,
                                  (255, 255, 255))
        screen.blit(hints, (8, height - 44))
        pygame.display.flip()
        clock.tick(fps if fps > 0 else 30)
    try:
        pygame.mixer.music.stop()
    except Exception:
        pass
    try:
        if os.path.exists(temp_wav):
            os.remove(temp_wav)
    except Exception:
        pass
    try:
        clip.close()
    except Exception:
        pass


def main(video_path: str, output_dir: str):
    """ Launches cutter """

    run_interactive(video_path, output_dir)


if __name__ == "__main__":
    main(
        r"C:\Users\dmitry\Downloads\enS9E1.mp4",
        "clips"
    )
