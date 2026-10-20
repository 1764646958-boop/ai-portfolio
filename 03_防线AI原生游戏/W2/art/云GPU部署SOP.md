# 云 GPU 部署 SOP（AutoDL RTX 4090）· 可执行版

> 依据：美术产出方案 v3.1 §6.5 + §2.3/§2.4（2026-08-25 整理）
> 目标：今天（W3 D2）完成环境补做 + 3 张计时实测；全程成本目标 ¥10-15 封顶。
> 纪律：随用随关（按小时计费）；所有生成统一云端执行；C 的 4050 不参与生成。

---

## 第 1 步：租机（约 10 分钟）

1. 打开 AutoDL 控制台（cloud.autodl.com）→ 注册/登录（需实名）
2. 租用 GPU：筛选 **RTX 4090**（¥1.98/h，24GB）
   - 备选：3090（¥1.39/h，速度约 45%）；**不要** H800/A800/MTT（生态/价格不划算）
3. **镜像选择（关键）**：搜"ComfyUI"或"Forge"现成镜像（社区镜像，含 SDXL 环境）
   - 优先带 Illustrious / Animagine 的镜像，可省模型上传
4. 计费方式：按量计费 → 开机
5. 记下：**SSH 登录指令**（`ssh -p <端口> root@<IP>`）和 root 密码（控制台复制）
   - ⚠️ AutoDL 的 SSH 端口不是 22，以控制台显示为准

## 第 2 步：模型部署（网盘秒传，约 15-30 分钟）

需要上传的模型清单：

| 模型 | 用途 | 格式 |
|---|---|---|
| Illustrious XL 1.1 | 基础模型（主力） | FP8（约 6-7GB） |
| Animagine XL 4.0 Opt Clear | 备选模型（概念稿/变体） | FP8 |
| IP-Adapter FaceID Plus v2 | 主人公面部一致性 | — |
| ControlNet OpenPose XL | 旧友姿态控制 | **FP8** |
| Detail Tweaker XL | 细节增强 LoRA | — |
| 4x-UltraSharp | 出图后放大 | — |

上传方式（二选一）：
- **AutoDL 网盘（推荐）**：本机上传模型到 AutoDL 网盘 → 实例内 `unzip /root/autodl-tmp/...` 秒传
- 镜像自带则跳过（社区镜像常含 Illustrious）

放置路径（ComfyUI 惯例）：
```
/models/checkpoints/    ← Illustrious、Animagine
/models/loras/          ← Detail Tweaker 等 LoRA
/models/controlnet/     ← OpenPose FP8
/models/ipadapter/      ← IP-Adapter FaceID
/models/upscale_models/ ← 4x-UltraSharp
```

## 第 3 步：SSH 隧道 + WebUI（本机操作）

```bash
# Forge WebUI 默认 7860；ComfyUI 默认 8188 —— 按实际改端口
ssh -p <AutoDL端口> -L 7860:127.0.0.1:7860 root@<服务器IP>
# 保持此终端开着；浏览器打开 http://127.0.0.1:7860 即可操作（体验与本地一致）
```

验证：浏览器能打开 WebUI → 环境就绪 ✅

## 第 4 步：3 张计时实测（本次核心目标）

按《云4090计时实测记录表.md》跑 3 张图：
1. 角色头像 1024×1024（Steps 30-35 / CFG 5-6）
2. 角色立绘 1024×1536（Steps 28-32 / CFG 5-7）
3. 场景 1920×1080（Steps 28-32 / CFG 6-7）
各测 3 次取平均 → 回填表格 → **用真实速度校准 W3-W5 排期**

## 第 5 步：批量出图（正式批，W3/W4 用，今天不强制）

```bash
# character_pipeline.py（W3 D3 跑通后）
python character_pipeline.py --character all --batch-size 3   # 夜间无人值守
# 场景走 ComfyUI workflow（1920×1080 → 4x 放大 → VRAM 压缩 ≤500KB）
```

## 第 6 步：下载与验收

```bash
# 结果打包（实例内）
cd /root/autodl-tmp && tar czf output.tar.gz output/
# 本机下载
scp -P <端口> root@<IP>:/root/autodl-tmp/output.tar.gz .
# 验收：A 的 780M 跑 CPU 型脚本（InsightFace/CLIP/ΔE00/Laplacian），通过才入库
```

## 第 7 步：关机纪律（省钱关键）

```bash
# 全部完成后 → AutoDL 控制台 → 关机（不是"停止计费"也要确认）
# 目标：本次全程 3-4 小时墙钟 ≈ ¥6-8；W3-W5 全部生成 ¥10-15 封顶
```

---

## 应急出图对策（仅当云端不可用时）

C 的 4050 临时跑：模型全 FP8（底座约 3.5GB）+ Forge 低显存模式 + **一次只挂一个插件栈**（按角色分栈加载，方案本就如此设计）。

## 常见问题

| 问题 | 解法 |
|---|---|
| SSH 连不上 | 端口用控制台给的（非 22）；确认实例开机 |
| WebUI 打不开 | 隧道命令端口与 WebUI 实际端口一致；检查 `-L` 参数 |
| 出图显存爆 | 切 FP8 + 低显存模式；batch 用 1 测试 |
| 模型加载失败 | 路径放错；对照第 2 步路径表 |
| 忘关机 | 控制台开"定时关机"（如 4 小时后），防漏 |
