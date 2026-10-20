extends Node
## 场景管理框架 · autoload 单例「SceneManager」
## 职责:场景加载/卸载、UI Canvas 层级规划(见 ui_layers.gd)、预留记忆锚点层
## 验收标准:可加载/卸载至少 2 个场景,无内存泄漏(见演示与内存统计)

signal scene_changed(scene_name: String)

## 当前加载的场景实例(挂在本管理器下,作为子节点)
var current_scene: Node = null
var current_scene_name: String = ""

## 记忆锚点层预留:scene_name -> Array[Dictionary],每个场景独立的锚点物品列表
var _anchors_by_scene: Dictionary = {}


## 加载并切换到指定场景(内部会先卸载当前场景)
func change_scene(scene_path: String) -> void:
	_unload_current_scene()
	var packed: PackedScene = load(scene_path)
	if packed == null:
		push_error("[SceneManager] 无法加载场景: %s" % scene_path)
		return
	var inst: Node = packed.instantiate()
	current_scene = inst
	current_scene_name = _scene_name_from(scene_path)
	# 挂到本管理器下,入口壳场景(壳)保持常驻,演示/调度逻辑不丢失
	add_child(inst)
	# 重置该场景的锚点列表,由场景自身在 _ready 中重新注册
	_anchors_by_scene[current_scene_name] = []
	scene_changed.emit(current_scene_name)
	print("[SceneManager] 加载场景:「%s」(%s)" % [current_scene_name, scene_path])


## 卸载当前场景(free 实例并释放引用)。queue_free 在帧末回收,无泄漏则对象数稳定。
func unload_current_scene() -> void:
	_unload_current_scene()


func _unload_current_scene() -> void:
	if current_scene == null:
		return
	var name: String = current_scene_name
	var nodes_before := _count_nodes(current_scene)
	current_scene.queue_free()
	current_scene = null
	current_scene_name = ""
	_anchors_by_scene.erase(name)
	print("[SceneManager] 卸载场景:「%s」(卸载前节点数=%d)" % [name, nodes_before])


## 打印内存统计,用于观察加载/卸载是否无泄漏。
## 反复切换 A↔B,若对象数不持续增长,即为无内存泄漏。
func print_memory_stats() -> void:
	var scene_nodes := _count_nodes(current_scene)
	var mounted_scenes := _count_active_children()
	print("[SceneManager] 内存统计 | 当前场景=%s | 场景内节点数=%d | 活动挂载场景数=%d"
		% [current_scene_name, scene_nodes, mounted_scenes])


## ---- 记忆锚点层预留 ----
## 场景脚本在 _ready 中调用,把本场景独立的锚点物品列表注册给管理器。
func register_anchors(anchor_items: Array) -> void:
	if current_scene_name == "":
		return
	_anchors_by_scene[current_scene_name] = anchor_items
	print("[SceneManager][记忆锚点层] 场景「%s」注册锚点物品 %d 个"
		% [current_scene_name, anchor_items.size()])


## 查询某场景的锚点物品列表(留空取当前场景)。后续记忆锚点系统据此挂接。
func get_anchors(scene_name: String = "") -> Array:
	var key := scene_name if scene_name != "" else current_scene_name
	return _anchors_by_scene.get(key, [])


func _scene_name_from(scene_path: String) -> String:
	return scene_path.get_file().get_basename()


## 统计节点子树中的节点总数(用于观察场景卸载后是否残留)
func _count_nodes(node: Node) -> int:
	if node == null:
		return 0
	var count := 1
	for child in node.get_children():
		count += _count_nodes(child)
	return count


## 统计当前挂载的活动场景数(排除帧末待删除节点)
## 验证无泄漏:反复切换后该值应始终为 1,不增长。
func _count_active_children() -> int:
	var count := 0
	for child in get_children():
		if not child.is_queued_for_deletion():
			count += 1
	return count
