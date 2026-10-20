shader_type canvas_item;

// ================================================================
// 《防线》视觉压迫 Shader · 隧道视觉（纯遮罩）
// ----------------------------------------------------------------
// 用途（W3.4）：记忆崩塌阶段（30s 起）的「通道化」——屏幕中心保留一个
//   越来越小的清晰圆窗，其余全部压成近黑，模拟视野收缩、现实感从边缘消失。
// 与 vision_erosion 的关系：vision_erosion 是「冷蓝罩」侵蚀（全屏节奏），
//   tunnel_vision 是「近黑罩」收口（中心管道）——两者可叠加；战斗段由
//   tunnel_radius 驱动（pressure_params.json：30s 起 0.20 → 每 5s -0.025 →
//   60s 后保持 0.05；后摇 0.05 → 0.30 退散）。
// 挂载方式：全屏 ColorRect + ShaderMaterial（纯遮罩，不采样屏幕纹理，
//   开销极低，可直接叠在 vision_erosion 之上；见 W3\shaders\三项Shader接入说明.md §2）。
// 驱动示例（GDScript）：
//   mat.set_shader_parameter("tunnel_radius", 0.20)   # 阶段二起点
// ================================================================

// 中心清晰圆半径（口径与 vision_erosion.erosion_progress 相同：
//   1.0 = 全屏清晰，越小隧道越窄）。【注意】0.05 是阶段三的最终值；
//   接入后请从 0.20 开始驱动（0.20 → 每 5s -0.025 → 0.05）。
//   设为 -1.0 时进入自动演示模式（TIME 循环收放），方便预览。
uniform float tunnel_radius : hint_range(-1.0, 1.0) = 0.05;

// 隧道边缘的过渡宽度（0.15 = pressure_params.json 恒定值；越大边界越柔）。
uniform float tunnel_softness : hint_range(0.0, 0.5) = 0.15;

// 隧道覆盖色：近黑（微带冷蓝底，与 vision_erosion 的 AI 冷蓝一致）。
uniform vec4 tunnel_color : source_color = vec4(0.01, 0.02, 0.06, 1.0);

// 隧道中心：默认屏幕中心。UV 原点在左上角。
uniform vec2 tunnel_center = vec2(0.5, 0.5);

void fragment() {
    // 1) 解析当前隧道半径（-1 进自动演示：0.05~0.65 循环）
    float r = tunnel_radius;
    if (r < 0.0) {
        r = 0.35 + 0.30 * sin(TIME);
    }
    r = clamp(r, 0.0, 1.0);

    // 2) 像素到隧道中心的归一化距离（宽高比修正，保证正圆）
    float aspect = SCREEN_PIXEL_SIZE.y / SCREEN_PIXEL_SIZE.x;
    vec2 d = (UV - tunnel_center) * vec2(aspect, 1.0);
    float dist = length(d) / length(vec2(0.5 * aspect, 0.5));

    // 3) smoothstep 软边遮罩：cover=1 → 隧道外压近黑；隧道内 alpha=0 透明露出场景
    float cover = smoothstep(r - tunnel_softness, r + tunnel_softness, dist);

    // 4) 输出：隧道外近黑（带蓝底），隧道内完全透明
    COLOR = vec4(tunnel_color.rgb, cover * tunnel_color.a);
}
