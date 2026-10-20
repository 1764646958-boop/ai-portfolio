# 三项视觉压迫 Shader 接入说明（W3.4）

> 交付物 W3.4 · 成员 A · 2026-08-29
> 新增文件（Godot 仓库 `assets/shaders/`）：
> - `vision_erosion.gdshader`（既有，W1 原型，本文件引用）
> - `color_grade.gdshader`（新增）
> - `screen_shake.gdshader`（新增）
> - `tunnel_vision.gdshader`（新增）
> 数值依据：`W3\battle\pressure_params.json`（v1 初稿，待 A+B 终稿）

---

## 1. 驱动参数 → pressure_params.json 映射表

| Shader | uniform | curves 键 | 默认值 | 驱动方式 |
|---|---|---|---|---|
| color_grade | `red_retain` | `red_retain` | 1.0 | 时间轴：1→0（每 5s -0.25，t=20 归零） |
| color_grade | `green_retain` | `green_retain` | 1.0 | 时间轴：t=25 前保持 1.0，25s 起每 5s -0.25（t=40 归零） |
| color_grade | `blue_retain` | `blue_retain` | 1.0 | 时间轴：1→0.95（t=15）→0.90（t=25）→0.80（t=50 保持） |
| color_grade | `posterize_amount` | `posterize_amount` | 0.0 | 时间轴：t=20 起 0→0.10→每 5s +0.05→0.50（t=60 保持） |
| color_grade | `posterize_levels` | `posterize_levels` | 16 | 恒定 |
| screen_shake | `shake_amount` | `shake_amount` | 0.0 | **事件驱动**：拖假碎片/被攻击置 0.03 → `lerp(shake, 0, 0.2)` 帧间衰减 |
| screen_shake | `shake_seed` | — | 0 | 事件驱动时按战斗编号取不同值（防抖动模式重复） |
| tunnel_vision | `tunnel_radius` | `tunnel_radius` | 0.05 | 时间轴：30s 起 0.20→每 5s -0.025→0.05（t=60 保持）；后摇 0.05→0.30 |
| tunnel_vision | `tunnel_softness` | `tunnel_softness` | 0.15 | 恒定 |
| tunnel_vision | `tunnel_color` | — | (0.01,0.02,0.06,1.0) | 恒定 |

> ⚠️ `tunnel_radius` 默认值 0.05 是**阶段三最终值**（预览用）；接入战斗系统后请从 0.20 开始驱动，避免开局即完全隧道化。

## 2. 单 Shader 挂载方式（Godot 4 / MagicAI 4.6.2）

### 2.1 通用步骤（三项相同）

1. 在战斗场景画面上层建一个 **ColorRect**，Anchors 四边铺满全屏（Layout → Full Rect）。
2. 给 ColorRect 新建 **ShaderMaterial**，把对应 `.gdshader` 内容贴入 shader 编辑器。
3. ColorRect 加 `mouse_filter = MOUSE_FILTER_IGNORE`（防挡 UI 点击）。
4. GDScript 用 `$ColorRect.material.set_shader_parameter("uniform名", 值)` 实时驱动。

### 2.2 color_grade / screen_shake（需屏幕纹理，额外注意）

- 二者采样 `SCREEN_TEXTURE`。Godot 4 的 canvas_item shader 通常自动处理屏幕拷贝；**若采样结果为空/画面错位**，在该 ColorRect 之前（树序上方）添加一个 **BackBufferCopy** 节点兜底（Godot 3 兼容做法，无副作用）。
- color_grade 为「滤镜」语义：**只允许存在一个**（全屏唯一，W4.4 合并版取代它后移除）。
- screen_shake 与 color_grade 采样的是同一张屏幕纹理，**不要**用两个 ColorRect 串行叠（二次采样会放大偏移/模糊）——最终以 W4.4 `battle_post.gdshader` 单 pass 合并版为准（§3）。

### 2.3 tunnel_vision（纯遮罩，无屏幕纹理）

- 与 `vision_erosion.gdshader` 同属「纯遮罩叠层」：**可同时叠用**，推荐渲染顺序：
  `vision_erosion（冷蓝全屏）→ tunnel_vision（近黑收口）→ color_grade（滤镜灰度）→ screen_shake（抖动）`
- 二者不带屏幕纹理，可独立使用，适合战斗以外的「记忆泄漏」小事件复用。

## 3. 单 pass 合并方案（W4.4 预告，非本次交付）

- **为什么合并**：screen texture 类 shader 每个 pass 都是一次全屏采样；4 个 ColorRect 串行 = 4 次读取 + 多次绘制。合并为单 pass `battle_post.gdshader` 后：
  - 只采样 1 次 `SCREEN_TEXTURE`；
  - erosion（纯计算）+ tunnel（纯计算）+ color_grade（采样后处理）+ shake（UV 偏移）一次完成；
  - 保留 `enable_erosion / enable_color_grade / enable_shake / enable_tunnel` 四开关（默认全开），便于按战斗编号只启用部分效果。
- 合并版 uniform **名与前文完全一致**（red_retain/green_retain/blue_retain/posterize_amount/posterize_levels/shake_amount/shake_seed/tunnel_radius/tunnel_softness/tunnel_color/erosion_progress/…），W4.4 的 `battle_post_controller.gd` 直接按 §1 映射表驱动，无需改名。
- 合并后在 `battle_post.gdshader` 内附带轻量 vignette（可选，遮蔽 shake 边缘拉伸）。

## 4. 画面抖动：为什么落地用 UV 偏移（替代选题报告的顶点位移）

| 方案 | 露底（四角黑边） | 与全屏屏 ColorRect 裁剪 | 多 pass 合并 | 结论 |
|---|---|---|---|---|
| 顶点位移 `VERTEX += offset` | 有（画面平移露下层） | 受 anchors/cfg 牵连，非 16:9 需额外对齐 | 与采样类效果可分但增加顶点步数 | 弃用 |
| UV 偏移（本实现） | 无（clamp 边缘拉伸，≤0.03 下几乎不可见） | 无（只改采样坐标） | 与 color_grade 同 pass 复用一次采样 | **采用** |

## 5. 性能预算

- 目标：**< 2 ms/帧**（1920×1080 ≈ 207 万像素；对标 W1 调查的 Godot 4 桌面 GL（Compatibility）全屏滤镜 0.5–1.5ms）。
- 本次 3 个独立 pass 合计：约 3 次屏幕纹理读取 + 少量 ALU；**合并单 pass 后（W4.4）预算降至 ~1 次采样 + ALU，< 2ms 达标**。
- 低端集显备注：保持全屏 ColorRect 数量 ≤ 2（未合并前），且关闭视口 HDR 可再省内存带宽。

## 6. 验收自查

- [x] 三个文件均已通过 Godot 4 gdshader 语法自查（canvas_item + uniform 声明带 hint_range/source_color）。
- [x] `color_grade`：hint_screen_texture 采样；posterize 用 `floor`（无 round 闪烁）；三通道保留用 `mix` + brightness dot（无分支）。
- [x] `screen_shake`：hash 噪声（sin+floor 帧号）每帧跳动、帧内稳定；CLAMP 防越界；事件驱动语义明确。
- [x] `tunnel_vision`：纯遮罩（无 screen texture）；宽度比校正（口 gdshader 正圆）；软边 smoothstep 无分支。
- [ ] 待 B/C 实测：Godot 项目内实际挂载后的视觉状态（W4.4 合并版交付时同测）。

---

### 依赖/对接提示

| 谁 | 需要知道 |
|---|---|
| B（玩法/UI） | 三个 ColorRect 的渲染顺序；事件驱动 shake 的触发点（拖假碎片/被攻击）由 B 侧信号接 `shake_amount` |
| C（前端/场景） | 场景搭建仅需 Copy 本说明 §2.1；不加代码也可用 Inspector 调参预览 |
