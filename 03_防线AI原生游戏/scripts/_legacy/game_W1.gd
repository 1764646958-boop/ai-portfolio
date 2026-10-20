extends Node
## 项目入口 · 空壳场景(常驻)
## 职责:启动 SceneManager 加载初始场景,并提供演示按键以验证
##      场景加载/卸载与无内存泄漏(验收标准)。
## 按键:
##   1    加载场景 1(记忆锚点原型)
##   2    加载场景 2(占位空场景)
##   空格  循环切换场景
## 每次切换后打印内存统计;反复切换若对象数不持续增长 → 无内存泄漏。

const SCENES: Array[String] = [
	"res://scenes/memory_anchor.tscn",
	"res://scenes/placeholder.tscn",
]
var _index: int = 0


func _ready() -> void:
	SceneManager.change_scene(SCENES[0])
	SceneManager.print_memory_stats()


func _unhandled_input(event: InputEvent) -> void:
	if event is InputEventKey and event.pressed and not event.echo:
		var changed := false
		match event.physical_keycode:
			KEY_1:
				_index = 0
				changed = true
			KEY_2:
				_index = 1
				changed = true
			KEY_SPACE:
				_index = (_index + 1) % SCENES.size()
				changed = true
		if changed:
			SceneManager.change_scene(SCENES[_index])
			SceneManager.print_memory_stats()
