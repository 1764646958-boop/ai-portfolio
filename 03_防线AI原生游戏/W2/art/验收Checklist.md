# 《防线》美术验收 Checklist（每张图必过）

> 依据：美术产出方案 v3.1 §7.6（2026-08-25 建立）
> 用法：A 的 780M 跑自动化（5 项），人工只看 2 项（1 + 5）。逐图填写，未过不入库。

## 验收 8 项

| # | 类别 | 检查项 | 判定标准 | 方式 |
|---|---|---|---|---|
| 1 | 角色 | 五官比例（仅 protagonist） | 眼距、鼻位、嘴位与参考图肉眼一致 | **人工** |
| 2 | 角色 | 二次元特征 | 动漫大眼 + 动漫画法，非写实 | 自动化（CLIP anime ≥ 0.85） |
| 3 | 色调 | 主色在 12 色卡内 | 主色 ΔE00 < 8 | 自动化 |
| 4 | 色调 | 光影方向与场景匹配 | 阴影误差 < 15° | 自动化 |
| 5 | 整体 | 整体违和感 | "放旁边看不出来" = 通过 | **人工** |
| 6 | 角色 | 旧友不露正脸 | InsightFace 检测不到 face landmarks | 自动化（+人工复检模糊/遮挡） |
| 7 | AI 形态 | 恐怖谷评分 | 评分 ≥ 0.7（对称度 < 5% + 纹理均匀度 < 15%） | 自动化 |
| 8 | 整体 | 无画面崩坏 | 手指 5 根、脸部无 artifact、构图完整（Laplacian ≥ 100） | 自动化 |

## 角色类专用

| 角色 | 额外校验 |
|---|---|
| 主人公（头像+4 表情） | InsightFace landmarks 眼距偏差 < 5%；CLIP anime ≥ 0.85；Laplacian ≥ 100 |
| 旧友（背/侧/模糊/遮挡） | OpenPose 检测 ≥ 10 关键点；InsightFace 检测不到正脸；遮挡版右侧 30% 被 UI 覆盖 |
| AI 形态（正常/恐怖谷/故障） | 恐怖谷评分 ≥ 0.7；故障版含明显 glitch |

## 场景类专用

- 分辨率 1920×1080（±2px）；文件 ≤ 500KB（VRAM 压缩后）
- 主色调在 12 色色彩卡内；异常变体与正常版 ΔE00 在 8-15 范围

## 逐图验收表（复制使用）

| 图 | 1人工 | 2 | 3 | 4 | 5人工 | 6 | 7 | 8 | 入库? |
|---|---|---|---|---|---|---|---|---|---|
| （示例）protagonist_neutral | ✅ | ✅ | ✅ | ✅ | ✅ | — | — | ✅ | ✅ |
| | | | | | | | | | |

## 自动化脚本调用

```bash
# W3 D3 跑通后使用（character_pipeline.py 内置 6 项校验）
python character_pipeline.py --character protagonist --variants neutral smiling confused determined
python character_pipeline.py --character all --batch-size 3   # 批量 3 候选/变体
# 失败图 → user://failed/ ；报告 → user://reports/
```
