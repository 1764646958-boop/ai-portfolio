# -*- coding: utf-8 -*-
"""
P1 · 资产质量评估框架 —— 常数额外线回溯校准 demo
================================================
目的：给 k（收缩平衡常数）、β（探索系数）、α（生态增益权重）三个常数一个「可推理、可复现」的取值方法，
     而不是拍脑袋硬给。方法基于离线历史日志（或人工合成的带真值数据）做回溯。

依赖：纯 Python（仅标准库 random），无第三方依赖。seed 固定，结果可复现。

原理一句话：
  · k  —— 用「只看前 N0 个样本的冷启动估计」预测「最终真实质量」的准确度来标定；k 越小越早信任行为。
  · β  —— 用 UCB 在历史回流上重放，权衡「平均质量收益」与「长尾获得机会数 / 收益损失（regret）」来标定。
  · α  —— 用「稀缺增益」重算分发，看「生态多样性（Gini）」抬升与「命中质量」损失的拐点来标定。

运行：python p1_backtest.py
"""

import random, math
from itertools import product

SEED = 42
random.seed(SEED)


# ----------------------------------------------------------------------
# 0) 构造一份「带真值」的模拟历史日志
#    asset: 有真实质量 q_true、内容先验 content（≈q_true+噪声）、行为证据 N、失败率、
#           所属需求簇 cluster、niche。
# ----------------------------------------------------------------------
def build_corpus(n=200):
    assets = []
    clusters = ["办公", "开发", "金融", "医疗", "生活", "影视", "法律", "教育"]
    for i in range(n):
        cluster = clusters[i % len(clusters)]
        # 真实质量：偏态分布，少数头部偏高，长尾在 0.4~0.8
        q_true = min(0.98, max(0.4, random.gauss(0.62, 0.16)))
        # 内容先验 = 真实质量 + 噪声（内容信号只能「近似」反映质量）
        content = float(np_clip(q_true + random.gauss(0, 0.12), 0.1, 1.0))
        # 行为证据量 N：头部（高真实质量者）曝光多，长尾少 —— 用真实质量做偏置的指数分布
        lam = 8 + 60 * (q_true - 0.4)
        N = int(random.expovariate(1.0 / lam)) + 1
        # 失败率与质量相关
        fail = float(np_clip(0.2 - 0.15 * q_true + random.gauss(0, 0.03), 0.01, 0.5))
        # 需求覆盖缺口：稀疏 niche 更高（生活/影视/医疗这些 niche 供给薄）
        gap = 0.75 if cluster in ("生活", "影视", "医疗") else 0.2
        # 稀缺度：真正稀疏 niche 的资产竞争者更少 → 稀缺度更高
        base_scarcity = {"生活": 0.85, "影视": 0.9, "医疗": 0.8}.get(cluster, 0.35)
        scarcity = float(np_clip(base_scarcity + random.gauss(0, 0.1), 0.1, 0.95))
        assets.append(dict(id=i, q_true=q_true, content=content, N=N, fail=fail,
                           cluster=cluster, gap=gap, scarcity=scarcity,
                           # 真实质量决定「能否胜任」→ 用于重放时的即时反馈
                           success_p=q_true))
    return assets


def np_clip(x, lo, hi):
    return max(lo, min(hi, x))


# ----------------------------------------------------------------------
# 1) k 的离线校准：收缩估计对「真实质量」的预测力
#    Q̂(N) = w·bar_behavior + (1-w)·content,  w = N/(N+k)
#    只用「前 N0 个样本」去估，看它预测真实质量 q_true 准不准。
# ----------------------------------------------------------------------
def calibrate_k(assets, n0=12, ks=None):
    if ks is None:
        ks = [5, 10, 20, 40, 60, 90, 140, 200]
    rows = []
    for k in ks:
        ests = []
        qs = []
        for a in assets:
            if a["N"] < n0:
                continue  # 无足量证据的资产不适合做「前 N0 预测」的标定
            # 只用前 n0 个样本的「累计成功率」作为行为观测（模拟：均值≈真实质量+噪声）
            sample_bar = float(np_clip(a["q_true"] + random.gauss(0, 0.06), 0.0, 1.0))
            w = n0 / (n0 + k)
            q_hat = w * sample_bar + (1 - w) * a["content"]
            ests.append(q_hat)
            qs.append(a["q_true"])
        # 用皮尔逊相关系数衡量预测力（线性近似，免装 numpy）
        corr = pearson(ests, qs)
        # RMSE
        rmse = sqrt(mean([(e - q) ** 2 for e, q in zip(ests, qs)]))
        rows.append((k, corr, rmse))
    rows.sort(key=lambda r: -r[1])  # 相关性越高越好
    return rows


def calibrate_beta(assets, betas=None, horizon=4000):
    """β 的离线校准：UCB 在历史回流上重放。
    权衡：平均质量收益 vs 长尾(低N)资产获得≥1次机会的数量 vs regret(与「总挑真最优」的期望差距)。"""
    if betas is None:
        betas = [0.05, 0.15, 0.3, 0.6, 1.0]
    rows = []
    for beta in betas:
        N = {a["id"]: 0 for a in assets}
        # Q̂ 用内容先验做初值（冷启动）
        Q = {a["id"]: a["content"] for a in assets}
        total_rew = 0.0
        tails_touched = set()
        t = 0
        for _ in range(horizon):
            t += 1
            # UCB 路由分
            best = max(assets, key=lambda a: Q[a["id"]] + beta * math.sqrt(math.log(t) / (N[a["id"]] + 1)))
            # 取反馈（成功=1/失败=0 的二项）
            rew = 1 if random.random() < best["success_p"] else 0
            total_rew += rew
            N[best["id"]] += 1
            # 贝叶斯收缩式更新
            w = N[best["id"]] / (N[best["id"]] + 60)
            Q[best["id"]] = w * (Q[best["id"]] * 0.7 + rew * 0.3) + (1 - w) * best["content"]
            if best["N"] <= 20:  # 长尾（初始证据低）
                tails_touched.add(best["id"])
        avg_reward = total_rew / horizon
        rows.append((beta, avg_reward, len(tails_touched)))
    return rows


def calibrate_alpha(assets, alphas=None, n_needs=400):
    """α 的离线校准：稀缺增益把「正好契合的稀缺长尾」抬起来，看多样性(Gini)与命中质量的平衡。

    结构：每个需求来自某个 niche；候选的「关联度 sim」= 同一 niche 高、跨 niche 低。
    稀缺度 = 同 niche 竞争者少。α 越大，越倾向抬举稀缺长尾 → 多样性↑；但超过拐点会
    开始选中「稀缺但不够契合」的资产 → 命中质量(平均 sim)↓。找「多样性改善且质量未损」的拐点。
    """
    if alphas is None:
        alphas = [0.0, 0.05, 0.1, 0.15, 0.2, 0.3, 0.5]
    rows = []
    for alpha in alphas:
        picks = []
        fit_sum = 0.0
        for _ in range(n_needs):
            # 需求来源：随机挑一个 niche，需求与真实最契合的那类资产对齐
            demand_cluster = random.choice(["办公", "开发", "金融", "医疗", "生活", "影视", "法律", "教育"])
            cands = []
            for a in assets:
                # 关联度：同 niche 高（0.6~0.95），不同 niche 低（0.1~0.3）
                if a["cluster"] == demand_cluster:
                    sim = float(np_clip(0.6 + random.gauss(0, 0.12), 0.3, 0.98))
                else:
                    sim = float(np_clip(random.gauss(0.18, 0.08), 0.05, 0.4))
                base = a["q_true"]
                gain = 1 + alpha * a["scarcity"] * a["gap"]
                cands.append((sim * base * gain, sim, a))
            # 命中 = 评分最高者；「命中质量」= 该资产对需求的关联度（越高越贴合）
            _, pick_sim, pick = max(cands, key=lambda x: x[0])
            picks.append(pick["id"])
            fit_sum += pick_sim
        gini = gini_of_counts(picks)
        avg_fit = fit_sum / n_needs
        rows.append((alpha, round(gini, 4), round(avg_fit, 4)))
    return rows


# --------------------- 统计辅助 ---------------------
def pearson(xs, ys):
    n = len(xs)
    if n < 2:
        return 0.0
    mx = sum(xs) / n
    my = sum(ys) / n
    cov = sum((a - mx) * (b - my) for a, b in zip(xs, ys))
    vx = sum((a - mx) ** 2 for a in xs)
    vy = sum((b - my) ** 2 for b in ys)
    if vx == 0 or vy == 0:
        return 0.0
    return cov / math.sqrt(vx * vy)


def mean(xs):
    return sum(xs) / len(xs) if xs else 0


def sqrt(x):
    return x ** 0.5


def gini_of_counts(items):
    from collections import Counter
    c = Counter(items)
    counts = sorted(c.values())
    n = len(counts)
    if n == 0:
        return 0.0
    cum = 0
    total = sum(counts)
    G = 0
    for i, x in enumerate(counts, start=1):
        cum += x
        G += (n + 1 - i) * x
    G = (n + 1 - 2 * G / total) / n if total else 0
    return G


# --------------------- 运行并输出 ---------------------
def fmt_row(headers, row):
    return "  ".join(f"{v:<10}" for v in row)


def report_calibration():
    assets = build_corpus()
    print("=" * 78)
    print("P1 · 常数额外线回溯校准 demo（seed=42，可复现；数据为带真值的合成日志）")
    print("=" * 78)

    print("\n[1] k（收缩平衡常数）：最小化「冷启动误差」，最大化「对真实质量的预测力」")
    print(f"    {'k':<8}{'相关系数':<12}{'RMSE':<12}  解读")
    ks = calibrate_k(assets)
    for i, (k, corr, rmse) in enumerate(ks):
        note = ""
        if i == 0:
            note = "  <- 推荐：预测力最强"
        print(f"    {k:<8}{corr:<12.4f}{rmse:<12.4f}{note}")

    print("\n[2] β（探索系数）：权衡「平均质量收益」与「长尾被探索的机会数」")
    print(f"    {'β':<8}{'平均收益':<12}{'长尾触达(个)':<14}  解读")
    bs = calibrate_beta(assets)
    for beta, avg_rew, tails in bs:
        note = ""
        if tails >= 30 and avg_rew >= 0.62:
            note = "  <- 推荐区间：探索够且收益不塌"
        print(f"    {beta:<8}{avg_rew:<12.4f}{tails:<14}{note}")

    print("\n[3] α（生态增益权重）：看「多样性（Gini↓为佳）抬升」与「命中质量损失」的拐点")
    print(f"    {'α':<8}{'Gini':<12}{'平均命中质量':<14}  解读")
    arows = calibrate_alpha(assets)
    base_fit = arows[0][2]  # α=0 时的命中质量
    # 推荐 α：在「命中质量不损」（≥ 基线-0.015）前提下，选 Gini 最低（最均衡）者
    ok = [r for r in arows if r[2] >= base_fit - 0.015]
    rec = min(ok, key=lambda r: r[1]) if ok else arows[0]
    for alpha, gini, fit in arows:
        note = "  <- 推荐：多样性最佳且质量未损" if (alpha, gini, fit) == rec else ""
        print(f"    {alpha:<8}{gini:<12.4f}{fit:<14.4f}{note}")
    print(f"    → 推荐 α ≈ {rec[0]}（Gini={rec[1]:.4f}，命中质量={rec[2]:.4f}）")

    print("\n" + "=" * 78)
    print("小结：以上给出的是「如何用离线日志标定常数」的可复现 demo。")
    print("实际落地时，用真实历史日志替换合成数据，即可得到平台自己的 k/β/α 推荐值。")
    print("=" * 78)


if __name__ == "__main__":
    report_calibration()
