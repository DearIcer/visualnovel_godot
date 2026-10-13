#!/usr/bin/env bash
# apimart.ai 生图脚本：提交任务 -> 轮询 -> 下载图片
# 支持 gpt-image-2（默认）、gpt-image-2.5-ext（flare / sunburst）、
# nano-banana-2（gemini-3.1-flash-image-preview 系列）、nano-banana-2.1 系列
# 与 seedream-5-0-pro
#
# 用法:
#   gen_image.sh [选项] "提示词" [size] [resolution] [输出目录] [参考图URL或本地路径...]
#
# 选项:
#   --model MODEL      gpt-image-2（默认）、gpt-image-2.5-ext、
#                      nano-banana-2（官方版）、nano-banana-2-ext（标准版）
#                      （也接受 gemini-3.1-flash-image-preview[-official] 主名）、
#                      gemini-nano-banana-2.1（2.1 官方版，n 支持 1~4）、
#                      gemini-nano-banana-2.1-ext（2.1 Ext 版，n 只能为 1）、
#                      seedream-5-0-pro（亦接受 seedream-5.0-pro）
#   --version VER      2.5 模型版本：flare（默认）或 sunburst
#   --n N              生成张数：仅 2.5 与 nano-banana-2.1 官方版支持 1~4；其余模型固定为 1
#   --google-search        nano-banana-2：启用 Google 文字搜索增强（2.1 不支持）
#   --google-image-search  nano-banana-2：启用 Google 图片搜索增强（需配合 --google-search）
#   --official-fallback    nano-banana-2-ext / gemini-nano-banana-2.1-ext：失败时兜底官方版
#                          （官方版不可用）
#   --output-format FMT    seedream-5-0-pro：输出格式 jpeg（默认）或 png
#   --watermark            seedream-5-0-pro：右下角添加 "AI generated" 水印
#   --transparent          seedream-5-0-pro：透明背景（需恰好 1 张带透明通道的参考图 + png 输出）
#   --no-denoise           跳过 BM3D 降噪后处理（nano-banana-2 / nano-banana-2.1 / seedream-5-0-pro
#                          默认启用，σ=20/255；依赖 .venv 中的 bm3d/pillow/numpy，缺失时告警并保留原图）
#
# 示例:
#   gen_image.sh "一只橘猫" 16:9 2k
#   gen_image.sh --model gpt-image-2.5-ext --version sunburst --n 2 "产品海报" 16:9 2K ./out a.png
#   gen_image.sh --model nano-banana-2 --google-search "今日上海外滩实景风格海报" 16:9 2K
#   gen_image.sh --model gemini-nano-banana-2.1 --n 4 "赛博朋克风格的城市夜景，霓虹灯" 16:9 2K
#   gen_image.sh --model seedream-5-0-pro "水墨风格的江南小镇" 16:9 1.5K ./out
set -euo pipefail

API_BASE="https://api.apimart.ai/v1"

is_nano_model() {
  case "$1" in
    nano-banana-2|nano-banana-2-ext|gemini-3.1-flash-image-preview|gemini-3.1-flash-image-preview-official) return 0 ;;
    *) return 1 ;;
  esac
}

is_nano_official() {
  case "$1" in
    nano-banana-2|gemini-3.1-flash-image-preview-official) return 0 ;;
    *) return 1 ;;
  esac
}

# nano-banana-2.1 系列：与 nano-banana-2 是不同模型（非别名），仅 1K/2K/4K，不支持 Google 搜索增强
is_nano21_model() {
  case "$1" in
    gemini-nano-banana-2.1|gemini-nano-banana-2.1-ext) return 0 ;;
    *) return 1 ;;
  esac
}

is_seedream_model() {
  case "$1" in
    seedream-5-0-pro|seedream-5.0-pro) return 0 ;;
    *) return 1 ;;
  esac
}

# --- 解析选项 ---
MODEL="gpt-image-2"
VERSION="flare"
N=1
GOOGLE_SEARCH=0
GOOGLE_IMAGE_SEARCH=0
OFFICIAL_FALLBACK=0
OUTPUT_FORMAT="jpeg"
WATERMARK=0
TRANSPARENT=0
NO_DENOISE=0
while [ $# -gt 0 ]; do
  case "$1" in
    --model) MODEL="$2"; shift 2 ;;
    --version) VERSION="$2"; shift 2 ;;
    --n) N="$2"; shift 2 ;;
    --google-search) GOOGLE_SEARCH=1; shift ;;
    --google-image-search) GOOGLE_IMAGE_SEARCH=1; shift ;;
    --official-fallback) OFFICIAL_FALLBACK=1; shift ;;
    --output-format) OUTPUT_FORMAT="$2"; shift 2 ;;
    --watermark) WATERMARK=1; shift ;;
    --transparent) TRANSPARENT=1; shift ;;
    --no-denoise) NO_DENOISE=1; shift ;;
    *) break ;;
  esac
done

if is_nano_model "$MODEL"; then
  [ "$N" = "1" ] || { echo "ERROR: nano-banana-2 的 --n 只能为 1" >&2; exit 1; }
  if [ "$GOOGLE_IMAGE_SEARCH" = "1" ] && [ "$GOOGLE_SEARCH" != "1" ]; then
    echo "ERROR: --google-image-search 需配合 --google-search 一起使用" >&2; exit 1
  fi
  if [ "$OFFICIAL_FALLBACK" = "1" ] && is_nano_official "$MODEL"; then
    echo "ERROR: 官方版（nano-banana-2）不能使用 --official-fallback" >&2; exit 1
  fi
elif ! is_nano21_model "$MODEL"; then
  if [ "$GOOGLE_SEARCH" = "1" ] || [ "$GOOGLE_IMAGE_SEARCH" = "1" ] || [ "$OFFICIAL_FALLBACK" = "1" ]; then
    echo "ERROR: --google-search/--google-image-search 仅 nano-banana-2 支持；--official-fallback 仅 nano-banana-2-ext / gemini-nano-banana-2.1-ext 支持" >&2
    exit 1
  fi
fi
if ! is_seedream_model "$MODEL"; then
  if [ "$OUTPUT_FORMAT" != "jpeg" ] || [ "$WATERMARK" = "1" ] || [ "$TRANSPARENT" = "1" ]; then
    echo "ERROR: --output-format/--watermark/--transparent 仅 seedream-5-0-pro 支持" >&2
    exit 1
  fi
fi

PROMPT="${1:?用法: gen_image.sh [--model 模型] [--version 版本] [--n 张数] \"提示词\" [size] [resolution] [输出目录] [参考图...]}"
SIZE="${2:-1:1}"
RESOLUTION="${3:-1k}"
OUTDIR="${4:-.}"
shift $(( $# >= 4 ? 4 : $# ))

# seedream-5-0-pro：依赖参考图数量的校验（此时 $@ 为参考图列表）
if is_seedream_model "$MODEL"; then
  [ "$N" = "1" ] || { echo "ERROR: seedream-5-0-pro 是单图模型，--n 只能为 1" >&2; exit 1; }
  [ $# -le 10 ] || { echo "ERROR: seedream-5-0-pro 参考图最多 10 张" >&2; exit 1; }
  if [ "$TRANSPARENT" = "1" ]; then
    [ "$OUTPUT_FORMAT" = "png" ] || { echo "ERROR: --transparent 必须配合 --output-format png" >&2; exit 1; }
    [ $# -eq 1 ] || { echo "ERROR: --transparent 必须恰好传入 1 张带透明通道的参考图" >&2; exit 1; }
  fi
fi

# nano-banana-2.1：依赖 size/resolution 的校验（此时位置参数已解析）
if is_nano21_model "$MODEL"; then
  if [ "$GOOGLE_SEARCH" = "1" ] || [ "$GOOGLE_IMAGE_SEARCH" = "1" ]; then
    echo "ERROR: --google-search/--google-image-search 仅 nano-banana-2 支持，nano-banana-2.1 不支持" >&2; exit 1
  fi
  case "${RESOLUTION,,}" in
    0.5k|512) echo "ERROR: nano-banana-2.1 不支持 0.5K/512，仅支持 1K/2K/4K" >&2; exit 1 ;;
  esac
  if [ "$MODEL" = "gemini-nano-banana-2.1" ]; then
    if [ "$N" -lt 1 ] || [ "$N" -gt 4 ]; then
      echo "ERROR: gemini-nano-banana-2.1 的 --n 支持 1~4" >&2; exit 1
    fi
    [ "$OFFICIAL_FALLBACK" = "0" ] || { echo "ERROR: 官方版（gemini-nano-banana-2.1）不能使用 --official-fallback" >&2; exit 1; }
  else
    [ "$N" = "1" ] || { echo "ERROR: gemini-nano-banana-2.1-ext 的 --n 只能为 1（需多张请用官方版）" >&2; exit 1; }
    case "${RESOLUTION,,}" in
      2k|4k)
        case "${SIZE,,}" in
          1:4|4:1|1:8|8:1|1x4|4x1|1x8|8x1)
            echo "ERROR: gemini-nano-banana-2.1-ext 的极端比例 1:4/4:1/1:8/8:1 仅 1K 支持，2K/4K 不支持" >&2; exit 1 ;;
        esac ;;
    esac
  fi
fi

# --- API Key ---
KEY="${APIMART_API_KEY:-}"
if [ -z "$KEY" ] && [ -f "$HOME/.kimi-code/skills/apimart-image/api_key" ]; then
  KEY="$(tr -d '[:space:]' < "$HOME/.kimi-code/skills/apimart-image/api_key")"
fi
if [ -z "$KEY" ]; then
  echo "ERROR: 未找到 API Key。请设置 APIMART_API_KEY 环境变量，或将 key 写入 ~/.kimi-code/skills/apimart-image/api_key" >&2
  exit 1
fi

# --- 代理：优先 HTTPS_PROXY 环境变量，否则自动读取 Windows 系统代理 ---
PROXY="${HTTPS_PROXY:-${https_proxy:-}}"
if [ -z "$PROXY" ] && command -v reg >/dev/null 2>&1; then
  REG_OUT="$(reg query 'HKCU\Software\Microsoft\Windows\CurrentVersion\Internet Settings' //v ProxyEnable 2>/dev/null || true)"
  if printf '%s' "$REG_OUT" | grep -q '0x1'; then
    SRV="$(reg query 'HKCU\Software\Microsoft\Windows\CurrentVersion\Internet Settings' //v ProxyServer 2>/dev/null | awk '/ProxyServer/{print $NF}')"
    [ -n "$SRV" ] && PROXY="http://${SRV}"
  fi
fi
CURL_PROXY=()
if [ -n "$PROXY" ]; then
  CURL_PROXY=(-x "$PROXY")
  echo "使用代理: $PROXY" >&2
fi

mkdir -p "$OUTDIR"

json_escape() {
  # 用 python 做 JSON 转义；没有 python 则退回 sed 基本转义
  if command -v python >/dev/null 2>&1; then
    python -c 'import json,sys; print(json.dumps(sys.stdin.read()))'
  else
    sed 's/\\/\\\\/g; s/"/\\"/g' | awk 'BEGIN{printf "\""} {printf "%s\\n", $0} END{printf "\""}'
  fi
}

gen_uuid() {
  if command -v python >/dev/null 2>&1; then
    python -c 'import uuid; print(uuid.uuid4())'
  elif [ -f /proc/sys/kernel/random/uuid ]; then
    cat /proc/sys/kernel/random/uuid
  else
    echo "$(date +%s%N)-$$-$RANDOM"
  fi
}

# --- 组装 image_urls ---
IMAGES_JSON=""
for ref in "$@"; do
  [ -z "$ref" ] && continue
  if [ -f "$ref" ]; then
    ext="${ref##*.}"
    case "${ext,,}" in
      png) mime="image/png" ;;
      jpg|jpeg) mime="image/jpeg" ;;
      webp) mime="image/webp" ;;
      gif) mime="image/gif" ;;
      *) mime="image/png" ;;
    esac
    b64="$(base64 -w 0 "$ref")"
    ref="data:${mime};base64,${b64}"
  fi
  esc="$(printf '%s' "$ref" | json_escape)"
  if [ -z "$IMAGES_JSON" ]; then
    IMAGES_JSON="$esc"
  else
    IMAGES_JSON="$IMAGES_JSON,$esc"
  fi
done

# --- 组装请求体与请求头 ---
# nano-banana-2（0.5K/1K/2K/4K）、nano-banana-2.1（1K/2K/4K）与 seedream（1K/1.5K/2K）的分辨率统一成大写形式
if is_nano_model "$MODEL"; then
  case "${RESOLUTION,,}" in
    0.5k|1k|2k|4k) RESOLUTION="${RESOLUTION^^}" ;;
  esac
elif is_nano21_model "$MODEL"; then
  case "${RESOLUTION,,}" in
    1k|2k|4k) RESOLUTION="${RESOLUTION^^}" ;;
  esac
elif is_seedream_model "$MODEL"; then
  case "${RESOLUTION,,}" in
    1k|1.5k|2k) RESOLUTION="${RESOLUTION^^}" ;;
  esac
fi
PROMPT_JSON="$(printf '%s' "$PROMPT" | json_escape)"
BODY="{\"model\":\"${MODEL}\",\"prompt\":${PROMPT_JSON},\"n\":${N},\"size\":\"${SIZE}\",\"resolution\":\"${RESOLUTION}\""
EXTRA_HEADERS=()
if [ "$MODEL" = "gpt-image-2.5-ext" ]; then
  BODY="{\"model\":\"${MODEL}\",\"version\":\"${VERSION}\",\"prompt\":${PROMPT_JSON},\"n\":${N},\"size\":\"${SIZE}\",\"resolution\":\"${RESOLUTION}\""
  EXTRA_HEADERS=(-H "X-APIMart-Response-Version: 2026-07-27" -H "Idempotency-Key: $(gen_uuid)")
fi
if is_nano_model "$MODEL"; then
  [ "$GOOGLE_SEARCH" = "1" ] && BODY="${BODY},\"google_search\":true"
  [ "$GOOGLE_IMAGE_SEARCH" = "1" ] && BODY="${BODY},\"google_image_search\":true"
  [ "$OFFICIAL_FALLBACK" = "1" ] && BODY="${BODY},\"official_fallback\":true"
fi
if is_nano21_model "$MODEL"; then
  [ "$OFFICIAL_FALLBACK" = "1" ] && BODY="${BODY},\"official_fallback\":true"
fi
if is_seedream_model "$MODEL"; then
  BODY="${BODY},\"output_format\":\"${OUTPUT_FORMAT}\""
  [ "$WATERMARK" = "1" ] && BODY="${BODY},\"watermark\":true"
  [ "$TRANSPARENT" = "1" ] && BODY="${BODY},\"background\":\"transparent\""
fi
if [ -n "$IMAGES_JSON" ]; then
  BODY="${BODY},\"image_urls\":[${IMAGES_JSON}]"
fi
BODY="${BODY}}"

# --- 提交任务 ---
echo "提交生图任务... (model=${MODEL}, version=${VERSION}, size=${SIZE}, resolution=${RESOLUTION}, n=${N})" >&2
RESP="$(curl -sS "${CURL_PROXY[@]}" -X POST "${API_BASE}/images/generations" \
  -H "Authorization: Bearer ${KEY}" \
  -H "Content-Type: application/json" \
  "${EXTRA_HEADERS[@]+"${EXTRA_HEADERS[@]}"}" \
  -d "$BODY" || true)"

# 旧格式: data[0].task_id；202 新格式: data.id
TASK_ID="$(printf '%s' "$RESP" | grep -o '"task_id"[[:space:]]*:[[:space:]]*"[^"]*"' | head -1 | sed 's/.*"\([^"]*\)"$/\1/' || true)"
if [ -z "$TASK_ID" ]; then
  TASK_ID="$(printf '%s' "$RESP" | grep -o '"id"[[:space:]]*:[[:space:]]*"task_[^"]*"' | head -1 | sed 's/.*"\(task_[^"]*\)"$/\1/' || true)"
fi
if [ -z "$TASK_ID" ]; then
  echo "ERROR: 提交失败，响应：$RESP" >&2
  exit 1
fi
echo "任务已提交: $TASK_ID，等待生成..." >&2

# --- 轮询（每 5 秒，最多 10 分钟）---
IMG_URLS=""
for i in $(seq 1 120); do
  sleep 5
  STATUS_RESP="$(curl -sS "${CURL_PROXY[@]}" "${API_BASE}/tasks/${TASK_ID}" -H "Authorization: Bearer ${KEY}" || true)"
  if [ -z "$STATUS_RESP" ]; then
    echo "  轮询网络异常，重试中 (${i}/120)" >&2
    continue
  fi
  STATUS="$(printf '%s' "$STATUS_RESP" | grep -o '"status"[[:space:]]*:[[:space:]]*"[^"]*"' | head -1 | sed 's/.*"\([^"]*\)"$/\1/' || true)"
  case "$STATUS" in
    completed|success)  # seedream 完成状态为 success
      IMG_URLS="$(printf '%s' "$STATUS_RESP" | grep -oE 'https?://[^"]+' || true)"
      break
      ;;
    failed|cancelled)
      echo "ERROR: 任务失败：$STATUS_RESP" >&2
      exit 1
      ;;
    *) echo "  状态: ${STATUS:-unknown} (${i}/120)" >&2 ;;
  esac
done

if [ -z "$IMG_URLS" ]; then
  echo "ERROR: 等待超时或未取得图片 URL。最后响应：$STATUS_RESP" >&2
  exit 1
fi

# --- 下载（可能多张）---
TS="$(date +%Y%m%d_%H%M%S)"
IDX=0
MULTIPLE=0
[ "$N" -gt 1 ] && MULTIPLE=1

# BM3D 降噪后处理（nano-banana-2 / nano-banana-2.1 / seedream-5-0-pro 默认启用，σ=20/255）
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_PY=""
for candidate in "$SCRIPT_DIR/../.venv/Scripts/python.exe" "$SCRIPT_DIR/../.venv/bin/python"; do
  [ -f "$candidate" ] && VENV_PY="$candidate" && break
done
needs_denoise() { is_nano_model "$MODEL" || is_nano21_model "$MODEL" || is_seedream_model "$MODEL"; }

printf '%s\n' "$IMG_URLS" | while IFS= read -r url; do
  [ -z "$url" ] && continue
  IDX=$((IDX + 1))
  EXT="png"
  is_seedream_model "$MODEL" && EXT="$OUTPUT_FORMAT"
  if [ "$MULTIPLE" = "1" ]; then
    OUTFILE="${OUTDIR%/}/${MODEL}_${TS}_${IDX}.${EXT}"
  else
    OUTFILE="${OUTDIR%/}/${MODEL}_${TS}.${EXT}"
  fi
  if curl -sS --fail --retry 3 "${CURL_PROXY[@]}" -o "$OUTFILE" "$url"; then
    if [ "$NO_DENOISE" != "1" ] && needs_denoise; then
      if [ -n "$VENV_PY" ]; then
        if "$VENV_PY" "$SCRIPT_DIR/denoise_bm3d.py" --strength 20 "$OUTFILE" >/dev/null; then
          echo "  已降噪（BM3D，RGB 分通道，σ=20/255）" >&2
        else
          echo "  降噪失败（保留原图）: $OUTFILE" >&2
        fi
      else
        echo "  跳过降噪：未找到 .venv（需先 python -m venv .venv 并安装 bm3d pillow numpy）" >&2
      fi
    fi
    echo "$OUTFILE"
  else
    rm -f "$OUTFILE"
    echo "ERROR: 下载失败: $url" >&2
  fi
done
