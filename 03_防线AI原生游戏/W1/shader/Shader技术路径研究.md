# 《防线》Shader 技术路径初步研究

> 交付物 ⑤ · 成员 A（主程序 / Shader 开发）
> 引擎：Godot 4.x（MagicAI = Godot 4.6.2 AI 定制版，gdshader 语法一致）
> 目标：为第三周开发的四项视觉压迫 Shader 打基础，并给出可直接贴进引擎使用的视野侵蚀原型。
> 对应《团队选题报告》7.4「战斗压迫特效」：视野侵蚀（动态遮罩）、色调分离（RGB 通道独立控制）、画面抖动（顶点位移）、隧道视觉（径向渐变遮罩）。

---

## 0. 结论速览

1. **本作是 2D 游戏，全部 Shader 用 `shader_type canvas_item`**，不用 Spatial。四项压迫效果全部跑在 2D 后处理 / 遮罩叠层上。
2. **四项效果本质是两类**：
   - **遮罩叠层型**（不采样屏幕，纯 alpha 遮罩）：**视野侵蚀**、**隧道视觉** —— 成本极低，一个全屏 ColorRect 搞定，无需 BackBufferCopy。
   - **后处理型**（需采样屏幕纹理）：**色调分离**、**画面抖动** —— 需要 BackBufferCopy 或 SubViewport 拿到画面再处理。
3. **战斗时把四项效果合并进「一个」全屏后处理 Shader**，用一组 uniform 开关 + GDScript 按 90 秒时间轴驱动。一次全屏 pass 做完，性能最稳。
4. **视野侵蚀与隧道视觉是同一个径向遮罩的两个阶段**：侵蚀 = 半透明冷蓝渐进（阶段一，0→40%）；隧道 = 高不透明暗色压到 10% 中央（阶段二）。原型里已实现前者，后者复用同一套距离场即可。
5. 性能底线：**日常 60fps，战斗 30fps 为硬底线、目标 60fps**（PerfDog 验证）。后处理 GPU 预算控制在 **< 2ms/帧**。

---

## 1. Godot 4 的 Shader 语言（gdshader）基础

gdshader 是 Godot 自研的类 GLSL 着色语言。Godot 4 里一个 Shader 文件的基本骨架：

```glsl
shader_type canvas_item;          // 着色器类型（canvas_item / spatial / particles / sky / fog）

uniform float speed : hint_range(0.0, 2.0) = 0.15;   // 可配置参数
uniform vec4 tint : source_color = vec4(1.0);         // 颜色参数

void vertex() {                    // 顶点阶段（可选），处理几何/位置
    VERTEX += vec2(0.0, 1.0);
}

void fragment() {                  // 片元阶段（必写），逐像素上色
    COLOR = vec4(1.0, 0.0, 0.0, 1.0);
}
```

### 1.1 `shader_type` 类型

| 类型 | 用途 | 本作是否使用 |
|---|---|---|
| `canvas_item` | 2D：Sprite、Control（ColorRect/TextureRect）、Node2D | ✅ **全部用这个** |
| `spatial` | 3D：网格、材质 | ❌ 本作为 2D |
| `particles` | 粒子 | 备选（若做碎片特效） |
| `sky` / `fog` | 天空 / 雾（4.3+） | ❌ |

### 1.2 `uniform` 可配置参数与 hint

`uniform` 就是暴露到 Inspector 的「可配置参数」，也是 GDScript `set_shader_parameter()` 的入口。常用 hint：

```glsl
uniform float erosion_speed : hint_range(0.0, 2.0) = 0.15;   // 数值范围（浮点/整数）
uniform int levels : hint_range(2, 64) = 16;                 // 整数范围
uniform vec4 erosion_color : source_color = vec4(0.05,0.13,0.3,1.0); // 颜色（sRGB）
uniform bool enable_shake = false;                           // 布尔开关
uniform int shape : hint_enum("圆形,矩形") = 0;               // 枚举下拉
uniform sampler2D screen_tex : hint_screen_texture, filter_linear_mipmap; // 屏幕纹理
```

> 关键点：**`source_color` 是 Godot 4 的颜色 hint**（Godot 3 的 `hint_color` 已废弃），颜色会正确做 sRGB→线性转换。战斗四件套的颜色参数都用它。

### 1.3 `vertex()` 与 `fragment()` 两阶段

- `vertex()`：逐顶点执行。`canvas_item` 里可读写 `VERTEX`（顶点局部坐标）做顶点位移（对应「画面抖动」的位移）。
- `fragment()`：逐像素执行，是绝大多数视觉效果的落点。读写 `COLOR`（最终输出色）、`UV`、`SCREEN_UV` 等。

### 1.4 `canvas_item` 常用内置变量（直接可用的全局量）

| 内置变量 | 类型 | 含义 | 用于哪个效果 |
|---|---|---|---|
| `UV` | vec2 | 本节点的纹理坐标（0~1，左上原点） | 遮罩距离场 |
| `COLOR` | vec4 | 输入/输出颜色 | 所有 |
| `VERTEX` | vec2 | 顶点局部坐标（`vertex()` 内） | 画面抖动 |
| `SCREEN_UV` | vec2 | 屏幕坐标（0~1） | 采样屏幕 |
| `SCREEN_PIXEL_SIZE` | vec2 | 单像素在屏幕 UV 里的尺寸（=1/分辨率） | 宽高比修正 |
| `SCREEN_TEXTURE` | sampler2D | 屏幕纹理（需 BackBufferCopy） | 后处理 |
| `TEXTURE` / `TEXTURE_PIXEL_SIZE` | sampler2D / vec2 | 本节点纹理 | — |
| `TIME` | float | 运行累计秒数 | 抖动/演示动画 |
| `PI` `TAU` | float | 圆周率常量 | 三角函数 |

### 1.5 常用内置函数（务必记熟，落地全靠它们）

| 函数 | 作用 | 典型场景 |
|---|---|---|
| `mix(a,b,t)` | 线性插值 | 颜色/数值过渡 |
| `smoothstep(e0,e1,x)` | 软边阶跃（无分支！） | **边缘柔化**、遮罩边界 |
| `step(e,x)` | 硬边阶跃 | 锐利遮罩 |
| `clamp(x,a,b)` | 夹取 | 参数安全 |
| `length(v)` / `distance(a,b)` | 向量长度/距离 | **径向距离场（侵蚀/隧道核心）** |
| `fract(x)` / `floor(x)` | 取小数/取整 | 减色、循环动画 |
| `dot(a,b)` | 点积 | 噪声哈希、衰减 |
| `sin/cos` | 三角 | 抖动噪声 |
| `pow/exp/sqrt` | 幂/指数/开方 | 衰减曲线（慎用，偏贵） |

---

## 2. CanvasItem vs Spatial 选择，及全屏后处理方案

### 2.1 为什么本作只用 CanvasItem

《防线》是 **2D 二次元风格、第一人称心理叙事**游戏（报告 7.4「本作以 2D 为主」），画面由 Sprite + Control UI 构成，没有 3D 网格。因此：

- **Spatial shader 不适用**——它作用于 3D 网格/材质，需要 Vertex/光与视差。强行用是方向性错误。
- 所有战斗压迫特效都落在 **2D 后处理 / 遮罩叠层** 上，用 `canvas_item` 即可，且能直接作用于全屏 Control 节点。

### 2.2 全屏后处理的三种落地方式（重点：视野侵蚀是后处理类）

「后处理」= 先渲染完整画面，再对整幅画面做一次逐像素加工。Godot 4 里 2D 全屏后处理有 3 种做法，取舍如下：

| 方案 | 原理 | 优点 | 缺点 | 适用 |
|---|---|---|---|---|
| **① BackBufferCopy + ColorRect** | 场景里放 `BackBufferCopy` 节点拷贝屏幕，上方的全屏 ColorRect 用 `hint_screen_texture` 采样 | 最轻量、零额外配置 | 每加一个后处理都要一次全屏拷贝；多个叠加会累积带宽 | 单个/少量后处理 |
| **② SubViewport + TextureRect** | 游戏世界渲染进一个 SubViewport，再用全屏 TextureRect 显示并挂 Shader | 纹理访问干净、可叠加多效果、无边界缝隙 | 多一层 Viewport 管理，UI 与世界的层级要理顺 | **战斗场景推荐** |
| **③ CompositorEffect（4.2+）** | 用 compute shader 走引擎真正的后处理管线 | 性能最强、最规范 | 要写 GLSL compute + RenderingDevice，复杂度高，2D 用偏重 | 3D / 极复杂管线 |

**本作推荐路线：**
- **日常场景**：零后处理，直接渲染，保证 60fps。
- **战斗场景**：用 **方案② SubViewport**（或项目简单时方案① BackBufferCopy），挂**一个**「战斗后处理总 Shader」，把四项效果合并成**一次全屏 pass**，用 uniform 开关逐项启停。

> 为什么合并成一次 pass？全屏 pass 的成本 = 分辨率像素数 × 每像素指令。1080p ≈ 207 万像素。四项各跑一次 = 800 万+ 像素/帧，中低端集显会跌破 30fps；合并成一次 = 207 万像素，稳。

### 2.3 视野侵蚀的落地方式（后处理类，但可更省）

任务明确「视野侵蚀是后处理类」，但落地时它可以比一般后处理**更省**，取决于要不要「改变被侵蚀区域的画面」：

- **纯遮罩叠层（原型采用）**：侵蚀 = 在画面上叠一层带 alpha 遮罩的冷蓝 ColorRect，**不采样屏幕**。无需 BackBufferCopy，成本近乎为 0。适合「冷蓝边框向内收缩」这一纯覆盖语义。
- **真后处理（进阶）**：若要求「被侵蚀区域还要变蓝/降饱和/变暗」，才需要采样屏幕（BackBufferCopy/SubViewport），在 `fragment()` 里 `mix(原色, 冷蓝, cover)`。

原型先落地「纯遮罩叠层」版（见 `视野侵蚀Shader原型.gdshader`），进阶版作为第三周的可选增强。

---

## 3. 四项 Shader 实现路径

### 3.0 战斗时间轴 ↔ Shader 参数映射（落地总纲）

《团队选题报告》4.4 定义了 90 秒三阶段战斗，四项 Shader 与时间的对应关系：

| 战斗阶段 | 时间 | 主导 Shader | 关键参数走向 |
|---|---|---|---|
| 阶段一·认知入侵 | 0–30s | **视野侵蚀** + **色调分离** | 侵蚀进度 0→0.4（每 5 秒收缩一次，30s 占 40% 屏幕）；红色先被过滤（~前 20s），绿色随后（~40s），只剩冷蓝+灰白 |
| 阶段二·记忆崩塌 | 30–60s | **隧道视觉** + **画面抖动** | AI 界面扩张到 90%（清晰区压到 10%）；拖拽假碎片/被攻击时触发抖动 |
| 阶段三·最终抉择 | 60–90s | 保持高压 + 视结果收敛 | 玩家选 A（依赖）→ 进一步收敛；选 B（输入旧友的话）→ 遮罩裂纹式退散 |

四项效果全部由 **GDScript 每帧 `set_shader_parameter()` 驱动**，shader 内部不写死时间逻辑（原型里的 `TIME` 仅用于「独立预览」的自动演示）。

---

### 3.1 视野侵蚀（动态遮罩）

- **目标**：冷蓝「AI 界面」边框从屏幕边缘向中心收缩，逐秒吞噬中央清晰区。
- **类型**：`canvas_item` 遮罩叠层（纯 alpha 遮罩，无需采样屏幕）。
- **核心数学**：径向距离场 + smoothstep 软边。
  1. 把 UV 平移到遮罩中心，乘宽高比修正 → 得到圆形距离 `dist ∈ [0,1]`（0=中心，1=角落）。
  2. 侵蚀进度 `p ∈ [0,1]` 控制「清晰区半径」`inner_radius = mix(1 + soft, -soft, p)`——半径随 p 从最大收缩到 0。
  3. `cover = smoothstep(inner_radius - soft, inner_radius + soft, dist)` 得到无分支软边遮罩。
  4. 输出 `vec4(冷蓝.rgb, cover * opacity)`：侵蚀区冷蓝、清晰区透明。
- **可配置参数**（原型已实现，全部 `uniform`）：`erosion_progress`（进度）、`erosion_speed`（速度）、`erosion_opacity`（透明度）、`edge_softness`（边缘柔化）、`erosion_color`（颜色）、`erosion_center`（中心）。
- **落地步骤**：
  1. 直接使用 `视野侵蚀Shader原型.gdshader`（已可贴进引擎）。
  2. 战斗中把 `erosion_progress` 从 `-1.0`（自动演示）改为 GDScript 驱动：`set_shader_parameter("erosion_progress", battle_time/30.0*0.4)`。
  3. 「每 5 秒收缩一次」若要做成**阶梯感**而非平滑，可把进度改成 `floor(battle_time/5.0)/6.0*0.4`（6 步）。
- **变形**：若要「矩形边框」而非圆形，把距离场从 `length(d)` 换成 Chebyshev 距离 `max(abs(d.x), abs(d.y))` 即可（界面感更强）。

---

### 3.2 色调分离（RGB 通道独立控制）

- **目标**：阶段一「红色最先被过滤，然后绿色消失，只剩冷蓝和灰白」；叠加「数字纹理」的减色量化感。
- **类型**：`canvas_item` **真后处理**（需采样屏幕）。
- **核心数学**：通道独立增益 + 减色量化（posterize）。
- **关键代码**：

```glsl
shader_type canvas_item;
uniform sampler2D screen_tex : hint_screen_texture, filter_linear_mipmap;
uniform float red_retain : hint_range(0.0, 1.0) = 1.0;    // 红色保留比例（1→0 即被过滤）
uniform float green_retain : hint_range(0.0, 1.0) = 1.0;  // 绿色保留比例
uniform float blue_retain : hint_range(0.0, 1.0) = 1.0;   // 蓝色保留比例
uniform int posterize_levels : hint_range(2, 64) = 16;    // 减色等级
uniform float posterize_amount : hint_range(0.0, 1.0) = 1.0; // 减色强度

void fragment() {
    vec4 c = texture(screen_tex, SCREEN_UV);
    // ① 通道独立过滤：红 → 绿 依次被剥夺，只剩冷蓝 + 灰白
    c.r *= red_retain;
    c.g *= green_retain;
    c.b *= blue_retain;
    // ② 减色量化（posterize）：制造「数字纹理」的阶梯色阶
    if (posterize_amount > 0.0) {
        float lv = float(posterize_levels);
        vec3 q = floor(c.rgb * lv) / lv;
        c.rgb = mix(c.rgb, q, posterize_amount);
    }
    COLOR = c;
}
```

- **落地步骤**：
  1. 建 BackBufferCopy（或 SubViewport）+ 全屏 ColorRect，挂此 shader。
  2. 阶段一 GDScript 驱动：`red_retain` 在前 ~20s 从 1→0，`green_retain` 在 ~40s 从 1→0，`blue_retain` 保持 1（或微降到 0.9 制造灰白）。
  3. 如需「整体向灰白靠拢」，再加一个 `gray = dot(c.rgb, vec3(0.299,0.587,0.114))` 与 `mix(c.rgb, vec3(gray), desat_amount)`。
- **注意**：这是真后处理，需要 `hint_screen_texture` 且场景里有 BackBufferCopy/SubViewport，否则采到的是空/上一帧内容。

---

### 3.3 画面抖动（顶点位移 / UV 偏移）

> ⚠️ **修正标注（W2，2026-08-25）**：团队选题报告 §7.4 写「画面抖动（顶点位移）」；
> 经 W1 研究确认，顶点位移版只能整幅平移且边缘露缝（幅度大时屏幕对侧露出空隙），
> 落地采用 **UV 偏移版为主、顶点位移为备选**——对外口径（PPT/技术演示视频）以此为准。

- **目标**：拖拽假碎片、被攻击时，整幅画面随机抖动，模拟认知崩塌的不稳定感。
- **类型**：`canvas_item`。两种落地：**顶点位移**（报告指定的「顶点位移」）与 **UV 偏移**（更稳，无边界缝隙）。
- **核心数学**：每帧一个伪随机偏移（无状态哈希），幅值由 `shake_amount` 控制。

**A. 顶点位移版（报告指定）**——在 `vertex()` 里整体平移四个顶点：

```glsl
shader_type canvas_item;
uniform float shake_amount : hint_range(0.0, 0.02) = 0.0;  // 抖动幅度（越大越剧烈）

float hash(float t) { return fract(sin(t) * 43758.5453); }

void vertex() {
    float f = floor(TIME * 60.0);           // 按 60fps 步进，每帧跳一次
    VERTEX += vec2(hash(f + 1.0), hash(f + 2.0)) * shake_amount - shake_amount * 0.5;
}
```

**B. UV 偏移版（推荐，更稳）**——在 `fragment()` 里抖动采样坐标，避免平移四边形时露出屏幕边缘：

```glsl
shader_type canvas_item;
uniform sampler2D screen_tex : hint_screen_texture, filter_linear_mipmap;
uniform float shake_amount : hint_range(0.0, 0.05) = 0.0;

float hash(float t) { return fract(sin(t) * 43758.5453); }

void fragment() {
    float f = floor(TIME * 60.0);
    vec2 jitter = (vec2(hash(f + 1.0), hash(f + 2.0)) - 0.5) * shake_amount;
    COLOR = texture(screen_tex, SCREEN_UV + jitter);
}
```

- **落地步骤**：
  1. `shake_amount` 由**交互事件**驱动而非时间轴：拖拽到「假碎片」时 GDScript 把它冲到 0.03，随后每帧衰减（`shake_amount = lerp(shake_amount, 0.0, 0.2)`），制造「强烈阻力」的震感。
  2. 若项目里已有 `Camera2D`，**更省事的替代方案**是直接在 GDScript 里抖动相机 offset（`camera.offset = random_dir * amount`），完全不用 shader；shader 版是「四件套」统一交付时的主方案。
- **注意**：顶点位移版的四边形是 4 个顶点，只能做「整幅平移」抖动，不能做局部抖动；幅度过大会在屏幕对侧露出空隙（需把 ColorRect 放大 5–10% 留安全边距），所以推荐 B 方案。

---

### 3.4 隧道视觉（径向渐变遮罩）

- **目标**：阶段二 AI 界面扩张到 90%，视野被压缩到屏幕中央极小的「隧道」里。
- **类型**：`canvas_item` 遮罩叠层（与视野侵蚀共用同一套径向距离场）。
- **核心数学**：与视野侵蚀**完全同构**，区别只在两点——半径固定很小、遮罩色是不透明暗色而非半透明冷蓝。

```glsl
shader_type canvas_item;
uniform float tunnel_radius : hint_range(0.0, 0.5) = 0.05;      // 中央清晰区半径（0.05≈直径 10%）
uniform float tunnel_softness : hint_range(0.0, 0.5) = 0.15;    // 过渡带宽度
uniform vec4 tunnel_color : source_color = vec4(0.0, 0.0, 0.02, 1.0); // 遮罩色（近黑）

void fragment() {
    float aspect = SCREEN_PIXEL_SIZE.y / SCREEN_PIXEL_SIZE.x;
    vec2 d = (UV - vec2(0.5)) * vec2(aspect, 1.0);
    float dist = length(d) / length(vec2(0.5 * aspect, 0.5));
    float cover = 1.0 - smoothstep(tunnel_radius, tunnel_radius + tunnel_softness, dist);
    COLOR = vec4(tunnel_color.rgb, cover * tunnel_color.a);
}
```

- **落地步骤**：
  1. 阶段二 GDScript 驱动 `tunnel_radius`：从 0.2 收缩到 0.05（视野 10%）。
  2. 与视野侵蚀**复用同一个 shader** 也是可行方案：侵蚀进度推到 0.9、颜色切暗、透明度拉到 1 就是隧道。第三周可做成「侵蚀/隧道二合一」减少 pass。
  3. 隧道中心可随 AI「眼睛」位置轻微漂移（`tunnel_center` uniform 缓动），增加压迫感。

---

## 4. 性能注意点（战斗场景 30fps 以上）

### 4.1 成本模型：全屏后处理的真实开销

- 全屏 pass 成本 = **像素数 × 每像素指令**。1080p = 1920×1080 ≈ **207 万像素**。
- 每多一个独立全屏 pass 就再乘一遍。**四个效果各自跑 = 800 万+ 像素/帧**，是中低端集显掉到 30fps 以下的主因。
- 对策：**合并成一次 pass**（3.0 的「战斗后处理总 Shader」），四个效果在同一个 `fragment()` 里串行完成，只花 207 万像素。

### 4.2 无分支技巧

- 用 `smoothstep()` / `clamp()` / `mix()` 替代 `if` 判断。现代 GPU 分支预测不差，但逐像素 `if` 仍可能产生 warp 分歧；smoothstep 是硬件友好的纯算术，且天然软边。
- 原型里 `erosion_progress` 的判断是 uniform（全屏同值），属「一致性分支」，无害。

### 4.3 纹理采样

- 后处理（色调分离/画面抖动）每帧只 `texture(screen_tex, ...)` **1 次**；不要在 fragment 里做多次不同偏移采样（除非刻意做模糊）。
- 屏幕纹理用 `filter_linear_mipmap` 抗锯齿；遮罩叠层（侵蚀/隧道）**根本不采样屏幕**，开销近乎 0。

### 4.4 避免昂贵运算

- 少用 `pow`/`exp`/`log`/`sqrt` 等超越函数；能用 `mix`/`smoothstep` 近似就用近似。
- 抖动噪声用 `fract(sin(...))` 这种 O(1) 哈希，**不要**采样噪声纹理。
- 不要在 fragment 里写循环；若做模糊等重效果，务必降分辨率（见 4.5）。

### 4.5 分辨率与降采样

- 后处理若压测不达标，把后处理 RT 降到 **0.5× 分辨率**再上采样。色调分离/画面抖动对分辨率不敏感，几乎看不出差异，却能省 3/4 像素。
- SubViewport 方案天然支持降采样（Viewport `size` 设一半），BackBufferCopy 方案则依赖整体分辨率。

### 4.6 与 LLM 调度的 CPU/GPU 分工（本作特有）

- 战斗场景 GPU 侧压力不大，**30fps 的关键风险在 CPU/网络侧**：阶段三 LLM 实时对话（目标延迟 <2s）。
- **铁律**：LLM 调用必须**异步**（后台线程 / `await`），绝不阻塞主线程的 `_process` 渲染循环；战斗对话用「预生成 + 缓存 + 超时降级」。
- Shader 只吃 uniform 数字，**每帧不读 LLM、不读磁盘、不读网络**，保证渲染帧独立稳定。

### 4.7 性能预算表（战斗场景）

| 项 | 预算 | 说明 |
|---|---|---|
| 帧目标 | 60fps（16.6ms/帧），30fps 硬底线 | PerfDog 验证 |
| 后处理总 Shader | **< 2ms/帧** | 一次合并 pass，1080p |
| 场景 + Sprite | ~8–10ms | 2D 场景，合批尽量少 |
| UI + 战斗 HUD | ~2–3ms | 计时器/选项/碎片图标 |
| LLM 调用 | 不占渲染帧 | 异步，超时降级 |
| 预留余量 | ~2ms | 抖动峰值、GC 尖刺 |

> 验证工具：Godot 内置 `debugger → Monitors → Frame Time`，配合赛事官方 PerfDog。先保证 60fps，再逐步把 `erosion_opacity`/软边等美术参数往上调，用数据说话而非拍脑袋。

---

## 5. 落地清单（第三周工作项）

### 5.1 战斗后处理驱动脚本骨架（示意）

```gdscript
# 挂在战斗场景根节点（Godot 4 / GDScript）
@onready var post: ShaderMaterial = $PostOverlay.material   # 合并后的后处理材质

const PHASE1_END := 30.0
const PHASE2_END := 60.0
var battle_time := 0.0

func _process(delta: float) -> void:
    battle_time += delta

    if battle_time <= PHASE1_END:
        # 阶段一：视野侵蚀（30s 占 40%）+ 色调分离（红→绿依次过滤）
        post.set_shader_parameter("erosion_progress", battle_time / PHASE1_END * 0.4)
        post.set_shader_parameter("red_retain",   1.0 - clamp(battle_time / 20.0, 0.0, 1.0))
        post.set_shader_parameter("green_retain", 1.0 - clamp(battle_time / 40.0, 0.0, 1.0))
    elif battle_time <= PHASE2_END:
        # 阶段二：隧道视觉（视野压到 10%）；抖动由拖拽事件单独驱动
        var t := (battle_time - PHASE1_END) / (PHASE2_END - PHASE1_END)
        post.set_shader_parameter("tunnel_radius", lerp(0.2, 0.05, t))
        post.set_shader_parameter("erosion_progress", 0.9)
    else:
        # 阶段三：最终抉择——选 A 继续收敛，选 B 遮罩退散
        pass
```

### 5.2 第三周开发项

1. 把 `视野侵蚀Shader原型.gdshader` 接入战斗场景，验证「每 5 秒收缩、30s 占 40%」的节奏。
2. 落地「战斗后处理总 Shader」，合并色调分离 + 画面抖动 + 侵蚀/隧道（一次 pass）。
3. 搭建 SubViewport（或 BackBufferCopy）后处理链，跑通 `hint_screen_texture` 采样。
4. 用 GDScript 把 90 秒时间轴与交互事件（拖拽阻力触发抖动）接到 uniform。
5. PerfDog 压测战斗场景，按 4.7 预算表调优，锁 60fps / 保 30fps。

---

## 附录：原型 Shader 参数速查

`视野侵蚀Shader原型.gdshader` 的全部可配置参数：

| 参数 | 类型 | 默认值 | 含义 |
|---|---|---|---|
| `erosion_progress` | float | -1.0 | 侵蚀进度 0~1；-1 = 自动演示 |
| `erosion_speed` | float | 0.15 | 自动演示下的侵蚀速度 |
| `erosion_opacity` | float | 0.88 | 侵蚀层不透明度（透明度=1-此值） |
| `edge_softness` | float | 0.14 | 边缘柔化过渡带宽度 |
| `erosion_color` | vec4 | 冷蓝 | 侵蚀层颜色 |
| `erosion_center` | vec2 | (0.5,0.5) | 遮罩中心 |
