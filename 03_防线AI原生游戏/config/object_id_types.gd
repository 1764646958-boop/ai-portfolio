class_name ObjectIdTypes
## 记忆锚点 object_id 类型枚举
## 命名规范:object_id = 场景缩写_类型_序号 (例:CF_CAKE_01)
## 类型集合:C 集成决策清单 v0.1 冲突 #8 通过的方案 A
##  - 保留 (C 原有):PHOTO / DIARY / TICKET / SMS / MUSIC
##  - 扩容 (B 范本新增):CAKE / FOOD / ACC / FLOWER / MARK
##
## B 维护此枚举;C 已经在场景 tscn 里按此规范配置了 object_id。
## 任何类型变更请同步通知 C 的 interactable.gd 校验。

enum Type {
	PHOTO = 0,   ## 照片
	DIARY = 1,   ## 日记
	TICKET = 2,  ## 票根
	SMS = 3,     ## 短信草稿 / 手机消息
	MUSIC = 4,   ## 音乐播放器 / 录音
	## ---- B 范本扩容 (W2 集成决策 #8) ----
	CAKE = 10,   ## 蛋糕 / 甜点
	FOOD = 11,   ## 食物 / 饮品
	ACC = 12,    ## 饰品 (手链 / 项链 / 戒指)
	FLOWER = 13, ## 花 (玫瑰 / 针织花 / 任意花束)
	MARK = 14,   ## 地点标记 (公交站划痕 / 屋檐 / 城市地标)
	## ---- 记忆考古专用 ----
	MA_BRACELET = 20,
	MA_ROSE = 21,
	MA_FLOWER = 22,
}


## 场景缩写 (C 触发器接口文档 §三)
const SCENE_ABBREV := {
	"咖啡店": "CF",
	"教室": "CR",
	"街道": "ST",
	"公寓": "AP",
	"宿舍": "DM",
	"公园": "PK",
	"记忆考古": "MA",
}


## 校验 object_id 是否符合 场景缩写_类型_序号 命名规范
## scene_abbrev: 期望的 2 字母场景缩写 (如 "CF")
## 返回:bool (通过/不通过)
static func validate(object_id: String, scene_abbrev: String = "") -> bool:
	if scene_abbrev == "":
		return true
	if not object_id.begins_with(scene_abbrev + "_"):
		return false
	# 取 _ 后的第二段作类型
	var parts := object_id.split("_", false)
	if parts.size() < 2:
		return false
	var type_str := parts[1]
	var valid_types := ["PHOTO", "DIARY", "TICKET", "SMS", "MUSIC",
		"CAKE", "FOOD", "ACC", "FLOWER", "MARK",
		"MA_BRACELET", "MA_ROSE", "MA_FLOWER"]
	return type_str in valid_types