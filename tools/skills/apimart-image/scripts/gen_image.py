#!/usr/bin/env python3
"""apimart.ai 生图脚本（Windows / 无 bash 环境下的等价实现）。

流程：读取 API Key -> 提交任务 -> 轮询 -> 下载图片。
支持 gpt-image-2（默认）、gpt-image-2.5-ext（flare / sunburst）、
nano-banana-2（gemini-3.1-flash-image-preview 系列）、nano-banana-2.1 系列
与 seedream-5-0-pro。

用法:
  python gen_image.py [选项] "提示词" [size] [resolution] [输出目录] [参考图URL或本地路径...]

选项:
  --model MODEL      gpt-image-2（默认）、gpt-image-2.5-ext、
                     nano-banana-2（官方版，= gemini-3.1-flash-image-preview-official）、
                     nano-banana-2-ext（标准版，= gemini-3.1-flash-image-preview）、
                     gemini-nano-banana-2.1（2.1 官方版，n 支持 1~4）、
                     gemini-nano-banana-2.1-ext（2.1 Ext 版，n 只能为 1）、
                     seedream-5-0-pro（亦接受 seedream-5.0-pro）
  --version VER      2.5 模型版本：flare（默认）或 sunburst
  --n N              生成张数：仅 2.5 与 nano-banana-2.1 官方版支持 1~4；其余模型固定为 1
  --google-search        nano-banana-2：启用 Google 文字搜索增强（2.1 不支持）
  --google-image-search  nano-banana-2：启用 Google 图片搜索增强（需配合 --google-search）
  --official-fallback    nano-banana-2-ext / gemini-nano-banana-2.1-ext：失败时兜底官方版
                         （官方版不可用）
  --output-format FMT    seedream-5-0-pro：输出格式 jpeg（默认）或 png
  --watermark            seedream-5-0-pro：右下角添加 "AI generated" 水印
  --transparent          seedream-5-0-pro：透明背景（需恰好 1 张带透明通道的参考图 + png 输出）
  --no-denoise           跳过 BM3D 降噪后处理（nano-banana-2 / nano-banana-2.1 / seedream-5-0-pro
                         出图后默认自动做 BM3D RGB 三通道降噪，σ=20/255；依赖 skill 目录 .venv
                         中的 bm3d/pillow/numpy，缺失时告警并保留原图）

示例:
  python gen_image.py "一只橘猫坐在窗台上看夕阳，水彩画风格" 16:9 2k
  python gen_image.py --model gpt-image-2.5-ext --version sunburst --n 2 "极简产品海报" 16:9 2K ./out ./ref.png
  python gen_image.py --model nano-banana-2 --google-search "今日上海外滩实景风格海报" 16:9 2K
  python gen_image.py --model gemini-nano-banana-2.1 --n 4 "赛博朋克风格的城市夜景，霓虹灯" 16:9 2K
  python gen_image.py --model seedream-5-0-pro "水墨风格的江南小镇，清晨薄雾" 16:9 1.5K ./out
"""

from __future__ import annotations

import argparse
import base64
import http.client
import json
import mimetypes
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from datetime import datetime
from pathlib import Path

API_BASE = "https://api.apimart.ai/v1"
KEY_FILE = Path.home() / ".kimi-code" / "skills" / "apimart-image" / "api_key"
# 兼容 DSH 安装位置（~/.dsh/skills/apimart-image/api_key）
KEY_FILE_ALT = Path.home() / ".dsh" / "skills" / "apimart-image" / "api_key"

POLL_INTERVAL_SECONDS = 5
POLL_MAX_ATTEMPTS = 120  # 5s * 120 = 最多等待 10 分钟

# nano-banana-2 系列：别名与主名等价，可直接传给接口
NANO_BANANA_2_MODELS = {
    "nano-banana-2",
    "nano-banana-2-ext",
    "gemini-3.1-flash-image-preview",
    "gemini-3.1-flash-image-preview-official",
}
# 官方版（等价别名 nano-banana-2）不允许 official_fallback
NANO_BANANA_2_OFFICIAL = {
    "nano-banana-2",
    "gemini-3.1-flash-image-preview-official",
}
# nano-banana-2.1 系列：与 nano-banana-2（Gemini 3.1 Flash Image）是不同模型，模型名不能互换。
# 官方版按 token 计费、n 支持 1~4；Ext 版按张计费、n 只能为 1，可 official_fallback 兜底官方版。
# 仅支持 1K/2K/4K（无 0.5K），不支持 Google 搜索增强。
NANO_BANANA_21_MODELS = {
    "gemini-nano-banana-2.1",
    "gemini-nano-banana-2.1-ext",
}
NANO_BANANA_21_OFFICIAL = {"gemini-nano-banana-2.1"}
# Seedream 5.0 Pro：单图模型，支持档位/比例/精确像素，任务完成状态为 success
SEEDREAM_MODELS = {"seedream-5-0-pro", "seedream-5.0-pro"}
MODEL_CHOICES = ["gpt-image-2", "gpt-image-2.5-ext", *sorted(NANO_BANANA_2_MODELS),
                 *sorted(NANO_BANANA_21_MODELS), *sorted(SEEDREAM_MODELS)]

# 出图后需要 BM3D 降噪后处理的模型（RGB 三通道分别降噪，σ=20/255）
DENOISE_MODELS = NANO_BANANA_2_MODELS | NANO_BANANA_21_MODELS | SEEDREAM_MODELS
DENOISE_STRENGTH = 20
SKILL_DIR = Path(__file__).resolve().parent.parent
DENOISE_SCRIPT = SKILL_DIR / "scripts" / "denoise_bm3d.py"
VENV_PYTHON = SKILL_DIR / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def log(message: str) -> None:
    """输出进度信息到 stderr，保持 stdout 只含最终图片路径。"""
    print(message, file=sys.stderr, flush=True)


def resolve_api_key() -> str | None:
    """按 环境变量 -> api_key 文件 的顺序解析 API Key。"""
    key = (os.environ.get("APIMART_API_KEY") or "").strip()
    if key:
        return key
    for path in (KEY_FILE, KEY_FILE_ALT):
        try:
            if path.is_file():
                key = path.read_text(encoding="utf-8").strip()
                if key:
                    return key
        except OSError:
            continue
    return None


def windows_system_proxy() -> str | None:
    """读取 Windows 系统代理（HTTPS_PROXY 未设置时的兜底）。"""
    if os.name != "nt":
        return None
    try:
        import winreg  # type: ignore[import-not-found]
    except ImportError:  # pragma: no cover - 仅在非 Windows 上发生
        return None
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Internet Settings",
        ) as handle:
            enabled, _ = winreg.QueryValueEx(handle, "ProxyEnable")
            if not enabled:
                return None
            server, _ = winreg.QueryValueEx(handle, "ProxyServer")
    except OSError:
        return None
    server = str(server or "").strip()
    if not server:
        return None
    # 形如 "http=1.2.3.4:8080;https=1.2.3.4:8080" 或 "1.2.3.4:8080"
    if "=" in server:
        entries = {}
        for part in server.split(";"):
            if "=" in part:
                scheme, _, value = part.partition("=")
                entries[scheme.strip().lower()] = value.strip()
        server = entries.get("https") or entries.get("http") or ""
    if not server:
        return None
    if not server.startswith(("http://", "https://", "socks")):
        server = "http://" + server
    return server


class ApiError(RuntimeError):
    """HTTP 层错误（附带响应体，便于排查 400/401/402/429）。"""


def _http_request(
    url: str,
    method: str,
    headers: dict[str, str],
    body: bytes | None,
    proxy: str | None,
    timeout: float,
) -> tuple[int, bytes]:
    """发送一次请求，返回 (状态码, 响应体)。

    直接使用 http.client 而不是 urllib，是为了让请求头保持原始大小写
    （urllib 会用 str.capitalize() 改写成 X-apimart-response-version 这种形式）。
    """
    parts = urllib.parse.urlsplit(url)
    host = parts.hostname or ""
    port = parts.port or (443 if parts.scheme == "https" else 80)
    target = urllib.parse.urlunsplit(("", "", parts.path or "/", parts.query, ""))
    connection: http.client.HTTPConnection
    if proxy:
        proxy_parts = urllib.parse.urlsplit(proxy)
        proxy_host = proxy_parts.hostname or ""
        proxy_port = proxy_parts.port or (443 if proxy_parts.scheme == "https" else 80)
        if parts.scheme == "https":
            connection = http.client.HTTPSConnection(proxy_host, proxy_port, timeout=timeout)
            connection.set_tunnel(host, port)
        else:
            connection = http.client.HTTPConnection(proxy_host, proxy_port, timeout=timeout)
            target = url
    elif parts.scheme == "https":
        connection = http.client.HTTPSConnection(host, port, timeout=timeout)
    else:
        connection = http.client.HTTPConnection(host, port, timeout=timeout)

    sent = set()
    try:
        connection.putrequest(method, target)
        for name, value in headers.items():
            lowered = name.lower()
            if lowered in ("host", "content-length"):
                continue
            connection.putheader(name, value)
            sent.add(lowered)
        if body is not None and "content-length" not in sent:
            connection.putheader("Content-Length", str(len(body)))
        connection.endheaders(body)
        response = connection.getresponse()
        payload = response.read()
        if response.status >= 400:
            detail = payload.decode("utf-8", errors="replace")
            raise ApiError(f"HTTP {response.status} {response.reason}: {detail}")
        return response.status, payload
    finally:
        connection.close()


def fetch_json(url: str, method: str, headers: dict[str, str], body: bytes | None, proxy: str | None, timeout: float) -> dict:
    """发送请求并把响应体解析为 JSON。"""
    try:
        _, payload = _http_request(url, method, headers, body, proxy, timeout)
    except urllib.error.HTTPError as error:  # pragma: no cover - 兼容旧路径
        detail = error.read().decode("utf-8", errors="replace")
        raise SystemExit(f"ERROR: 请求失败（HTTP {error.code}）：{detail or error.reason}") from error
    except OSError as error:
        raise SystemExit(f"ERROR: 请求失败（网络错误）：{error}") from error
    text = payload.decode("utf-8", errors="replace")
    try:
        data = json.loads(text)
    except json.JSONDecodeError as error:
        raise SystemExit(f"ERROR: 响应不是合法 JSON：{text}") from error
    if not isinstance(data, dict):
        raise SystemExit(f"ERROR: 响应格式异常：{text}")
    return data


def _open_stream(
    url: str,
    proxy: str | None,
    timeout: float,
    offset: int,
    accept_error: bool = False,
) -> tuple[http.client.HTTPConnection, http.client.HTTPResponse]:
    """建立下载连接并返回未读完的响应（调用方负责关闭连接）。"""
    parts = urllib.parse.urlsplit(url)
    host = parts.hostname or ""
    port = parts.port or (443 if parts.scheme == "https" else 80)
    target = urllib.parse.urlunsplit(("", "", parts.path or "/", parts.query, ""))
    connection: http.client.HTTPConnection
    if proxy:
        proxy_parts = urllib.parse.urlsplit(proxy)
        proxy_host = proxy_parts.hostname or ""
        proxy_port = proxy_parts.port or (443 if proxy_parts.scheme == "https" else 80)
        if parts.scheme == "https":
            connection = http.client.HTTPSConnection(proxy_host, proxy_port, timeout=timeout)
            connection.set_tunnel(host, port)
        else:
            connection = http.client.HTTPConnection(proxy_host, proxy_port, timeout=timeout)
            target = url
    elif parts.scheme == "https":
        connection = http.client.HTTPSConnection(host, port, timeout=timeout)
    else:
        connection = http.client.HTTPConnection(host, port, timeout=timeout)

    connection.putrequest("GET", target)
    connection.putheader("Accept", "image/*")
    connection.putheader("User-Agent", "gen_image.py/1.0")
    if offset:
        connection.putheader("Range", f"bytes={offset}-")
    connection.endheaders()
    response = connection.getresponse()
    if response.status >= 400 and not accept_error:
        connection.close()
        raise RuntimeError(f"HTTP {response.status} {response.reason}")
    return connection, response


def _content_total(response: http.client.HTTPResponse, offset: int) -> int | None:
    """从 Content-Range / Content-Length 推断文件总大小。"""
    content_range = response.getheader("Content-Range")
    if content_range and "/" in content_range:
        tail = content_range.rsplit("/", 1)[-1].strip()
        if tail.isdigit():
            return int(tail)
        return None
    length = response.getheader("Content-Length")
    if length and length.isdigit():
        return offset + int(length)
    return None


def download_to_file(url: str, outfile: Path, proxy: str | None, timeout: float, attempts: int = 5) -> Path:
    """下载图片到 outfile：流式写入 + 断点续传 + 重试。

    结果图 URL 会过期，且大图经代理下载容易被中断（IncompleteRead），
    因此按块写盘并在续传时带上 Range，尽力保证已生成的结果不白丢。
    """
    outfile.parent.mkdir(parents=True, exist_ok=True)
    part = outfile.with_name(outfile.name + ".part")
    total: int | None = None
    last_error: Exception | None = None

    for attempt in range(1, attempts + 1):
        have = part.stat().st_size if part.exists() else 0
        if total is not None and have >= total:
            break
        connection = None
        response = None
        try:
            connection, response = _open_stream(url, proxy, timeout, have)
            if total is None:
                total = _content_total(response, have)
            # 服务器忽略 Range 时返回 200，必须从头重写
            if have and response.status != 206:
                have = 0
            mode = "ab" if have else "wb"
            with open(part, mode) as handle:
                while True:
                    chunk = response.read(1 << 16)
                    if not chunk:
                        break
                    handle.write(chunk)
        except Exception as error:  # noqa: BLE001 - 任何网络/IO 异常都重试
            last_error = error
            log(f"  下载中断（第 {attempt}/{attempts} 次）：{type(error).__name__}: {error}")
        finally:
            if connection is not None:
                connection.close()
        size = part.stat().st_size if part.exists() else 0
        if total is not None and size >= total:
            break
        if attempt < attempts:
            time.sleep(min(2 * attempt, 5))

    size = part.stat().st_size if part.exists() else 0
    if total is None or size < total:
        raise RuntimeError(f"下载不完整（{size}/{total if total is not None else '未知'} 字节）"
                           + (f"，最后错误：{last_error}" if last_error else ""))
    part.replace(outfile)
    return outfile


def first_match(pattern: str, text: str) -> str | None:
    """返回正则第一个捕获组的内容。"""
    match = re.search(pattern, text, re.DOTALL)
    return match.group(1) if match else None


def encode_reference(ref: str) -> str:
    """本地路径转 data URL，公网 URL 原样返回。"""
    path = Path(ref)
    if path.is_file():
        mime = mimetypes.guess_type(path.name)[0] or "image/png"
        data = base64.b64encode(path.read_bytes()).decode("ascii")
        return f"data:{mime};base64,{data}"
    return ref


def normalize_resolution(model: str, resolution: str) -> str:
    """nano-banana-2（0.5K/1K/2K/4K）、nano-banana-2.1（1K/2K/4K）与 seedream（1K/1.5K/2K）的分辨率统一成大写形式。"""
    if model in NANO_BANANA_2_MODELS and re.fullmatch(r"(?i)0\.5k|1k|2k|4k", resolution.strip()):
        return resolution.strip().upper()
    if model in NANO_BANANA_21_MODELS and re.fullmatch(r"(?i)1k|2k|4k", resolution.strip()):
        return resolution.strip().upper()
    if model in SEEDREAM_MODELS and re.fullmatch(r"(?i)1k|1\.5k|2k", resolution.strip()):
        return resolution.strip().upper()
    return resolution


def submit_task(
    proxy: str | None,
    api_key: str,
    model: str,
    version: str,
    n: int,
    prompt: str,
    size: str,
    resolution: str,
    references: list[str],
    google_search: bool = False,
    google_image_search: bool = False,
    official_fallback: bool = False,
    output_format: str = "jpeg",
    watermark: bool = False,
    transparent: bool = False,
) -> str:
    """提交生图任务并返回 task_id。"""
    payload: dict[str, object] = {
        "model": model,
        "prompt": prompt,
        "n": n,
        "size": size,
        "resolution": normalize_resolution(model, resolution),
    }
    if model == "gpt-image-2.5-ext":
        payload["version"] = version
    if model in NANO_BANANA_2_MODELS:
        if google_search:
            payload["google_search"] = True
        if google_image_search:
            payload["google_image_search"] = True
        if official_fallback:
            payload["official_fallback"] = True
    if model in NANO_BANANA_21_MODELS and official_fallback:
        payload["official_fallback"] = True
    if model in SEEDREAM_MODELS:
        payload["output_format"] = output_format
        if watermark:
            payload["watermark"] = True
        if transparent:
            payload["background"] = "transparent"
    if references:
        payload["image_urls"] = references

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    if model == "gpt-image-2.5-ext":
        headers["X-APIMart-Response-Version"] = "2026-07-27"
        headers["Idempotency-Key"] = str(uuid.uuid4())

    try:
        response = fetch_json(
            f"{API_BASE}/images/generations",
            "POST",
            headers,
            json.dumps(payload).encode("utf-8"),
            proxy,
            timeout=300,
        )
    except (ApiError, OSError) as error:
        raise SystemExit(f"ERROR: 提交失败：{error}") from error
    except SystemExit as error:
        raise SystemExit(f"ERROR: 提交失败：{error}") from error

    raw = json.dumps(response, ensure_ascii=False)
    # 旧格式: data[0].task_id；202 新格式: data.id
    task_id = first_match(r'"task_id"\s*:\s*"([^"]*)"', raw)
    if not task_id:
        task_id = first_match(r'"id"\s*:\s*"(task_[^"]*)"', raw)
    if not task_id:
        task_id = first_match(r'"id"\s*:\s*"([^"]*)"', raw)
    if not task_id:
        raise SystemExit(f"ERROR: 提交失败，响应：{raw}")
    return task_id


def poll_task(proxy: str | None, api_key: str, task_id: str) -> list[str]:
    """轮询任务直到完成，返回图片 URL 列表。"""
    last_response = ""
    for attempt in range(1, POLL_MAX_ATTEMPTS + 1):
        time.sleep(POLL_INTERVAL_SECONDS)
        try:
            response = fetch_json(
                f"{API_BASE}/tasks/{task_id}",
                "GET",
                {"Authorization": f"Bearer {api_key}", "Accept": "application/json"},
                None,
                proxy,
                timeout=120,
            )
        except SystemExit as error:
            log(f"  轮询网络异常，重试中 ({attempt}/{POLL_MAX_ATTEMPTS})：{error}")
            continue
        last_response = json.dumps(response, ensure_ascii=False)
        status = first_match(r'"status"\s*:\s*"([^"]*)"', last_response) or "unknown"
        if status in ("completed", "success"):  # seedream 完成状态为 success
            urls = re.findall(r'https?://[^"\s\\]+', last_response)
            if urls:
                return urls
            raise SystemExit(f"ERROR: 任务完成但未解析到图片 URL：{last_response}")
        if status in ("failed", "cancelled"):
            raise SystemExit(f"ERROR: 任务失败：{last_response}")
        log(f"  状态: {status} ({attempt}/{POLL_MAX_ATTEMPTS})")
    raise SystemExit(f"ERROR: 等待超时。最后响应：{last_response}")


def download(proxy: str | None, url: str, outdir: Path, model: str, stamp: str, index: int,
             multiple: bool, ext: str = "png") -> Path:
    """下载单张图片（流式 + 续传 + 重试），失败时抛出异常。"""
    name = f"{model}_{stamp}_{index}.{ext}" if multiple else f"{model}_{stamp}.{ext}"
    return download_to_file(url, outdir / name, proxy, timeout=300)


def denoise(path: Path) -> bool:
    """BM3D 降噪后处理（调用 .venv 中的 denoise_bm3d.py，σ=20/255）。

    依赖缺失或降噪失败时保留原图并告警，不影响主流程。
    """
    if not VENV_PYTHON.is_file():
        log(f"  跳过降噪：未找到 {VENV_PYTHON}（需先 python -m venv .venv && pip install bm3d pillow numpy）")
        return False
    try:
        result = subprocess.run(
            [str(VENV_PYTHON), str(DENOISE_SCRIPT), "--strength", str(DENOISE_STRENGTH), str(path)],
            capture_output=True, text=True, timeout=600,
        )
    except Exception as error:  # noqa: BLE001 - 后处理失败保留原图
        log(f"  降噪失败（保留原图）：{type(error).__name__}: {error}")
        return False
    if result.returncode != 0:
        log(f"  降噪失败（保留原图）：{result.stderr.strip()}")
        return False
    log(f"  已降噪（BM3D，RGB 分通道，σ={DENOISE_STRENGTH}/255）")
    return True


def parse_args(argv: list[str]) -> argparse.Namespace:
    """解析命令行参数（选项在前，位置参数在后）。"""
    parser = argparse.ArgumentParser(add_help=True, description="apimart.ai 生图")
    parser.add_argument("--model", default="gpt-image-2", choices=MODEL_CHOICES)
    parser.add_argument("--version", dest="version", default="flare", choices=["flare", "sunburst"])
    parser.add_argument("--n", type=int, default=1)
    parser.add_argument("--google-search", action="store_true",
                        help="nano-banana-2：启用 Google 文字搜索增强")
    parser.add_argument("--google-image-search", action="store_true",
                        help="nano-banana-2：启用 Google 图片搜索增强（需配合 --google-search）")
    parser.add_argument("--official-fallback", action="store_true",
                        help="nano-banana-2-ext / gemini-nano-banana-2.1-ext：失败时兜底官方版")
    parser.add_argument("--output-format", default="jpeg", choices=["jpeg", "png"],
                        help="seedream-5-0-pro：输出格式，默认 jpeg")
    parser.add_argument("--watermark", action="store_true",
                        help="seedream-5-0-pro：添加 AI generated 水印")
    parser.add_argument("--transparent", action="store_true",
                        help="seedream-5-0-pro：透明背景（需恰好 1 张带透明通道的参考图，且 --output-format png）")
    parser.add_argument("--no-denoise", action="store_true",
                        help="跳过 BM3D 降噪后处理（nano-banana-2 / nano-banana-2.1 / seedream-5-0-pro 默认启用）")
    parser.add_argument("prompt", help="提示词")
    parser.add_argument("size", nargs="?", default="1:1")
    parser.add_argument("resolution", nargs="?", default="1k")
    parser.add_argument("outdir", nargs="?", default=".")
    parser.add_argument("references", nargs="*", help="参考图 URL 或本地路径")
    args = parser.parse_args(argv)
    is_nano = args.model in NANO_BANANA_2_MODELS
    is_nano21 = args.model in NANO_BANANA_21_MODELS
    is_seedream = args.model in SEEDREAM_MODELS
    if args.n < 1 or (args.model == "gpt-image-2" and args.n != 1):
        raise SystemExit("ERROR: --n 仅 gpt-image-2.5-ext 与 nano-banana-2.1 官方版支持 1~4，gpt-image-2 固定为 1")
    if args.model == "gpt-image-2.5-ext" and args.n > 4:
        raise SystemExit("ERROR: --n 最大为 4")
    if is_nano:
        if args.n != 1:
            raise SystemExit("ERROR: nano-banana-2 的 --n 只能为 1")
        if args.google_image_search and not args.google_search:
            raise SystemExit("ERROR: --google-image-search 需配合 --google-search 一起使用")
        if args.official_fallback and args.model in NANO_BANANA_2_OFFICIAL:
            raise SystemExit("ERROR: 官方版（nano-banana-2）不能使用 --official-fallback")
    elif is_nano21:
        if args.google_search or args.google_image_search:
            raise SystemExit("ERROR: --google-search/--google-image-search 仅 nano-banana-2 支持，nano-banana-2.1 不支持")
        if args.resolution.strip().lower() in ("0.5k", "512"):
            raise SystemExit("ERROR: nano-banana-2.1 不支持 0.5K/512，仅支持 1K/2K/4K")
        if args.model in NANO_BANANA_21_OFFICIAL:
            if not 1 <= args.n <= 4:
                raise SystemExit("ERROR: gemini-nano-banana-2.1 的 --n 支持 1~4")
            if args.official_fallback:
                raise SystemExit("ERROR: 官方版（gemini-nano-banana-2.1）不能使用 --official-fallback")
        else:  # gemini-nano-banana-2.1-ext
            if args.n != 1:
                raise SystemExit("ERROR: gemini-nano-banana-2.1-ext 的 --n 只能为 1（需多张请用官方版）")
            if (args.resolution.strip().lower() in ("2k", "4k")
                    and re.fullmatch(r"(?i)1[:x]4|4[:x]1|1[:x]8|8[:x]1", args.size.strip())):
                raise SystemExit("ERROR: gemini-nano-banana-2.1-ext 的极端比例 1:4/4:1/1:8/8:1 仅 1K 支持，2K/4K 不支持")
    elif args.google_search or args.google_image_search or args.official_fallback:
        raise SystemExit("ERROR: --google-search/--google-image-search 仅 nano-banana-2 支持；--official-fallback 仅 nano-banana-2-ext / gemini-nano-banana-2.1-ext 支持")
    if is_seedream:
        if args.n != 1:
            raise SystemExit("ERROR: seedream-5-0-pro 是单图模型，--n 只能为 1")
        if len(args.references) > 10:
            raise SystemExit("ERROR: seedream-5-0-pro 参考图最多 10 张")
        if args.transparent:
            if args.output_format != "png":
                raise SystemExit("ERROR: --transparent 必须配合 --output-format png")
            if len(args.references) != 1:
                raise SystemExit("ERROR: --transparent 必须恰好传入 1 张带透明通道的参考图")
    elif (args.output_format != "jpeg" or args.watermark or args.transparent):
        raise SystemExit("ERROR: --output-format/--watermark/--transparent 仅 seedream-5-0-pro 支持")
    return args


def main(argv: list[str]) -> int:
    """命令行入口。"""
    args = parse_args(argv)

    api_key = resolve_api_key()
    if not api_key:
        log("ERROR: 未找到 API Key。请设置 APIMART_API_KEY 环境变量，或将 key 写入 "
            f"{KEY_FILE}（或 {KEY_FILE_ALT}）")
        return 1

    proxy = (os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy") or "").strip()
    proxy = proxy or windows_system_proxy()
    if proxy:
        log(f"使用代理: {proxy}")

    outdir = Path(args.outdir).expanduser()
    outdir.mkdir(parents=True, exist_ok=True)

    references = [encode_reference(ref) for ref in args.references if ref]
    log(
        f"提交生图任务... (model={args.model}, version={args.version}, "
        f"size={args.size}, resolution={args.resolution}, n={args.n})"
    )
    task_id = submit_task(
        proxy, api_key, args.model, args.version, args.n,
        args.prompt, args.size, args.resolution, references,
        google_search=args.google_search,
        google_image_search=args.google_image_search,
        official_fallback=args.official_fallback,
        output_format=args.output_format,
        watermark=args.watermark,
        transparent=args.transparent,
    )
    log(f"任务已提交: {task_id}，等待生成...")

    urls = poll_task(proxy, api_key, task_id)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    multiple = args.n > 1
    ext = args.output_format if args.model in SEEDREAM_MODELS else "png"

    failures = 0
    for index, url in enumerate(urls, start=1):
        try:
            outfile = download(proxy, url, outdir, args.model, stamp, index, multiple, ext)
            if args.model in DENOISE_MODELS and not args.no_denoise:
                denoise(outfile)
        except Exception as error:  # noqa: BLE001 - 单张失败不影响其余图片
            failures += 1
            log(f"ERROR: 下载失败: {url} ({error})")
            continue
        print(outfile.resolve(), flush=True)

    return 1 if failures and failures == len(urls) else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
