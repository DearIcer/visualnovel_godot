# -*- coding: utf-8 -*-
"""绿幕抠图 + 自动裁边 + 统一高度，用于视觉小说立绘后处理。

用法：python remove_bg.py 输入.png 输出.png [目标高度=1800]
"""
import sys

import numpy as np
from PIL import Image, ImageFilter


def key_green(img: Image.Image) -> Image.Image:
    """将纯绿背景（#00FF00）转为透明，并对边缘做去绿溢色。"""
    arr = np.asarray(img.convert("RGB")).astype(np.int16)
    r, g, b = arr[..., 0], arr[..., 1], arr[..., 2]
    greenness = g - np.maximum(r, b)

    alpha = np.full(greenness.shape, 255, dtype=np.uint8)
    alpha[greenness > 40] = 0
    soft = (greenness > 15) & (greenness <= 40)
    alpha[soft] = ((40 - greenness[soft]) * (255 / 25)).astype(np.uint8)

    # 去绿溢色：半透明区域压掉绿色分量
    spill = (alpha > 0) & (greenness > 0)
    g2 = g.copy()
    g2[spill] = np.minimum(g[spill], np.maximum(r[spill], b[spill]) + 15)

    out = np.dstack([
        r.astype(np.uint8), g2.astype(np.uint8), b.astype(np.uint8), alpha
    ])
    res = Image.fromarray(out, "RGBA")
    # 中值滤波清理零星噪点
    a_ch = res.getchannel("A").filter(ImageFilter.MedianFilter(3))
    res.putalpha(a_ch)
    return res


def autocrop(img: Image.Image, margin: int = 8) -> Image.Image:
    """按 alpha 通道裁掉透明边，保留少量边距。"""
    bbox = img.getchannel("A").getbbox()
    if bbox is None:
        return img
    x0, y0, x1, y1 = bbox
    x0 = max(0, x0 - margin)
    y0 = max(0, y0 - margin)
    x1 = min(img.width, x1 + margin)
    y1 = min(img.height, y1 + margin)
    return img.crop((x0, y0, x1, y1))


def main() -> None:
    if len(sys.argv) < 3:
        print("用法: python remove_bg.py 输入.png 输出.png [目标高度]")
        sys.exit(1)
    src, dst = sys.argv[1], sys.argv[2]
    target_h = int(sys.argv[3]) if len(sys.argv) > 3 else 1800

    img = Image.open(src)
    img = key_green(img)
    img = autocrop(img)
    if img.height != target_h:
        w = round(img.width * target_h / img.height)
        img = img.resize((w, target_h), Image.LANCZOS)
    img.save(dst)
    print(f"完成: {dst} ({img.width}x{img.height})")


if __name__ == "__main__":
    main()
