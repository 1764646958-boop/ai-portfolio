# battle_scene.gd —— 战斗场景入口脚本（C）
#
# 战斗画面 = A 的 BattlePostController（90s 时间轴 + 30s 后摇）驱动
# assets/shaders/battle_post.gdshader 的全屏后处理。本脚本只做两件事：
#   1) 进场即 start_battle()，让时间轴跑起来；到 60s 处 controller 发出
#      phase_changed("phase3") → BattleChoiceUI 自动开最终抉择
#      （battle_choice_ui.gd:457，这是它唯一的正式驱动源，F5 只是调试热键）。
#   2) 场景内放一个返回街道的出口热点（interactable 节点），避免战斗场景成为死路。
#      注意这只是一个手动退出口，不参与 A 的后摇收尾逻辑——aftermath 的自动回流
#      该由时间轴驱动，属 A 的范围，这里不越界。
#
# 已知缺口（不是本场景能解的）：
#   battle_audio（W4.3）目前不是 autoload，controller 第 296 行
#   get_node_or_null("/root/battle_audio") 会拿到 null → 战斗音频四层静音。
#   补 autoload 是 B 的一行任务（见 W4/audio/战斗音频实现说明.md §5）。

extends Node2D

@onready var _controller: BattlePostController = $BattlePostController


func _ready() -> void:
	_controller.start_battle()
	print("[战斗场景] BattlePostController 已启动（0-30s 压迫 / 30-60s 隧道 / 60-90s 最终抉择 / 90s+ 后摇）")
