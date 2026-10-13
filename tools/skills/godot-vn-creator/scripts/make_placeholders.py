# -*- coding: utf-8 -*-
"""为缺失资产生成占位图（自动从剧情 JSON 扫描引用，真图到位后直接覆盖）。

用法：<带 PIL 的 python> make_placeholders.py <项目根目录> [剧情JSON路径=story/main.json]
- 扫描剧情中所有 bg（asset）与 show（character+emotion）引用；
- 已存在的文件一律跳过，只为缺失项生成带标注的占位图；
- 背景为渐变底 + 居中标注，立绘为人形剪影 + 标注。
"""
import json
import os
import sys

from PIL import Image, ImageDraw, ImageFont

ROOT = sys.argv[1] if len(sys.argv) > 1 else "."
STORY = sys.argv[2] if len(sys.argv) > 2 else "story/main.json"

# 中文字体跨平台回退链
FONT_CANDIDATES = [
    "C:/Windows/Fonts/msyh.ttc",            # Windows 微软雅黑
    "C:/Windows/Fonts/simhei.ttf",          # Windows 黑体
    "/System/Library/Fonts/PingFang.ttc",   # macOS
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",  # Linux Noto
    "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",            # Linux 文泉驿
]

# 占位图配色按名字哈希生成，保证同一资产每次颜色一致
def palette(name: str):
    h = abs(hash(name))
    top = (20 + h % 40, 15 + (h >> 4) % 35, 25 + (h >> 8) % 45)
    bottom = (top[0] + 50, top[1] + 45, top[2] + 55)
    return top, bottom


def font(size):
    for p in FONT_CANDIDATES:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except OSError:
                continue
    return ImageFont.load_default()


def gradient(size, top, bottom):
    w, h = size
    img = Image.new("RGB", size)
    d = ImageDraw.Draw(img)
    for y in range(h):
        t = y / max(h - 1, 1)
        c = tuple(int(a + (b - a) * t) for a, b in zip(top, bottom))
        d.line([(0, y), (w, y)], fill=c)
    return img


def scan_story(path):
    """从剧情 JSON 提取引用的背景与立绘清单。"""
    backgrounds, sprites = set(), set()
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    for scene in data.get("scenes", {}).values():
        for c in scene.get("commands", []):
            if c.get("cmd") == "bg" and c.get("asset"):
                backgrounds.add(c["asset"])
            if c.get("cmd") == "show" and c.get("character"):
                sprites.add((c["character"], c.get("emotion", "default")))
    return sorted(backgrounds), sorted(sprites)


def make_background(name):
    top, bottom = palette(name)
    img = gradient((1920, 1080), top, bottom)
    d = ImageDraw.Draw(img)
    text = f"[占位] {name}"
    f = font(72)
    bbox = d.textbbox((0, 0), text, font=f)
    d.text(((1920 - bbox[2]) / 2, (1080 - bbox[3]) / 2), text, font=f, fill=(220, 220, 220))
    out = os.path.join(ROOT, "assets/backgrounds", name + ".png")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    img.save(out)
    print("占位背景:", name)


def make_sprite(char, emotion):
    top, _ = palette(f"{char}/{emotion}")
    img = Image.new("RGBA", (600, 1800), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    color = (*top, 255)
    d.ellipse([220, 80, 380, 260], fill=color)                                # 头
    d.rounded_rectangle([160, 280, 440, 1400], radius=60, fill=color)          # 身体
    d.rounded_rectangle([190, 1400, 270, 1780], radius=30, fill=color)         # 左腿
    d.rounded_rectangle([330, 1400, 410, 1780], radius=30, fill=color)         # 右腿
    f = font(40)
    d.text((60, 850), f"[占位]\n{char}/{emotion}", font=f, fill=(255, 255, 255))
    out = os.path.join(ROOT, "assets/characters", char, emotion + ".png")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    img.save(out)
    print("占位立绘:", char, emotion)


def main():
    story_path = os.path.join(ROOT, STORY)
    if not os.path.exists(story_path):
        print(f"剧情文件不存在: {story_path}", file=sys.stderr)
        sys.exit(1)
    backgrounds, sprites = scan_story(story_path)
    made = 0
    for name in backgrounds:
        if not os.path.exists(os.path.join(ROOT, "assets/backgrounds", name + ".png")):
            make_background(name)
            made += 1
    for char, emotion in sprites:
        if not os.path.exists(os.path.join(ROOT, "assets/characters", char, emotion + ".png")):
            make_sprite(char, emotion)
            made += 1
    print(f"完成，共生成 {made} 张占位图。")


if __name__ == "__main__":
    main()
