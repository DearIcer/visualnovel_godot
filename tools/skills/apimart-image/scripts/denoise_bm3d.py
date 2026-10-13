#!/usr/bin/env python3
"""BM3D 降噪后处理：RGB 三通道分别降噪。

由 gen_image 流程在 nano-banana-2 / seedream-5-0-pro 出图后自动调用，
也可独立使用：

  python denoise_bm3d.py [--strength 20] 图片路径 [图片路径...]

sigma_psd = strength / 255（strength 20 即 σ=20/255）。
依赖（装在 skill 目录的 .venv 中）：bm3d、numpy、Pillow。
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
from bm3d import bm3d
from PIL import Image


def denoise_image(path: Path, strength: float) -> None:
    """对单张图片做 RGB 分通道 BM3D 降噪，原地覆盖保存。"""
    img = Image.open(path)
    alpha = None
    if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
        img = img.convert("RGBA")
        arr = np.asarray(img)
        alpha = arr[..., 3]
        rgb = arr[..., :3]
    else:
        rgb = np.asarray(img.convert("RGB"))

    sigma = strength / 255.0
    data = rgb.astype(np.float64) / 255.0
    out = np.empty_like(data)
    for channel in range(3):
        out[..., channel] = bm3d(data[..., channel], sigma)
    result = np.clip(out * 255.0 + 0.5, 0, 255).astype(np.uint8)

    if alpha is not None:
        merged = np.dstack([result, alpha])
        Image.fromarray(merged, "RGBA").save(path)
    else:
        Image.fromarray(result, "RGB").save(path)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="BM3D RGB 分通道降噪")
    parser.add_argument("--strength", type=float, default=20.0, help="噪声强度 σ（默认 20，即 20/255）")
    parser.add_argument("images", nargs="+", help="待降噪图片路径（原地覆盖）")
    args = parser.parse_args(argv)

    failures = 0
    for name in args.images:
        path = Path(name)
        try:
            denoise_image(path, args.strength)
            print(path.resolve(), flush=True)
        except Exception as error:  # noqa: BLE001 - 单张失败不影响其余图片
            failures += 1
            print(f"ERROR: 降噪失败: {path} ({error})", file=sys.stderr, flush=True)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
