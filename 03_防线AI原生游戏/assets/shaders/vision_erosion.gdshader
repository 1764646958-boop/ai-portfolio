shader_type canvas_item;

// ================================================================
// 《防线》视觉压迫 Shader · 视野侵蚀（动态遮罩）原型
// ----------------------------------------------------------------
// 用法（Godot 4 / MagicAI 4.6.2，语法一致）：
//   1. 新建 ColorRect（Control 节点），把 Anchors 四边都铺满全屏
//      （Layout → Full Rect，或手动把 anchor 设为 0~1）。
//   2. 给它新建 ShaderMaterial，把本文件内容贴到 shader 的 code 里。
//   3. 运行即可看到冷蓝遮罩从屏幕边缘向中心循环侵蚀（自动演示模式）。
//
// 接入战斗系统：用 GDScript 实时驱动侵蚀进度即可（0~1 的实数）：
//   $Overlay.material.set_shader_parameter("erosion_progress", battle_time / 30.0)
//
// 实现说明：这是一个「纯遮罩叠层」——不采样屏幕纹理，只输出一个带
//   alpha 遮罩的颜色，因此无需 BackBufferCopy，开销极低，可直接叠在
//   游戏画面上方。侵蚀区显示冷蓝、清晰区 alpha=0 完全透明露出底层场景。
// ================================================================

// ---- 可配置参数（Inspector 可调 / GDScript 可实时驱动）----

// 侵蚀进度：0.0 = 无侵蚀（全屏清晰）；1.0 = 遮罩填满全屏。
// 设为 -1.0 时进入「自动演示」模式，由 TIME × erosion_speed 循环驱动，方便预览。
uniform float erosion_progress : hint_range(-1.0, 1.0) = -1.0;

// 侵蚀速度：自动演示模式下每秒推进的侵蚀进度量（0~2）。
uniform float erosion_speed : hint_range(0.0, 2.0) = 0.15;

// 透明度：侵蚀层整体不透明度（1.0 = 完全不透明；实际透明度 = 1 - 此值）。
uniform float erosion_opacity : hint_range(0.0, 1.0) = 0.88;

// 边缘柔化：侵蚀边界的过渡带宽度（0 = 锐利硬边，越大越柔和）。
uniform float edge_softness : hint_range(0.0, 0.5) = 0.14;

// 侵蚀颜色：默认冷蓝，贴合「AI 界面」的压迫色调。
uniform vec4 erosion_color : source_color = vec4(0.05, 0.13, 0.30, 1.0);

// 遮罩中心：默认屏幕中心 (0.5, 0.5)。UV 原点在左上角。
uniform vec2 erosion_center = vec2(0.5, 0.5);

void fragment() {
    // 1) 解析当前侵蚀进度
    float p = erosion_progress;
    if (p < 0.0) {
        // 自动演示：让 p 在 0~1 之间循环，方便直接预览动画
        p = fract(TIME * erosion_speed);
    }
    p = clamp(p, 0.0, 1.0);

    // 2) 像素到遮罩中心的归一化距离（修正宽高比，保证圆形；0=中心，1=角落）
    //    SCREEN_PIXEL_SIZE.x = 1/屏宽，.y = 1/屏高，故 .y/.x = 屏宽/屏高 = 宽高比
    float aspect = SCREEN_PIXEL_SIZE.y / SCREEN_PIXEL_SIZE.x;
    vec2 d = (UV - erosion_center) * vec2(aspect, 1.0);
    float dist = length(d) / length(vec2(0.5 * aspect, 0.5));

    // 3) 清晰区半径随侵蚀进度收缩：
    //    p=0 → inner_radius = 1 + soft（全屏清晰）；p=1 → -soft（中心也被完全覆盖）
    float inner_radius = mix(1.0 + edge_softness, -edge_softness, p);

    // 4) 用 smoothstep 生成无分支的软边遮罩（cover = 1 表示被侵蚀覆盖）
    float cover = smoothstep(inner_radius - edge_softness,
                             inner_radius + edge_softness,
                             dist);

    // 5) 输出：侵蚀区显示冷蓝，清晰区 alpha=0 完全透明（露出底层场景）
    COLOR = vec4(erosion_color.rgb, cover * erosion_opacity * erosion_color.a);
}
