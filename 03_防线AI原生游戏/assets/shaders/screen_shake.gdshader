shader_type canvas_item;

// ================================================================
// 《防线》视觉压迫 Shader · 画面抖动（UV 偏移采样版）
// ----------------------------------------------------------------
// 用途（W3.4）：记忆被「外力捶了一下」的物理感 —— 拖拽假碎片 / 被攻击时
//   由 GDScript 置 shake_amount = 0.03，之后帧间 lerp 衰减（事件驱动，
//   不走 90s 时间轴，见 pressure_params.json curves.shake_amount）。
//
// 「顶点位移」vs「UV 偏移」的落地决策（W1 选题报告写顶点位移，此处修正）：
//   1) 顶点位移（VERTEX += offset）：画面四角会露底（露出下层画面/黑边），
//      且与全屏 ColorRect 的锚点/裁剪相互牵连，非 16:9 窗口还需额外对齐；
//   2) UV 偏移（本实现）：整体平移采样 SCREEN_TEXTURE，无露底，且与
//      color_grade / tunnel_vision 同为「采样阶段出效果」，W4.4 合并单 pass
//      时无需额外 pass 成本。
//   详见 W3\shaders\三项Shader接入说明.md §4（含两方案对比记录）。
//
// 挂载方式：全屏 ColorRect + ShaderMaterial（叠在战斗画面上层，同 color_grade）。
// 驱动示例（GDScript，事件驱动 + 帧间衰减）：
//   mat.set_shader_parameter("shake_amount", 0.03)          # 触发
//   # _process 里：shake = lerp(shake, 0.0, 0.2)；再写回 uniform
// ================================================================

// 抖动幅度（UV 单位，0.03 ≈ 屏幕宽度 3%）。压力参数表事件驱动峰值：0.03。
uniform float shake_amount : hint_range(0.0, 0.10) = 0.0;

// 抖动种子：不同战斗时段取不同值，让抖动模式不重复（避免帧级 hash 撞车）。
uniform float shake_seed : hint_range(0.0, 100.0) = 0.0;

void fragment() {
    // 1) 帧粒度随机扰动：以 60Hz 帧号 + seed 作 hash 输入，
    //    帧内稳定（无闪烁）、帧间跳变（高频抖动感）。
    float t = floor(TIME * 60.0);
    vec2 rnd = vec2(
        fract(sin(t * 12.9898 + shake_seed * 17.0) * 43758.5453),
        fract(sin(t * 78.2330 + shake_seed * 31.7) * 43758.5453)
    );
    rnd = rnd * 2.0 - 1.0;  // [-1, 1]

    // 2) 幅度按宽高比修正：水平和垂直方向视觉位移一致。
    //    SCREEN_PIXEL_SIZE.x/y = 1/屏宽 / 1/屏高 → y/x = 屏宽/屏高。
    vec2 offset = rnd * shake_amount * vec2(1.0, SCREEN_PIXEL_SIZE.x / SCREEN_PIXEL_SIZE.y);

    // 3) 偏移采样屏幕纹理 + CLAMP 防越界。边缘浅拉伸可接受：
    //    抖动 ≤0.03 时，四周拉伸在侵蚀/隧道遮罩下几乎不可见。
    COLOR = texture(SCREEN_TEXTURE, clamp(UV + offset, vec2(0.0), vec2(1.0)));
}
