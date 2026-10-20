shader_type canvas_item;

// ================================================================
// 《防线》视觉压迫 Shader · 战斗后处理单 pass 合并版（W4.4）
// ----------------------------------------------------------------
// 合并对象（W3.4 四个散装 ColorRect → 此一个）：
//   vision_erosion(冷蓝罩) + tunnel_vision(近黑管道) + color_grade(通道保留/海报量化)
//   + screen_shake(UV 抖动)
// uniform 命名与原四文件逐一对应（C/B 侧既有 set_shader_parameter 调用不改名）；
// 另加 enable_* 四开关（0=跳过该效果，便于性能分级/半开半关联调）。
//
// 渲染管线（单 pass、单次 SCREEN_TEXTURE 采样，数学说明见 W4\shaders\四Shader合并与调校说明.md §3）：
//   1) 抖动偏移采样（screen_shake 效果 —— 先抖后分级，与分离版数学等价）
//   2) 三通道保留 + 灰色基准（color_grade 通道部分）
//   3) Posterize 量化（color_grade 量化部分，可选开）
//   2.5) 局部暖色 mask（§E，B5；分级后、罩层前，恢复「原色 × 暖光」）
//   4) 冷蓝侵蚀罩 over 叠加（可选开；纯色 over，侵蚀色不被灰度化 = 比分离版更纯）
//   5) 近黑隧道罩 over 叠加（可选开）
//
// 驱动方：scripts/battle_post_controller.gd（90s 时间轴，数据源 W3\battle\pressure_params.json）
// 挂载：全屏 ColorRect + ShaderMaterial（替代 W3.4 四个散装 ColorRect——C 删旧四节点）。
//   Godot 4 已移除 SCREEN_TEXTURE 内建，必须显式声明 uniform（见下方 §0）；
//   若采样仍为空 → 在 ColorRect 前兜底 BackBufferCopy。
// ================================================================

// ─────────────────────────
// §0 · 屏幕纹理
// ─────────────────────────
// Godot 4 把 SCREEN_TEXTURE 内建移除了，改成用 hint_screen_texture 的 uniform。
// 不声明这一行，fragment() 里的 texture(SCREEN_TEXTURE, uv) 会让整个 shader 编译失败
// （报 "SCREEN_TEXTURE has been removed"），表现为战斗画面零效果——不是画面变黑，是彻底不生效。
uniform sampler2D SCREEN_TEXTURE : hint_screen_texture, filter_linear_mipmap;

// ---- enable 开关（0/1；用 bool 在 GDScript 直接传 true/false）----
uniform bool enable_erosion = true;      // 冷蓝侵蚀罩
uniform bool enable_tunnel = false;      // 近黑隧道（非战斗时段建议关）
uniform bool enable_color_grade = true;  // 通道保留 + 海报量化
uniform bool enable_shake = true;        // 画面抖动

// ─────────────────────────
// §A · 视野侵蚀（= vision_erosion.gdshader 原 uniform）
// ─────────────────────────
// 侵蚀进度：0=无侵蚀 1=全屏覆盖；-1.0=自动演示（TIME×speed 循环）
uniform float erosion_progress : hint_range(-1.0, 1.0) = -1.0;
uniform float erosion_speed : hint_range(0.0, 2.0) = 0.15;
uniform float erosion_opacity : hint_range(0.0, 1.0) = 0.88;
uniform float edge_softness : hint_range(0.0, 0.5) = 0.14;
uniform vec4 erosion_color : source_color = vec4(0.05, 0.13, 0.30, 1.0);
uniform vec2 erosion_center = vec2(0.5, 0.5);

// ─────────────────────────
// §B · 隧道视觉（= tunnel_vision.gdshader 原 uniform）
// ─────────────────────────
// 中心清晰圆半径：1.0=全屏清晰；-1.0=自动演示（0.35±0.30 正弦循环）
uniform float tunnel_radius : hint_range(-1.0, 1.0) = 0.05;
uniform float tunnel_softness : hint_range(0.0, 0.5) = 0.15;
uniform vec4 tunnel_color : source_color = vec4(0.01, 0.02, 0.06, 1.0);
uniform vec2 tunnel_center = vec2(0.5, 0.5);

// ─────────────────────────
// §C · 颜色分级（= color_grade.gdshader 原 uniform）
// ─────────────────────────
uniform float red_retain : hint_range(0.0, 1.0) = 1.0;
uniform float green_retain : hint_range(0.0, 1.0) = 1.0;
uniform float blue_retain : hint_range(0.0, 1.0) = 1.0;
uniform float posterize_amount : hint_range(0.0, 1.0) = 0.0;
uniform float posterize_levels : hint_range(2.0, 32.0) = 16.0;

// ─────────────────────────
// §D · 画面抖动（= screen_shake.gdshader 原 uniform）
// ─────────────────────────
uniform float shake_amount : hint_range(0.0, 0.10) = 0.0;
uniform float shake_seed : hint_range(0.0, 100.0) = 0.0;

// ─────────────────────────
// §E · 局部暖色 mask（B5：刺痛型暖色，仅最近 3 次交互锚点位置，≈15% 画面）
// ----------------------------------------------------------------
// 语义：mask 圆内把「分级后的冷色」混回「原色 × 暖色偏移」——AI 把旧友的暖色
//       回忆提取出来展示给玩家（0.5-1s 后由 AI 文字框遮盖；遮盖为上层 UI 行为）。
// 3 槽 = 最近 3 次交互锚点（controller.flash_warm_mask 维护 FIFO）；
// strength=0 或 radius=0 时该槽自动跳过（默认全 0 = 功能关闭）。
// ─────────────────────────
uniform vec3 warm_mask_tint = vec3(1.0, 0.80, 0.60);      // 暖色偏移（回忆暖光）
uniform float warm_mask_softness : hint_range(0.0, 0.5) = 0.12;
uniform vec2 warm_mask_center_0 = vec2(0.5, 0.5);
uniform float warm_mask_radius_0 : hint_range(0.0, 1.0) = 0.0;
uniform float warm_mask_strength_0 : hint_range(0.0, 1.0) = 0.0;
uniform vec2 warm_mask_center_1 = vec2(0.5, 0.5);
uniform float warm_mask_radius_1 : hint_range(0.0, 1.0) = 0.0;
uniform float warm_mask_strength_1 : hint_range(0.0, 1.0) = 0.0;
uniform vec2 warm_mask_center_2 = vec2(0.5, 0.5);
uniform float warm_mask_radius_2 : hint_range(0.0, 1.0) = 0.0;
uniform float warm_mask_strength_2 : hint_range(0.0, 1.0) = 0.0;

// -- 内部复用：遮罩（侵蚀/隧道）半径计算，宽高比修正保证正圆 --
float _mask_dist(vec2 uv, vec2 center, float aspect) {
    vec2 d = (uv - center) * vec2(aspect, 1.0);
    return length(d) / length(vec2(0.5 * aspect, 0.5));
}

// -- 暖色 mask 单槽：分级后颜色 → 混回「原色 × 暖色偏移」（cover 圆内生效） --
void _apply_warm_mask(inout vec3 col, vec3 base_col, vec2 uv, vec2 center,
                      float radius, float strength, float aspect) {
    if (strength <= 0.0 || radius <= 0.0) { return; }
    float dist = _mask_dist(uv, center, aspect);
    float cover = 1.0 - smoothstep(radius - warm_mask_softness,
                                   radius + warm_mask_softness, dist);
    vec3 warm = clamp(base_col * warm_mask_tint, 0.0, 1.0);
    col = mix(col, warm, cover * strength);
}

void fragment() {
    // ---- 1) 抖动偏移（screen_shake；60Hz 帧 hash，帧内稳定帧间跳变）----
    vec2 uv = UV;
    if (enable_shake) {
        float t = floor(TIME * 60.0);
        vec2 rnd = vec2(
            fract(sin(t * 12.9898 + shake_seed * 17.0) * 43758.5453),
            fract(sin(t * 78.2330 + shake_seed * 31.7) * 43758.5453)
        ) * 2.0 - 1.0;
        vec2 offset = rnd * shake_amount * vec2(1.0, SCREEN_PIXEL_SIZE.x / SCREEN_PIXEL_SIZE.y);
        uv = clamp(uv + offset, vec2(0.0), vec2(1.0));
    }

    // ---- 2) 采样 + 颜色分级（color_grade：通道保留 + 海报量化；如果不需要整体分级可关 enable_color_grade）----
    vec3 col = texture(SCREEN_TEXTURE, uv).rgb;
    vec3 base_col = col;    // B5 暖色 mask 用：分级前原色（mask 内恢复「原色 × 暖色」）
    if (enable_color_grade) {
        float gray = dot(col, vec3(0.299, 0.587, 0.114));
        col = mix(vec3(gray), col, vec3(red_retain, green_retain, blue_retain));
        float step_size = 1.0 / posterize_levels;
        vec3 quantized = floor(col / step_size) * step_size;
        col = mix(col, quantized, posterize_amount);
    }

    // ---- 2.5) 局部暖色 mask（B5：3 槽 = 最近 3 次交互锚点；分级后、罩层前）----
    {
        float warm_aspect = SCREEN_PIXEL_SIZE.y / SCREEN_PIXEL_SIZE.x;
        _apply_warm_mask(col, base_col, uv, warm_mask_center_0, warm_mask_radius_0, warm_mask_strength_0, warm_aspect);
        _apply_warm_mask(col, base_col, uv, warm_mask_center_1, warm_mask_radius_1, warm_mask_strength_1, warm_aspect);
        _apply_warm_mask(col, base_col, uv, warm_mask_center_2, warm_mask_radius_2, warm_mask_strength_2, warm_aspect);
    }

    // ---- 3) 冷蓝侵蚀罩 over（vision_erosion；-1 走自动演示）----
    if (enable_erosion) {
        float p = erosion_progress;
        if (p < 0.0) { p = fract(TIME * erosion_speed); }
        p = clamp(p, 0.0, 1.0);
        float aspect = SCREEN_PIXEL_SIZE.y / SCREEN_PIXEL_SIZE.x;
        float dist = _mask_dist(uv, erosion_center, aspect);
        float inner_radius = mix(1.0 + edge_softness, -edge_softness, p);
        float cover = smoothstep(inner_radius - edge_softness,
                                 inner_radius + edge_softness, dist);
        col = mix(col, erosion_color.rgb, cover * erosion_opacity * erosion_color.a);
    }

    // ---- 4) 近黑隧道罩 over（tunnel_vision；-1 走自动演示）----
    if (enable_tunnel) {
        float r = tunnel_radius;
        if (r < 0.0) { r = 0.35 + 0.30 * sin(TIME); }
        r = clamp(r, 0.0, 1.0);
        float aspect = SCREEN_PIXEL_SIZE.y / SCREEN_PIXEL_SIZE.x;
        float dist = _mask_dist(uv, tunnel_center, aspect);
        float cover = smoothstep(r - tunnel_softness, r + tunnel_softness, dist);
        col = mix(col, tunnel_color.rgb, cover * tunnel_color.a);
    }

    COLOR = vec4(col, 1.0);
}
