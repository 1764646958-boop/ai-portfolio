shader_type canvas_item;

// ================================================================
// 《防线》视觉压迫 Shader · 色调分离 / 灰白化（颜色分级）
// ----------------------------------------------------------------
// 用途（W3.4 · 配合 W3\battle\pressure_params.json 的 0-90s 时间轴）：
//   1. 记忆侵蚀期间逐通道「滤除/白化」：红（0-20s）→ 绿（25-40s）→
//      微灰蓝（阶段二起），画面从日常色走向机械冷灰；
//   2. Posterize（色调分离/减色量化）制造「数字纹理」的机械感。
// 挂载方式：全屏 ColorRect + ShaderMaterial（叠在战斗画面上层）。
//   注意：本 Shader 采样 SCREEN_TEXTURE（hint_screen_texture），
//   若采样结果为空，请在 ColorRect 前加一个 BackBufferCopy 作兜底
//   （Godot 4 通常自动处理，详见 W3\shaders\三项Shader接入说明.md §2）。
// 驱动示例（GDScript，与 pressure_params.json 映射见接入说明 §2）：
//   mat.set_shader_parameter("red_retain", 1.0 - clamp(t / 20.0, 0.0, 1.0))
//   mat.set_shader_parameter("posterize_amount", clamp((t - 20.0) / 80.0 * 0.5, 0.0, 0.5))
// ================================================================

// ---- 三通道保留度 ----
// retain = 1.0：该通道原样保留；retain = 0.0：该通道被灰白化（混入灰度基准）。
// 设计语义（W3.3 参数表）：red_retain 1→0（20s 归零）；green_retain 1→0
//   （25s 起每 5s -0.25，40s 归零）；blue_retain 1→0.8（保留冷蓝+灰白基调）。
uniform float red_retain : hint_range(0.0, 1.0) = 1.0;
uniform float green_retain : hint_range(0.0, 1.0) = 1.0;
uniform float blue_retain : hint_range(0.0, 1.0) = 1.0;

// ---- Posterize（色调分离 / 减色量化）----
// posterize_amount：量化强度（0.0 = 关闭；1.0 = 完全量化为 posterize_levels 个色阶）。
// pressure_params.json：20s 起 0→0.50，levels 恒 16 —— 数字纹理感。
uniform float posterize_amount : hint_range(0.0, 1.0) = 0.0;
uniform float posterize_levels : hint_range(2.0, 32.0) = 16.0;

void fragment() {
    vec3 col = texture(SCREEN_TEXTURE, UV).rgb;

    // 1) 通道保留：保留度低的通道向灰度基准混入（retain=0 完全灰白化）。
    //    用一次 dot 算亮度再按通道 mix，无分支、全通道并行。
    float gray = dot(col, vec3(0.299, 0.587, 0.114));
    col = mix(vec3(gray), col, vec3(red_retain, green_retain, blue_retain));

    // 2) Posterize：先量化再按强度混合（posterize_amount=0 时 mix 占比 0，等效关闭）。
    //    floor 量化取低阶，避免 round 带来的中间带闪烁。
    float step_size = 1.0 / posterize_levels;
    vec3 quantized = floor(col / step_size) * step_size;
    col = mix(col, quantized, posterize_amount);

    COLOR = vec4(col, 1.0);
}
