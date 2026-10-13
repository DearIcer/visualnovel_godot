# 交互式文本 · Godot Visual Novel Engine

> 写一份 JSON，就能做一部视觉小说。
> A JSON-driven visual novel engine built on Godot 4.7 (.NET / C#) + Web UI.

**交互式文本** 是一个开源视觉小说（Galgame / AVG）引擎：剧情全部用 JSON 脚本描述，引擎负责演出、立绘、音乐、分支、存档与界面——你只需要专注写故事。

## 演示
- 🎮 示例 Demo **《红线缠心》**（病娇 × 微恐怖，28 场景 4 结局，约 1.5 小时流程）：见 `yandere` 分支，全部美术与音乐素材由内置 AI 管线产出

## 特性

- **📜 JSON 剧情驱动**：对话、旁白、选择支、变量、条件跳转，零代码写剧本
- **🎭 完整演出系统**：背景淡入淡出、立绘表情交叉淡化、位置移动、BGM 交叉淡入、音效与语音
- **🌿 分支与多结局**：`choice` 选择支 + `set`/`if` 变量条件，轻松实现多路线多结局
- **💾 存档 / 读档**：多存档位 + 场景自动存档，舞台与音频快照完整复现演出现场
- **🖥️ Web UI 界面层**：WebView 渲染的毛玻璃 UI（打字机 / 历史回顾 / 设置 / 鉴赏 / 右键菜单），换皮改主题不动一行 C#
- **🤖 AI 制作管线**：内置 `godot-vn-creator` 技能——剧本大纲 → AI 生成立绘与背景 → itch.io 免版税配乐 → 自动构建验证

## 快速开始

### 环境要求

- [Godot 4.7 .NET 版](https://godotengine.org/download) 与 [.NET 8 SDK](https://dotnet.microsoft.com/download)
- Windows 需 WebView2 Runtime（Win10/11 通常自带）；Android 端请使用 `master_Android` 分支

### 构建运行

```bash
git clone <仓库地址>
cd <项目目录>
dotnet build        # 编译 C# 脚本（等价于编辑器中的 Build）
```

然后用 Godot 编辑器打开项目并运行主场景：开场 PV → 标题画面 → 开始游戏。

### 三步做出你的游戏

**1. 写剧情** —— 编辑 `story/main.json`：

```json
{
  "characters": { "mio": { "displayName": "澪", "color": "#c0392b" } },
  "scenes": {
    "start": { "commands": [
      { "cmd": "bg",   "asset": "street_dusk", "fade": 1.0 },
      { "cmd": "bgm",  "action": "play", "track": "daily" },
      { "cmd": "show", "character": "mio", "emotion": "smile" },
      { "cmd": "say",  "character": "mio", "text": "明天见哦，透君。" }
    ] }
  }
}
```

**2. 放素材** —— 按约定命名放入 `assets/`：

```
assets/
├─ backgrounds/    street_dusk.png   ← bg 指令按文件名引用
├─ characters/mio/ smile.png         ← 角色id/表情名.png
├─ bgm/            daily.ogg         ← 支持 ogg / mp3 / wav
└─ se/             heartbeat.wav     ← 音效
```

**3. 运行** —— `dotnet build` 后在编辑器中运行，引擎会自动校验剧情引用的所有资源并在控制台提示缺失项。

## 剧情指令一览

| 指令 | 作用 | 主要参数 |
|---|---|---|
| `bg` | 切换背景 | `asset`、`color`、`fade` |
| `bgm` | 背景音乐 | `action`(play/crossfade/stop)、`track`、`fade`、`loop` |
| `se` / `voice` | 音效 / 语音 | `sound`、`volume`、`pitch` / `path` |
| `show` / `hide` / `move` | 立绘显示 / 隐藏 / 移动 | `character`、`position`(left/center/right)、`emotion`、`animation`、`duration` |
| `say` / `narrate` | 角色对话 / 旁白 | `character`、`text` |
| `choice` | 选择支 | `options`: [{`text`, `target`}] |
| `jump` | 跳转场景 | `target` |
| `set` / `if` | 变量 / 条件（不满足则跳过下一条指令） | `name`、`op`、`value` |
| `cg` / `music` / `vo_unlock` | 解锁鉴赏内容 | `id` |

> `show` 省略 `position` 时：已登场角色保持当前位置（仅切换表情），新登场角色落到 `defaultPosition`。切换场景时旧角色不会自动退场，需显式 `hide`。

## 仓库分支

| 分支 | 说明 |
|---|---|
| `master` | 桌面端引擎基座——干净的引擎 + Web UI，Fork 后从这里开始 |
| `master_Android` | Android 端引擎基座——同一套剧情 JSON，移动端直接运行 |
| `yandere` | 示例 Demo《红线缠心》完整内容：剧本、AI 素材、配乐与署名文件 |

## AI 制作管线（tools/skills）

仓库内置两个 AI 编码助手技能，配合支持技能的 AI CLI 使用：

- **`godot-vn-creator`**：视觉小说全流程制作流水线——剧本设计、AI 立绘/背景生成（绿幕抠图管线，模型可选）、itch.io 免版税配乐收集、音效合成、UI 主题化、构建验证
- **`apimart-image`**：apimart.ai 生图接口封装（文生图 / 图生图，多模型支持）

> 首次使用 AI 管线需配置 apimart API Key（详见 `tools/skills/apimart-image/SKILL.md`）。

> 立即体验：基于当前项目框架，编写一部视觉小说，阅读时长大概一个半小时，类型是病娇的略带点恐怖，女主的病娇程度我期望是比较高的。立绘场景需要你调用生图技能进行生成。当前项目基座的内容需要完全重写，不要保留。生图模型使用gemini-nano-banana-2.1。最后需要你去itch上找一些适合当前项目且免版税的音乐作为配乐。godot编辑器在D:\Github-WebProject\godot\bin\godot.windows.editor.x86_64.mono.console.exe。哦对，pv先用占位代替，这个不做先。

## 目录结构

```
project.godot          # Godot 工程配置
scenes/                # Intro.tscn（开场 PV）+ Main.tscn（主场景）
webui/                 # Web UI 前端（HTML/CSS/JS，无构建步骤）
scripts/               # C# 源码（Engine / Data / Audio / UI）
story/main.json        # 剧情脚本
assets/                # 背景 / 立绘 / BGM / SE 等资源
tools/skills/          # AI 制作管线技能
tools/story-editor/    # 剧情编辑器（纯前端，浏览器打开即用）
presentation/          # 项目介绍演示页与视频
addons/godot_wry/      # WebView GDExtension（驱动整个 Web UI 层）
```

## 第三方素材与署名

- 示例 Demo 的配乐来自 itch.io 免版税素材（Vacuous BGM / YUKARINOTI / D-Wheat Music），**发布作品时请按 `assets/bgm/CREDITS.md` 中的格式署名**
- 示例 Demo 的美术素材由 AI（gemini-nano-banana-2.1）生成，仅供学习参考
- 演示页 BGM：「chill guitar」— D-Wheat Music（itch.io，免费可用于个人与商业用途）

## License

引擎本体以 [MIT License](LICENSE) 开源。第三方素材按其各自许可使用（见上文署名要求）。
