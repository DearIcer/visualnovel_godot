using Godot;
using System.Text.Json;

namespace 交互式文本.UI
{
	/// <summary>
	/// 开场 PV 场景控制器：挂在 scenes/Intro.tscn 根节点。
	/// WebView 全屏加载 webui/intro.html 播放 PV，收到 intro_done 消息（播完/点击跳过/文件缺失）后切换到主场景。
	/// </summary>
	public partial class IntroPlayer : Node
	{
		[Export] public string MainScenePath = "res://scenes/Main.tscn";

		private bool _finished = false;

		public override void _Ready()
		{
			var webView = GetNode<GodotObject>("WebView");
			webView.Connect("ipc_message", Callable.From<string>(OnIpcMessage));
		}

		private void OnIpcMessage(string message)
		{
			if (_finished)
				return;

			try
			{
				using var doc = JsonDocument.Parse(message);
				if (doc.RootElement.TryGetProperty("type", out var type) && type.GetString() == "intro_done")
				{
					_finished = true;
					GetTree().ChangeSceneToFile(MainScenePath);
				}
			}
			catch (JsonException ex)
			{
				GD.PushWarning($"开场 PV 消息解析失败: {ex.Message}");
			}
		}
	}
}
