# EventBus.gd —— 全局事件总线（Autoload 单例）
# 用途：解耦 C 的场景热点交互 与 B 的记忆锚点系统 / 氛围事件
# 配置：项目设置 → Autoload → 添加本文件，节点名 EventBus
#
# 2D 场景切换版：交互 = 鼠标悬停/点击热点
# （原 3D "靠近/离开"语义，在 2D 下映射为"鼠标悬停进入/移出"）
# 对应文档：docs/trigger_interface.md

extends Node

## 鼠标悬停进入热点（原"靠近"）—— B 监听 → 锚点微光
signal object_approached(object_id: String)

## 鼠标点击热点 —— B 监听 → 范本浮现 + 打字机
signal object_interacted(object_id: String)

## 鼠标移出热点（原"离开"）—— B 监听 → 微光消失
signal object_left(object_id: String)

## 场景切换完成（target_path 为目标场景路径）
signal scene_changed(target_path: String)

## 记忆锚点情感选择完成（B 的锚点 UI 发出 → 信任偏移系统 / 对话系统消费）
## object_id = 锚点热点标识；emotion = 玩家选择的情感基调（如 "平静的怀念"）
signal anchor_resolved(object_id: String, emotion: String)

## 氛围事件触发（AmbientDirector 发出 → A 接真实 Shader/音频、B 可记录日志）
## event_id = 事件 id（如 CF_001）；effect_type = photo_glitch/bgm_shift/…；
## data = 事件完整数据（含 name/scene/trigger_param，供效果实现读取）
signal ambient_triggered(event_id: String, effect_type: String, data: Dictionary)
