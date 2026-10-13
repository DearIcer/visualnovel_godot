---
name: godot-vn-creator
description: 基于 Godot 4.7 .NET 视觉小说引擎（交互式文本/红线缠心基座）从零制作一部完整视觉小说：剧本创作、AI 立绘与背景生成（绿幕抠图管线）、itch.io 免版税配乐收集、音效合成、UI 主题化、构建验证。当用户要求"制作/编写一部视觉小说""做一个 Galgame/AVG"或要替换现有 VN 项目的全部剧情与素材时使用。
---

# Godot 视觉小说制作流水线

把一个 Godot VN 引擎项目的内容层（剧情/美术/音乐/UI 主题）整体替换为一部全新作品。全程可交付：能跑、能玩、多结局、有署名合规的配乐。

## 前置条件

- 引擎基座：Godot 4.7 .NET 项目，含 `story/main.json` 剧情驱动、`assets/backgrounds|characters|bgm|se` 资源约定、WebView UI（webui/）、标题画面与主菜单。
- 生图通过 `apimart-image` 技能完成（用 Skill 工具调用加载最新用法）。**技能的实际安装路径以当前会话技能清单中给出的 Path 为准**（不同宿主可能是 `~/.kimi-code/skills/`、`~/.dsh/skills/` 或其他位置，不要硬编码）。
- **首次使用必须配置 apimart API Key**（`APIMART_API_KEY` 环境变量，或 apimart-image 技能目录下的 `api_key` 文件）。开工第一步先试生一张测试图：若报"未找到 API Key"或 401，**立即停下来明确提醒用户**——需要去 apimart.ai 注册账号、获取 key 并完成配置后才能继续，征得同意后可将 key 写入技能目录的 `api_key` 文件。同时该测试也验证了余额（402 = 余额不足，提醒用户充值）。
- 生图模型由用户选择；用户未指定时用 AskUserQuestion 询问（推荐 `gemini-nano-banana-2.1`）。
- 本 skill 自带三个脚本（在 `scripts/` 下）：`remove_bg.py`（绿幕抠图+裁边+统一高度）、`make_se.py`（合成音效）、`make_placeholders.py`（占位图）。运行它们需要带 pillow/numpy 的 Python，按以下顺序解析：
  1. apimart-image 技能目录下的 `.venv`（如 `<apimart-image技能目录>/.venv/Scripts/python.exe`，Windows）——它自带 pillow/numpy/bm3d；
  2. 若不存在，自建：`python -m venv <项目>/tools/asset-gen/.venv && <venv python> -m pip install pillow numpy`。

## 总流程（按序执行）

### 1. 摸清引擎约束

先读引擎代码确认契约，不要凭记忆写剧情。关键文件：`scripts/Engine/CommandRunner.cs`（指令集）、`VNCore.cs`（菜单 BGM 常量、标题背景路径、立绘缩放比例、资源校验）、`scripts/Audio/MusicChannel.cs`（BGM 路径与格式解析）。典型约定：

- 背景 `res://assets/backgrounds/{asset}.png`；立绘 `res://assets/characters/{id}/{emotion}.png`；BGM `assets/bgm/{track}.ogg`（引擎可能支持 ogg/mp3/wav 回退，先确认）；SE `assets/se/{sound}.wav`。
- 指令：bg/bgm/se/voice/show/hide/move/say/narrate/choice/jump/set/if/cg/music/vo_unlock。`show` 省略 position 时新登场角色落 defaultPosition；切场景旧角色不会自动退场，**必须显式 hide**。
- 立绘按高度缩放（如屏高 0.9 倍），所以立绘 PNG 必须**紧贴人物裁边**，否则比例会错。
- 运行时入口可能有主菜单（menu_start 才进剧情）；结局指令耗尽后自动回标题。

### 2. 剧本设计（先设计，再生图）

- 阅读时长换算：中文约 400~500 字/分钟纯阅读，加上打字机/点击/演出停顿，**1.5 小时 ≈ 2~2.5 万字**对白旁白。
- 先定：标题、角色表（id/显示名/颜色/默认站位/表情清单）、场景清单、背景清单、BGM 情绪清单、结局数量与分支变量。资产清单必须从剧本反推，宁少勿多。
- 结构建议：序章 → 3~5 个日常/铺垫章节 → 转折事件 → 真相揭露（含关键 choice 设置 path 变量）→ 结局分流（用 `if` + `jump` 链路由）。
- 写 JSON 时用 Python 随时校验：`json.load` + 检查所有 jump/choice 目标存在、引用的角色/表情/背景/音乐都有对应文件计划。**增量追加大段 JSON 容易弄坏括号，每加一两章就校验一次。**

### 3. 立绘生成（调用 apimart-image 技能，模型由用户选择）

**第一步永远是：用 Skill 工具正式调用 `apimart-image`，加载它的最新用法**（脚本路径、参数、各模型能力与定价以该技能文档为准，本 skill 不复述，避免过时）。

**模型选择：**
- 若用户已指定模型 → 严格使用用户指定的模型，子代理提示词里写死"只准用此模型"。
- 若用户未指定 → 用 AskUserQuestion 让用户选择，并给出建议（默认推荐 `gemini-nano-banana-2.1`：立绘一致性好、图生图差分稳定、1K/2K 同价约 $0.05/张）。给出选项时附各模型对本任务的适配度（参考 apimart-image 技能文档的模型表）。
- 注意模型能力差异：nano-banana 系**不支持透明输出** → 必须走绿幕抠图管线；`seedream-5-0-pro` 支持 `--transparent` 透明背景直出，若用户选它，立绘可跳过抠图（但仍需 autocrop 裁边统一高度，用 `remove_bg.py` 的裁边逻辑或 PIL 手动裁）。

**绿幕抠图管线（nano-banana 系等不透明输出模型）：**

1. 每个角色先生成「基础立绘」：全身、正面、中性表情，提示词写死外貌/服装/发型细节，结尾固定 `Isolated on a completely flat solid pure green background (hex #00FF00), no shadow, no props, no text.` 比例 2:3。
2. 用 `scripts/remove_bg.py 输入 输出` 抠图（色度键 + 去绿溢色 + 中值滤波 + autocrop + 统一 1800px 高）。抠完必须 ReadMediaFile 目检：全身完整、无绿边、背景透明。
3. 表情差分用图生图，参考图传基础立绘的 **raw 绿幕原图**，提示词：`Using the reference image, keep the exact same character, hairstyle, face, uniform, pose, framing, and the same flat solid pure green (#00FF00) background. Only change the facial expression to: <表情>. Full body still visible from head to toe. No text.` 这样一致性最好。
4. 病娇/黑化类表情关键词参考：`eyes have lost their highlights, faint shadow over upper face`（阴沉）、`sweet smile with wide dark highlight-less eyes, slight head tilt`（病娇笑）、`unhinged manic laughter, small pupils`（狂气）、少量血迹用 `a few small blood stains`（一般能过审，被拒就改 `faint red stains like smeared paint`）。
5. **并行策略**：每个角色一个后台子代理（基础图→差分要串行），背景图另开 1~2 个代理。子代理提示词里写死：模型名、完整命令模板、超时 300s、重试上限、抠图命令、交付路径清单、"遇到 402 立即停止并汇报"。

### 4. 背景与标题图

沿用用户选定的生图模型，比例 16:9，分辨率按模型档位选 2K（或等价档）。提示词统一前缀 `Anime visual novel background illustration, highly detailed, atmospheric lighting, no people, no characters, no text, no watermark.` + 场景描述。**下载后检查真实格式**——脚本可能落盘 JPEG 冒充 .png，Godot 认扩展名会出问题，用 PIL 转成真 PNG：`Image.open(x).convert('RGB').save(p)`。

### 5. 配乐（itch.io 免版税）

- 按情绪列清单（如 menu/daily/角色主题/unease/tension/sad），再去 itch.io 找 free/NYOP 且明确允许游戏使用的音乐包。已知好用的包：
  - Vacuous BGM《Horror Novel BGM Collection》系列（`vacuous2409.itch.io`，钢琴+大提琴恐怖，署名即可商用）
  - YUKARINOTI 的八音盒包（`megumi-ryu.itch.io`，诡异八音盒，署名 "Music: YUKARINOTI"）
  - D-Wheat Music《Free Background Music for Visual Novels》（日常向，个人/商用免费）
- **itch 免登录下载法**：GET 项目页 → 提取 `<meta name="csrf_token">` 和下载按钮的 `data-upload_id` → POST `https://<author>.itch.io/<slug>/file/<upload_id>?after_download_lightbox=true`（带 `X-CSRF-Token` 和 cookie）→ 返回 JSON 里的签名 URL **几十秒内过期，拿到立即下载**。
- 格式：WAV 太大就转 ogg。无 ffmpeg 时建 venv `pip install imageio-ffmpeg` 拿自带 ffmpeg：`-c:a libvorbis -q:a 5`。
- 必须在 `assets/bgm/CREDITS.md` 逐条记录：原曲名、作者、来源 URL、授权条款原文、建议署名文案。

### 6. 音效

恐怖/日常 VN 的心跳、闷响、手机震动等基础 SE 可以直接程序合成（`make_se.py`，numpy 生成 WAV），零版权风险，比现找素材快且安全。

### 7. UI 主题化

改 webui/index.html 的标题/副标题/标语、style.css 的 `:root` 主题变量（accent 配色契合题材）、VNCore 的菜单 BGM 常量、project.godot 的 `config/name`。**assembly_name 不要动**，避免破坏 C# 程序集引用。PV/intro 若用户不要求就做占位。

### 8. 构建与验证

1. `dotnet build` 必须零错误。
2. Godot 编辑器无头导入：`<godot编辑器路径> --path <项目> --import --headless`，让新资源生成 .import。
3. 无头冒烟：`<godot> --path <项目> --headless scenes/Main.tscn --quit-after 240`，grep 输出中的"缺失/错误"——引擎的资源校验会打印所有剧情引用缺失。（WebView 在 headless 下不创建属正常，那条 WARNING 可忽略；"Extension marked as reloadable" 的 ERROR 是 godot_wry 的已知噪音，也可忽略。）
4. 全量资源自检：Python 遍历剧情 JSON 引用的所有 bg/立绘/BGM/SE，确认文件存在且是真图（可用文件大小阈值识别占位图残留）。

## 经验坑位

- apimart 出图失败常见码：401 key 无效、402 余额不足（nano-banana-2.1 的 1K/2K 同价，降分辨率不省钱；其他模型的计费档位以 apimart-image 技能文档为准）、429 限流、内容安全审核（含蓄化描述重试）。
- 生成任务 URL 有有效期，子代理中断后 raw 半成品可能还能复用，续跑前先盘点再决定重生成。
- 缺资产时不要干等充值：先用 `make_placeholders.py` 生成带中文标注的占位图把所有坑填满，保证游戏随时可跑，真图到位后覆盖即可。
- 大项目素材目录（tools/ 下的中间产物）加 `.gdignore`，避免 Godot 重复扫描导入。
- 子代理批量生图要在提示词里明确"只准用指定模型"，否则它们可能自作主张换默认模型。

## 剧本质量要点（病娇/恐怖类示例）

- 病娇浓度靠「精确到变态的细节」体现：对方生活数据的量化记录（秒、毫米、次数）、温柔语气说恐怖内容、"我不生气哦"式反差。
- 恐怖感靠日常异化：房间被打扫、物品被归还、所有出口都合法但无解。
- 高浓度病娇需要可理解的创伤根源（被抛弃的玄关、被处死的宠物），否则角色只是疯子而非病娇。
- 多结局要覆盖光谱：沉沦（共犯）、崩坏（监禁）、毁灭（殉情）、救赎（真结局），真结局应要求玩家在关键节点选择"理解"而非"接受"。
