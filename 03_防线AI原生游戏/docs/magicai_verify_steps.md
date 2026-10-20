# MagicAI 代码验证 · 手把手清单（2D 版）

- **目的**：在 MagicAI（Godot 4.x）里跑通 2D 触发器原型：热点悬停→微光、点击→触发、出口→切换场景
- **预期结果**：鼠标悬停热点→图标变亮，点击→控制台输出 `触发：CF_PHOTO_01`，点出口→切到另一场景
- **耗时**：约 30-45 分钟（首次）

---

## 前置：打开项目

1. 启动 MagicAI → 项目管理器
2. **导入** → 选 `D:\文档\学习相关\腾讯AI原生游戏开发比赛\防线Dev\project.godot` → 打开

---

## 步骤 0：注册两个 Autoload（⚠️ 必须先做）

菜单 **项目 → 项目设置 → 全局（Globals）→ Autoload** 标签，依次添加：

| 路径 | 节点名 |
|---|---|
| `res://scripts/EventBus.gd` | `EventBus` |
| `res://scripts/scene_manager.gd` | `SceneManager` |

> 两个都要加，否则运行时 `EventBus` / `SceneManager` 报"未声明"。

---

## 步骤 1：创建场景 A（咖啡店）

1. **场景 → 新建场景** → 根节点选 **Node2D**，改名 `CoffeeShop`
2. （可选）加 **Sprite2D** 当背景占位（随便一张图或留空）
3. 加**记忆锚点热点**：
   - 新建 **Area2D**，改名 `Item_CF_PHOTO_01`
   - 把 `scripts/interactable.gd` 拖到它上面
   - 加子节点 **CollisionShape2D**（shape 选 **RectangleShape2D**，尺寸约 100×100）
   - 加子节点 **Sprite2D**（占位图标，可加载任意图片）
   - 选中 `Item_CF_PHOTO_01` 节点（Area2D），Inspector 里找到 **Object Id**（Godot 把 `object_id` 显示成这个名字），确认是 `CF_PHOTO_01`（脚本默认值已是它，一般不用改）
4. 加**出口热点**：
   - 新建 **Area2D**，改名 `Exit_To_Classroom`
   - 挂 `interactable.gd`
   - Inspector 勾选 **is_exit**，`target_scene` 填 `res://scenes/classroom.tscn`
   - 加 CollisionShape2D + Sprite2D
5. 保存到 `res://scenes/coffee_shop.tscn`

---

## 步骤 2：创建场景 B（教室）

1. 新建场景 → 根 **Node2D**，改名 `Classroom`
2. 加一个出口热点 `Exit_To_Coffee`，`target_scene` 填 `res://scenes/coffee_shop.tscn`
3. 保存到 `res://scenes/classroom.tscn`

---

## 步骤 3：设主场景 + 运行

1. 菜单 **项目 → 项目设置 → 应用程序 → 运行 → 主场景** → 选 `res://scenes/coffee_shop.tscn`
2. 按 **F6** 运行

---

## 步骤 4：验证清单（逐项打勾）

- [ ] 鼠标移到 `Item_CF_PHOTO_01` 上 → Sprite2D 变亮（微光）
- [ ] 点击它 → 控制台输出 **`触发：CF_PHOTO_01`**
- [ ] 鼠标移开 → 变亮消失
- [ ] 点击出口热点 → 切换到教室场景
- [ ] 教室场景点出口 → 切回咖啡店

---

## 常见坑排查表

| 症状 | 最可能原因 | 解决 |
|---|---|---|
| 运行报错 `EventBus`/`SceneManager` 未声明 | 步骤 0 的 Autoload 没加 | 回去加两个 Autoload |
| 鼠标移到热点没反应 | 热点缺 CollisionShape2D | 加 CollisionShape2D（RectangleShape2D） |
| 点击热点没输出 | 热点没挂 interactable.gd / object_id 空 | 挂脚本、填 object_id |
| 微光不亮 | 热点缺 Sprite2D 子节点 | 加 Sprite2D（任何图片） |
| 点出口没切换 | is_exit 没勾 / target_scene 路径错 | 勾 is_exit、核对路径 `res://scenes/classroom.tscn` |
| 切换时报错 "Can't load" | target_scene 拼写/大小写错 | 确认文件已保存且路径完全一致 |

---

## 成功后要做的

1. 截图控制台输出 `触发：CF_PHOTO_01` → 发群 @B（触发器接口已就绪）
2. commit（`git add -A && git commit -m "[触发器] 2D热点原型可运行"`）
