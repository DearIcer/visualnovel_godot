---
name: apimart-image
description: 使用 apimart.ai 的 gpt-image-2 / gpt-image-2.5-ext / nano-banana-2 / nano-banana-2.1 / seedream-5-0-pro 模型生成图片（文生图 / 图生图）。当用户要求生成、绘制、创作图片，或基于参考图改图/融图时使用。支持多种比例、最高 4k 分辨率、多图输出、Google 搜索增强、透明背景。
---

# apimart-image 生图

通过 apimart.ai 的生图接口异步生图：提交任务 → 轮询 → 下载图片。支持五个模型：

| 模型 | 说明 |
| --- | --- |
| `gpt-image-2`（默认） | 15 种比例 + 像素尺寸，`n` 只能为 1，参考图最多 15 张 |
| `gpt-image-2.5-ext` | 10 种比例（`1:1` `16:9` `9:16` `4:3` `3:4` `3:2` `2:3` `5:4` `4:5` `21:9`）+ `auto`，`n` 支持 1~4，参考图最多 16 张；`version` 选 `flare`（默认）或 `sunburst` |
| `nano-banana-2` | 14 种比例（含极端比例 `1:4` `4:1` `1:8` `8:1`）+ `auto`，`n` 只能为 1，参考图最多 14 张（单张 ≤10MB），分辨率支持 `0.5K`/`1K`/`2K`/`4K`，支持 Google 搜索增强 |
| `gemini-nano-banana-2.1` | nano-banana 2.1 系列（与 nano-banana-2 是不同模型，模型名不能互换）。官方版按 token 计费、`n` 支持 1~4；`-ext` 按张计费、`n` 只能为 1。14 种比例（同 nano-banana-2，ext 版极端比例仅 1K 支持），分辨率仅 `1K`/`2K`/`4K`（不支持 `0.5K`），参考图单张 ≤20MB（ext 合计 ≤50MB）、无固定张数上限，不支持 Google 搜索增强 |
| `seedream-5-0-pro` | 单图模型（`n` 只能为 1），参考图最多 10 张（单张 ≤30MB），分辨率档位 `1K`/`1.5K`/`2K`（1.5K 与 1K 同价，画质更好，优先用）或 `size` 精确像素；支持透明背景；**不使用图层拆分**；生成较慢（1K 约 90 秒，2K 约 160 秒） |

用户要求"多张图""2.5""flare/sunburst"时用 2.5 模型；要求"nano banana""banana2""搜索增强/联网生图""极端宽高比"时用 nano-banana-2；要求"nano banana 2.1""2.1"或"nano banana 一次多张"时用 gemini-nano-banana-2.1（多张选官方版 `--n 2~4`，按张估算费用选 `-ext`）；要求"seedream""透明背景""坐标/bbox 精准编辑"时用 seedream-5-0-pro。

nano-banana-2 的模型名：`nano-banana-2` 等价 `gemini-3.1-flash-image-preview-official`（官方版），`nano-banana-2-ext` 等价 `gemini-3.1-flash-image-preview`（标准版）；别名与主名可互换。seedream 亦接受别名 `seedream-5.0-pro`。nano-banana-2.1 与 Gemini 3.1 Flash Image（nano-banana-2）是不同模型，模型名不能作为别名互换，且 2.1 不支持 `0.5K` 分辨率。

## API Key 解析顺序

1. 环境变量 `APIMART_API_KEY`
2. 文件 `~/.kimi-code/skills/apimart-image/api_key`（纯文本，只放 key）
3. 或文件 `~/.dsh/skills/apimart-image/api_key`（DSH 安装位置，与 2 是同一份文件）
4. 都没有 → 向用户索要 key，征得同意后写入上述 `api_key` 文件

请求头：`Authorization: Bearer <key>`

脚本会自动读取系统代理（`HTTPS_PROXY` 未设置时）。

## 用法

直接运行配套脚本（推荐）。脚本有两个等价实现，按当前环境选一个：

| 环境 | 脚本 |
| --- | --- |
| Windows / 无 bash | `python ~/.kimi-code/skills/apimart-image/scripts/gen_image.py` |
| Linux / macOS / Git Bash | `bash ~/.kimi-code/skills/apimart-image/scripts/gen_image.sh` |

Windows 下 `~` 即 `C:\Users\<用户名>`；两个脚本行为一致（同一套参数、同样的代理与轮询逻辑）。
`.py` 只用 Python 3.9+ 标准库，无需安装任何依赖。

```bash
# Windows（推荐）：注意选项写在提示词之前
python ~/.kimi-code/skills/apimart-image/scripts/gen_image.py [选项] "提示词" [size] [resolution] [输出目录] [参考图URL或本地图片路径...]

# 类 Unix
bash ~/.kimi-code/skills/apimart-image/scripts/gen_image.sh [选项] "提示词" [size] [resolution] [输出目录] [参考图URL或本地图片路径...]
```

选项（放在提示词之前）：

- `--model gpt-image-2.5-ext`：使用 2.5 模型（默认 `gpt-image-2`）；nano-banana-2 用 `--model nano-banana-2`（官方版）或 `--model nano-banana-2-ext`（标准版）；nano-banana-2.1 用 `--model gemini-nano-banana-2.1`（官方版）或 `--model gemini-nano-banana-2.1-ext`（Ext 版）；seedream 用 `--model seedream-5-0-pro`
- `--version flare|sunburst`：2.5 模型的版本，默认 `flare`
- `--n 2`：生成张数，仅 2.5 模型与 nano-banana-2.1 官方版支持 1~4；`gpt-image-2`、nano-banana-2、gemini-nano-banana-2.1-ext 与 seedream 固定为 1
- `--google-search`：仅 nano-banana-2，启用 Google 文字搜索增强（适合需要真实信息的场景；2.1 不支持）
- `--google-image-search`：仅 nano-banana-2，追加 Google 图片搜索增强（需与 `--google-search` 同用）
- `--official-fallback`：仅 nano-banana-2-ext 与 gemini-nano-banana-2.1-ext，失败时用官方渠道/官方版兜底；官方版不可用
- `--output-format jpeg|png`：仅 seedream，输出格式，默认 `jpeg`
- `--watermark`：仅 seedream，右下角添加 "AI generated" 水印
- `--transparent`：仅 seedream，透明背景输出；必须恰好 1 张带透明通道的参考图且 `--output-format png`
- `--no-denoise`：跳过 BM3D 降噪后处理（见下）

> **约束：seedream 不使用图层拆分（`layer_decomposition`）**，脚本已移除该能力；需要拆图层时不要选 seedream。

## 出图后处理（BM3D 降噪）

`nano-banana-2`、`gemini-nano-banana-2.1` 与 `seedream-5-0-pro` 出图后，脚本会自动做 **BM3D 降噪：RGB 三通道分别降噪，强度 σ=20/255**（原地覆盖保存）。不需要时加 `--no-denoise`。

- 实现在 `scripts/denoise_bm3d.py`，依赖安装在 skill 目录的 `.venv`（bm3d / pillow / numpy）；缺失时脚本告警并保留原图，不影响主流程
- 重建依赖：`cd ~/.kimi-code/skills/apimart-image && python -m venv .venv && .venv/Scripts/python -m pip install bm3d pillow numpy`（pip 如需代理，设置 `HTTPS_PROXY` 环境变量）
- 可独立使用：`<.venv python> scripts/denoise_bm3d.py [--strength 20] 图片路径...`

参数：

- `提示词`：必填，中英文均可，建议详细描述（英文提示词主体更稳定）
- `size`：比例，默认 `1:1`。`gpt-image-2` 支持 `auto` `1:1` `3:2` `2:3` `4:3` `3:4` `5:4` `4:5` `16:9` `9:16` `2:1` `1:2` `3:1` `1:3` `21:9` `9:21` 及像素尺寸如 `1881x836`；2.5 模型支持 `auto` `1:1` `16:9` `9:16` `4:3` `3:4` `3:2` `2:3` `5:4` `4:5` `21:9`；nano-banana-2 在 2.5 的基础上额外支持 `1:4` `4:1` `1:8` `8:1`；nano-banana-2.1 比例与 nano-banana-2 相同（兼容 `16x9` 写法），但 ext 版 `1:4` `4:1` `1:8` `8:1` 仅 `1K` 支持，`2K`/`4K` 只有其余 10 种；seedream 支持 `auto` `1:1` `4:3` `3:4` `16:9` `9:16` `3:2` `2:3` `2:1` `1:2` `21:9`、档位关键字（`1K`/`1.5K`/`2K`，模型自定比例）及精确像素如 `2048x1024`（总像素须在 [921600, 4624220]，宽高比 [1/16, 16]，此时 resolution 被忽略）
- `resolution`：`1k`（默认）/ `2k` / `4k`；nano-banana-2 额外支持 `0.5K`（低分辨率预览）；nano-banana-2.1 仅支持 `1K`/`2K`/`4K`（传 `0.5K` 会 400，脚本会直接拦截）；seedream 仅支持 `1K`/`1.5K`/`2K`（1.5K 与 1K 同价画质更好，无特殊理由优先 `1.5K`），传 `4k` 会 400
- `输出目录`：默认当前目录
- 参考图：可选（gpt-image-2 最多 15 张，2.5 最多 16 张，nano-banana-2 最多 14 张且单张 ≤10MB，nano-banana-2.1 无固定张数上限、单张 ≤20MB（ext 合计 ≤50MB），seedream 最多 10 张且单张 ≤30MB）；本地路径会自动转 base64，公网 URL 原样传入，可混填。传了参考图即图生图模式

示例：

```bash
# 文生图，16:9 2K（Windows）
python ~/.kimi-code/skills/apimart-image/scripts/gen_image.py "一只橘猫坐在窗台上看夕阳，水彩画风格" "16:9" "2k"

# 图生图：本地图片转水彩风
python ~/.kimi-code/skills/apimart-image/scripts/gen_image.py "把这张照片变成水彩画风格" "1:1" "1k" ./out ./photo.jpg

# 2.5 模型，sunburst 版本，一次出 2 张
python ~/.kimi-code/skills/apimart-image/scripts/gen_image.py --model gpt-image-2.5-ext --version sunburst --n 2 "极简产品海报" "16:9" "2K" ./out

# nano-banana-2，2K 宽屏
python ~/.kimi-code/skills/apimart-image/scripts/gen_image.py --model nano-banana-2 "赛博朋克风格的城市夜景，霓虹灯闪烁" "16:9" "2K"

# nano-banana-2 + Google 搜索增强（需要真实信息的场景）
python ~/.kimi-code/skills/apimart-image/scripts/gen_image.py --model nano-banana-2 --google-search "今日上海外滩实景风格海报" "16:9" "2K"

# nano-banana-2.1 官方版，一次出 4 张（2.1 不支持 0.5K 与 Google 搜索增强）
python ~/.kimi-code/skills/apimart-image/scripts/gen_image.py --model gemini-nano-banana-2.1 --n 4 "赛博朋克风格的城市夜景，霓虹灯，雨后街道" "16:9" "2K"

# nano-banana-2.1-ext 图生图编辑（仅 1 张，按张计费）
python ~/.kimi-code/skills/apimart-image/scripts/gen_image.py --model gemini-nano-banana-2.1-ext "给画面里的猫戴上一顶红色毛线帽，其余保持不变" "auto" "1K" ./out ./cat.jpg

# seedream-5-0-pro，1.5K（与 1K 同价，画质更好）
python ~/.kimi-code/skills/apimart-image/scripts/gen_image.py --model seedream-5-0-pro "水墨风格的江南小镇，清晨薄雾" "16:9" "1.5K"

# seedream 坐标精准编辑：把图 1 主体放到图 2 指定位置（<bbox> 为归一化 0-1000 坐标）
python ~/.kimi-code/skills/apimart-image/scripts/gen_image.py --model seedream-5-0-pro "将图 1 <bbox>179 283 796 986</bbox> 的主体放到图 2 <bbox>118 331 933 871</bbox> 位置。" "auto" "2K" ./out ./a.png ./b.png
```

成功后脚本输出下载到本地的图片路径。用 ReadMediaFile 查看确认效果后再交付给用户。

## 手动调用（脚本不可用时）

1. 提交：`POST https://api.apimart.ai/v1/images/generations`，JSON body：
   `{"model":"gpt-image-2","prompt":"...","n":1,"size":"16:9","resolution":"2k"}`，图生图加 `"image_urls":[...]`（URL 或 `data:image/png;base64,...`）。返回 `data[0].task_id`。
   2.5 模型：body 改为 `{"model":"gpt-image-2.5-ext","version":"flare",...,"n":1~4}`，并加请求头 `X-APIMart-Response-Version: 2026-07-27` 和 `Idempotency-Key: <uuid>`；返回 202，任务 ID 在 `data.id`。
   nano-banana-2：body 改为 `{"model":"nano-banana-2",...,"n":1}`，可选 `"google_search":true`、`"google_image_search":true`（需配合 google_search）、`"official_fallback":true`（仅标准版）；无需额外请求头，返回格式与 gpt-image-2 相同（`data[0].task_id`）。
   nano-banana-2.1：body 改为 `{"model":"gemini-nano-banana-2.1",...,"n":1~4}`（ext 版 `n` 只能为 1），可选 `"official_fallback":true`（仅 ext 版）；不支持 `google_search`/`google_image_search` 与 `0.5K`。提交与轮询格式与 gpt-image-2 相同（`data[0].task_id`）。
   seedream-5-0-pro：body 改为 `{"model":"seedream-5-0-pro",...,"n":1}`，可选 `"output_format":"png"`、`"watermark":true`、`"background":"transparent"`（需恰好 1 张透明参考图 + png 输出）；不使用 `layer_decomposition`。返回格式与 gpt-image-2 相同。其任务完成状态为 `success`（其他模型为 `completed`），脚本两者都认。
2. 轮询：`GET https://api.apimart.ai/v1/tasks/{task_id}`，每 5 秒一次直到 `data.status` 为 `completed`/`success` 或 `failed`/`cancelled`（通常 1 分钟内，最多等 10 分钟；seedream 较慢，1K 约 90 秒、2K 约 160 秒）。
3. 取图：图片 URL 在 `data.result.images[0].url[]`（多张时数组有多个元素），用 curl 全部下载保存。

## 注意事项

- 比例与分辨率组合决定实际像素（如 `16:9` + `2k` = 2048×1152，`4k` = 3840×2160）
- 参考图单张 ≤20M；不传 `size` 时输出尺寸跟随输入图
- `n`：gpt-image-2、nano-banana-2、gemini-nano-banana-2.1-ext 与 seedream-5-0-pro 固定为 1；gpt-image-2.5-ext 与 gemini-nano-banana-2.1（官方版）支持 1~4，按版本、分辨率和实际交付张数计费
- nano-banana-2：不同分辨率计费不同（4K 高于 1K）；`size` 为 `auto` 时文生图默认 `1:1` 或 `16:9`，图生图按上游返回比例为准，建议显式指定比例
- gemini-nano-banana-2.1：官方版按实际 token 用量计费（提交按分辨率档位与 `n` 预扣，完成后多退少补）；ext 版按分辨率档位单价 × 实际张数计费，宽高比不影响档位，开启 `official_fallback` 且实际用官方版完成时改按官方版 token 计费。不支持 `0.5K`（提交 400）；ext 版极端比例 `1:4` `4:1` `1:8` `8:1` 仅 1K 支持；`n` 大于 4 提交直接 400；任务失败全额退款
- seedream-5-0-pro：按输出实际像素分档计费（≤约 261 万像素 $0.045/张，超出 $0.09/张；1.5K 与 1K 同价）；第 1 张参考图免费，第 2 张起每张加收；提示词可用 `<point>x y</point>` / `<bbox>x1 y1 x2 y2</bbox>`（归一化 0-1000 坐标）精准定位编辑区域，或直接上传带手绘标记的图；**不支持也不使用图层拆分**
- 常见错误：401 key 无效；402 余额不足；429 频率限制；400 参数非法
- 结果图 URL 有过期时间（`expires_at`），生成后应及时下载；脚本下载走「流式写盘 + Range 断点续传 + 最多 5 次重试」，中途断流不会丢整张图。若最终仍失败，会明确报「下载不完整（已收/总字节）」并保留 `.part` 文件，此时应尽快用同一 URL 重新下载，URL 过期则需重新生成
- 网络：脚本优先用 `HTTPS_PROXY` 环境变量，未设置时自动读取 Windows 系统代理（当前机器需要代理才能访问 api.apimart.ai）
