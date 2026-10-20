# 《防线》12 色色彩卡 + Prompt 锚定词（锁定版）

> 依据：美术产出方案 v3.1 §4.1/§4.2（已定稿，2026-08-25 锁定）
> 用途：A（云端出图参数）+ B（叙事 prompt 撰写）共用基准；所有生成图主色必须落在 12 色内。

## 一、风格锚定词（所有 prompt 必须包含）

**通用前缀（每次生图必带）：**
```
masterpiece, best quality, anime style, AI-drawn aesthetic, modern urban setting, soft lighting, warm color palette, detailed eyes, beautiful detailed face, 7-8 head ratio
```

**负面提示词（随角色切换，注意第一幕不加 horror）：**
```
photorealistic, 3d render, chibi, galgame UI, horror (1st half only), blood, violence, jump scare
```

## 二、12 色色彩卡（按用途锁定）

### 暖色 6 色 —— 第一幕主调
| 色名 | 色值 | 用途 |
|---|---|---|
| 暖黄 | `#F5E1A4` | 场景主光 |
| 柔粉 | `#FFD1B8` | 角色肤色 |
| 米白 | `#F8F0E5` | AI 界面底色 |
| 暖橙 | `#FFA869` | AI 界面强调 |
| 暖棕 | `#8B6F5C` | 场景阴影 |
| 暖红 | `#D4795A` | 战斗 HUD 警告 |

### 冷色 4 色 —— 第三幕主调 + 战斗 HUD + 假记忆
| 色名 | 色值 | 用途 |
|---|---|---|
| 冷蓝 | `#4A6B8A` | 战斗边框 / 假记忆 |
| 深蓝 | `#2D4A6B` | 战斗最终压迫 |
| 灰白 | `#C5CCD4` | AI 形态皮肤 |
| 冷青 | `#6B8BAA` | 信号干扰 |

### 中性 2 色 —— UI 框架
| 色名 | 色值 | 用途 |
|---|---|---|
| 深色 | `#2A2A35` | 主菜单背景 |
| 米卡 | `#F0E5D0` | 记忆卡片背景 |

## 三、三幕色彩节奏（AI 界面/碎片配色基准）

| 幕 | 主色调 | AI 界面 | 真实碎片 | 假碎片 |
|---|---|---|---|---|
| 第一幕 | 暖黄/柔粉 | 暖橙/米白 | 暖色残留 | — |
| 第二幕 | 暖冷交织 | 冷蓝闪烁 | 暖色褪色 | 微冷蓝 |
| 第三幕 | 冷蓝/灰白 | 冷蓝/灰白 | 暖色闪现 | 纯冷蓝 |

## 四、自动化校验锚点

- 主色 ΔE00 < 8（与色卡比对，InsightFace/CLIP 脚本校验）
- 阴影方向误差 < 15°
- 验收脚本：`character_pipeline.py` 内 6 项 checklist（W3 D3 跑通）
