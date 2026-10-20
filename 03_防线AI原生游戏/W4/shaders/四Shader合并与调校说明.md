# 四 Shader 合并与调校说明（W4.4）

> 交付物 W4.4 · 成员 A · 2026-08-31
> 仓库新增：`assets\shaders\battle_post.gdshader`（单 pass 合并版）
> 　　　　　`scripts\battle_post_controller.gd`（90s+30s 时间轴控制器）
> 前身：W3.4 四枚散装 Shader（vision_erosion / tunnel_vision / color_grade / screen_shake）+ `W3\shaders\三项Shader接入说明.md`
> 数据源：W3\battle\pressure_params.json v1（B4 冲突同前，**B 定稿后同步一份到 `res://config/pressure_params.json` 即可被 controller 优先加载**）

---

## 1. 为什么合并（W3.4 → W4.4）

| | W3.4 散装 | W4.4 合并版 |
|---|---|---|
| ColorRect | 4 个叠层 | 1 个 |
| 采样 pass | grade/shake 各 1 次 SCREEN_TEXTURE | 1 次/帧 |
| 树序/挂载出错面 | 顺序敏感（vision→tunnel→grade→shake） | 顺序固化进 shader |
| 移动端/低端机 | ~4.6M 像素×2 采样 | ~207 万像素×1 采样（§7 预算） |
| 调参 | 4 个材质 | 1 个 ShaderMaterial + controller |

C 的迁移动作：删除 4 个散装 ColorRect，新建 1 个全屏 ColorRect 挂 `battle_post.gdshader`，节点加入组 `battle_post`。

## 2. 单 pass 管线（与分离版的数学关系）

```
纹理采样(UV+shake_offset)  ──① 通道保留(灰度 mix) ──② Posterize ──③ 冷蓝罩 over ──④ 近黑罩 over → COLOR
        └ screen_shake 效果就地合并（见下）        └ color_grade        └ erosion    └ tunnel
```

1. **shake 先于 grade，等价于分离版**：color_grade 全部是逐点（per-pixel）函数：`grade(S(UV+off)) ≡ grade(S)(UV+off)`。分离版（先 grade 出中间帧再被 shake 采样）在同一像素值的数学结果一致——唯一差异是双采样造成的纹理 LOD/mip 微差，可忽略。
2. **遮罩由「叠层」改为「over 合入」**：分离版遮罩色在 grade **之前**（被灰白化/量化）；合并版遮罩在 grade **之后**（纯色 over）——冷蓝罩保持纯净冷蓝、近黑罩保持近黑。视觉更贴「AI 覆盖」语义，属**有意变更**（不是回归）。
3. **采样次数**：1 次 SCREEN_TEXTURE + 遮罩纯数学（无二次取样），比分离版省一次全屏采样。

## 3. uniform 映射表（C/B 既有调用不改名）

| battle_post（合并版） | 原 W3.4 文件 | pressure_params | controller 驱动键 |
|---|---|---|---|
| `enable_erosion / enable_tunnel / enable_color_grade / enable_shake` | （新增开关） | — | 布尔，手动/分设备开放 |
| `erosion_progress` | vision_erosion | curves.erosion_progress | get_uniforms 0/20/30/…/90 |
| `erosion_speed / erosion_opacity / edge_softness / erosion_color / erosion_center` | vision_erosion | （常量；仅 -1 自动演示用） | — |
| `tunnel_radius` | tunnel_vision | curves.tunnel_radius (30s 起) | 同上 |
| `tunnel_softness / tunnel_color / tunnel_center` | tunnel_vision | （常量） | — |
| `red_retain / green_retain / blue_retain` | color_grade | curves.*_retain | 同上 |
| `posterize_amount / posterize_levels` | color_grade | curves.posterize_* | 同上 |
| `shake_amount / shake_seed` | screen_shake | curves.shake_amount（事件驱动） | set_shake / start_battle 换seed |

## 4. controller 接入（战斗场景 3 步）

```gdscript
# 1) 场景自动绑定（三选一）：
#    a. 全屏 ColorRect 加入节点组 "battle_post"（推荐，零代码）
#    b. battle_post_controller.target_path = NodePath("...")
#    c. BattlePost.bind_shader_material(mat)  # 显式绑定

# 2) 战斗事件接线（battle_test.gd 或 battle 场景脚本）：
BattlePost.start_battle()                     # 5.1 触发
BattlePost.phase_changed.connect(func(p): BattleAudio.set_phase(p))  # 若已注册 autoload 则自动
BattlePost.set_shake(0.03)                    # QTE 拖假碎片/被攻击（事件驱动）
BattlePost.resolve_battle(true)               # 5.4 选 A「只相信你」（蚀蒙从 1.0 退散）
BattlePost.resolve_battle(false)              # 5.4 选 B「那他也说过」+LLM 匹配（从 0.9 立即退散）

# 3) 调试/录制：
BattlePost.get_uniforms()                     # 快照 + 打印：BattlePost.set_battle_time(45.0)
```

- `phase_changed` 在 t=0/30/60/90 触发（"phase1/2/3/aftermath"），**battle_audio 已自动联动**（`/root/battle_audio` 存在即接）。
- `battle_finished(hold)` 在 t=120 触发（后摇完毕，可接 BGM 复位/场景切回）。

## 5. 调校档位（启用开关的可视化调参）

| 阶段 | enable_erosion | enable_tunnel | enable_color_grade | enable_shake |
|---|---|---|---|---|
| 日常/预热 | 关（或 -1 演示） | 关 | 关 | 关 |
| battle 全竞演 | 开 | 开（30s 后自动亮） | 开 | 开 |
| 低端机档 | 关 | 开 | 开 | 开（峰值 0.02） |
| 截图/静态渲染 | 关/设为 -1 演示 | 关 | 开 | 关 |

## 6. 验收自查（Godot 编辑器）

- [ ] `battle_post.gdshader` 加进全屏 ColorRect 后：无红色 shader 报错；`_mask_dist` 无编译警告
- [ ] `BattlePost.start_battle()`：0-20s 红通道逐段抽离 → 25-40s 绿抽离 → 40s+ 灰蓝机械色 + t≥20 出现 posterize 色带 → 30s 起隧道收口（0.20→0.05）→ 60-90s 高压保持
- [ ] `set_shake(0.03)` → 画面整体抖动（无露底黑边），一秒内衰减回稳
- [ ] `resolve_battle(true/false)` → 20s 后摇全通道回 1.0、posterize 归 0、tunnel 回 0.30 退出
- [ ] `get_uniforms()` 值与 `pressure_params.json` 逐 5s 表核对（抽 5 个时点）
- [ ] 与 battle_audio 联动：phase 切换时控制台同步打印 `[BattleAudio] phase →`

## 7. 性能预算（@1920×1080）

- 单次全屏采样 + 两次 smoothstep/长 bool 分支：估算 <1.2ms（GLES3/兼容渲染器）；预算 <2ms/帧 ✓
- 无 BackBufferCopy 必须项（采样失败提示仍援引：color_grade 原注——若 SCREEN_TEXTURE 空，在 ColorRect 前加一枚 BackBufferCopy 兜底）
- 移动端可关 `enable_shake`（最大头是随机数两枚 sin+floor，其实也是几十 cycle——非重点；分级以质感为准）

## 8. 已知差异 vs 分离版（记录在案）

1. 遮罩（冷蓝/近黑）不再被灰度化/量化——**有意**，见 §2.2。
2. shake 采样从「全局叠加帧」改为「uv 偏移同帧」——数学等价（§2.1）。
3. `enable_*` 全关时输出 = 原屏直通（仅一次采样拷贝），空跑成本 ≈ 无。

## 9. 待 B 定稿后的一次性动作（两处同步）

1. **B4 bpm/参数终稿**（170 vs 160、B1 窗口、B5 等）：改 `res://config/pressure_params.json`（复制 W3\battle\pressure_params.json 的终稿模板即可）→ controller 自动优先加载；否则改 `battle_post_controller.gd` 内置 `DEFAULT_TABLES`。
2. **B6/B7**（真碎片 shake、friend 层限额）：只影响 battle_audio.gd / 事件触发，不涉及本控制器。

## 10. 变更记录

| 版本 | 日期 | 变更 |
|---|---|---|
| v1 | 2026-08-31 | 单 pass 合并版 + controller + 本说明（W3.4 三枚散装保留在仓库，未删——备份/非战斗场景可继续用） |
