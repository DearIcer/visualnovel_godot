# -*- coding: utf-8 -*-
"""合成三个剧情音效：heartbeat（心跳）、phone_vibrate（手机震动）、thud（闷响）。

用法：<带 numpy 的 python> make_se.py <输出目录>
输出 16bit 44.1kHz WAV。
"""
import sys
import wave

import numpy as np

SR = 44100


def save_wav(path: str, data: np.ndarray) -> None:
    pcm = np.clip(data, -1.0, 1.0)
    pcm16 = (pcm * 32767).astype(np.int16)
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm16.tobytes())


def heartbeat() -> np.ndarray:
    """低频双跳：lub-dub，一次约 1.1 秒。"""
    t = np.arange(int(SR * 1.1)) / SR
    out = np.zeros_like(t)

    def thump(start: float, freq: float, amp: float, decay: float) -> None:
        idx = t >= start
        tt = t[idx] - start
        out[idx] += amp * np.sin(2 * np.pi * freq * tt) * np.exp(-tt * decay)

    thump(0.0, 55, 0.9, 18)
    thump(0.28, 48, 0.7, 22)
    return out


def phone_vibrate() -> np.ndarray:
    """方波蜂鸣两段：嗡-嗡。"""
    t = np.arange(int(SR * 1.4)) / SR
    out = np.zeros_like(t)

    def buzz(start: float, dur: float) -> None:
        idx = (t >= start) & (t < start + dur)
        tt = t[idx] - start
        env = np.minimum(tt / 0.01, 1.0) * np.minimum((dur - tt) / 0.05, 1.0)
        out[idx] += 0.5 * np.sign(np.sin(2 * np.pi * 180 * tt)) * env

    buzz(0.0, 0.45)
    buzz(0.65, 0.45)
    return out


def thud() -> np.ndarray:
    """低闷撞击：低频正弦骤衰 + 少量滤波噪声。"""
    t = np.arange(int(SR * 0.6)) / SR
    body = np.sin(2 * np.pi * 60 * t) * np.exp(-t * 12)
    noise = np.random.default_rng(7).normal(0, 1, len(t))
    # 简单一阶低通
    lp = np.cumsum(noise) * 0.02
    out = 0.9 * body + 0.25 * lp * np.exp(-t * 25)
    return out


def main() -> None:
    out_dir = sys.argv[1] if len(sys.argv) > 1 else "."
    for name, fn in (("heartbeat", heartbeat), ("phone_vibrate", phone_vibrate), ("thud", thud)):
        save_wav(f"{out_dir}/{name}.wav", fn())
        print(f"生成: {out_dir}/{name}.wav")


if __name__ == "__main__":
    main()
