# -*- coding: utf-8 -*-
"""将 presentation/frames/slide_*.png 合成为带转场与配乐的 1080p mp4。

两步走：先逐页渲染 CFR 中间片段（zoompan 呼吸推拉），再 xfade 串联 + 配乐。
（直接从静帧进 xfade 会报 "current rate of 1/0 is invalid"，必须先生成实体片段。）
"""
import os
import subprocess
import sys

import imageio_ffmpeg

HERE = os.path.dirname(os.path.abspath(__file__))
FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()

DURS = [5, 8, 7, 9, 7, 6, 8, 7, 6, 7]   # 与 index.html data-dur 一致
FPS = 30
XFADE = 0.5
OUT = os.path.join(HERE, "交互式文本-项目介绍.mp4")


def run(cmd):
    subprocess.run(cmd, check=True, capture_output=True)


def main():
    # 第一步：逐页渲染中间片段
    segs = []
    for i, d in enumerate(DURS):
        src = os.path.join(HERE, "frames", f"slide_{i}.png")
        if not os.path.exists(src):
            sys.exit(f"缺帧: {src}")
        seg = os.path.join(HERE, "frames", f"seg_{i}.mp4")
        z = "min(1+0.0009*on,1.10)" if i % 2 == 0 else "max(1.10-0.0009*on,1.001)"
        run([FFMPEG, "-y", "-loop", "1", "-framerate", str(FPS), "-t", str(d), "-i", src,
             "-vf", f"scale=1920:1080,zoompan=z='{z}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=1:s=1920x1080:fps={FPS},format=yuv420p",
             "-c:v", "libx264", "-crf", "18", "-preset", "fast", "-pix_fmt", "yuv420p", seg])
        segs.append(seg)
        print(f"片段 {i} 完成 ({d}s)")

    # 第二步：xfade 串联 + 配乐
    inputs = []
    for s in segs:
        inputs += ["-i", s]
    inputs += ["-i", os.path.join(HERE, "assets", "bgm.ogg")]

    parts = []
    total = float(DURS[0])
    prev = "[0:v]"
    for i in range(1, len(DURS)):
        offset = total - XFADE
        trans = "fadeblack" if i == len(DURS) - 1 else "fade"
        out = f"[x{i}]"
        parts.append(f"{prev}[{i}:v]xfade=transition={trans}:duration={XFADE}:offset={offset:.2f}{out}")
        prev = out
        total += DURS[i] - XFADE

    audio_idx = len(DURS)
    parts.append(f"[{audio_idx}:a]atrim=0:{total:.2f},afade=t=out:st={total-3:.2f}:d=3,volume=0.8[aout]")

    run([FFMPEG, "-y", *inputs,
         "-filter_complex", ";".join(parts),
         "-map", prev, "-map", "[aout]",
         "-c:v", "libx264", "-crf", "20", "-preset", "medium", "-pix_fmt", "yuv420p",
         "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart",
         "-t", f"{total:.2f}", OUT])

    for s in segs:  # 清理中间片段
        os.remove(s)
    print(f"完成: {OUT}（{total:.1f}s）")


if __name__ == "__main__":
    main()
