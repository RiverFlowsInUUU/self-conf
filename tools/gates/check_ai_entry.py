#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""AI 入口完整性 —— 保证「换任何 AI 都能维护本仓」。

守三件事（2026-10-08 立，因入口从 pi 专有的 SKILL.md 改为通用 AGENTS.md）：

  ① **AGENTS.md 存在且在仓库根** —— 它是唯一真源（事实标准：60k+ 项目、
     Linux Foundation 托管，Codex / Cursor / Amp / Jules / Factory 共同推动）。

  ② **各 AI 工具的约定文件都存在**，且**是指针不是副本**
     （CLAUDE.md · GEMINI.md · .cursorrules · .github/copilot-instructions.md）。
     ⚠️ 判定「指针 vs 副本」：指针必须**包含指向 AGENTS.md 的链接**，
     且**体积远小于** AGENTS.md。若某天有人把全文拷进去，体积会接近 ⇒ 报错。
     为什么不用软链：本机 `core.symlinks=false`，git 会把软链存成**完整副本**。

  ③ **指针里的红线与 AGENTS.md 不矛盾**（都提到「两份形态」「生成物」「门禁」）。
     防的是「指针说 A、真源说 B」——那比只有一个文件更糟。

退出码：0 = 通过 · 1 = 违规 · 2 = 环境不达标（cwd 不对）
"""
import io
import os
import re
import sys

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))

MAIN = "AGENTS.md"
# 各 AI 工具的约定入口（都应有，且都是薄指针）
POINTERS = ["CLAUDE.md", "GEMINI.md", ".cursorrules",
            ".github/copilot-instructions.md"]

# 指针里必须内联的关键红线（关键词）
MUST_MENTION = ["AGENTS.md", "verify_all", "生成物"]

# ── 体积与内容纪律（2026-10-08 依据外部研究补）────────────────────────
# 事实来源：
#   · ETH Zurich（arXiv 2602.11988）：context files 平均**增加 20%+ 推理成本**，
#     且**不普遍提升成功率**；"repository overviews 无益 —— agent 自己读代码"；
#     结论：**只写最小必要要求**（unnecessary requirements make tasks harder）。
#   · GitHub 分析 2500+ agents.md：primary failure mode 是**含糊**；
#     有效的文件把**可执行命令放前面**、用**代码示例**而非描述、设**明确边界**；
#     覆盖六域：commands / testing / structure / style / git / boundaries。
#   · 实践建议：**< 150 行**（Codex 上限 32 KiB combined）。
MAIN_MAX_LINES = 150

# 六域关键词（各至少要能对上一处，否则说明该域缺失）
SIX_AREAS = {
    "命令": ["verify_all", "python"],
    "测试/门禁": ["门禁", "verify_all", "退出码"],
    "结构": ["tools/", "surge/", "profiles"],
    "风格": ["注释", "真源", "生成物"],
    "git/流程": ["CI", "提交", "PR", "发版"],
    "边界": ["从不要", "从不", "红线", "禁止", "🚫"],
}


def main():
    if not os.path.isfile(os.path.join(ROOT, "surge", "profiles", "routing.conf")):
        print("❌ 不在仓库根 —— 环境不达标")
        return 2

    bad = []

    # ① 真源存在
    mp = os.path.join(ROOT, MAIN)
    if not os.path.isfile(mp):
        print("❌ 缺 %s —— AI 入口不存在" % MAIN)
        return 1
    main_txt = io.open(mp, encoding="utf-8").read()
    main_size = len(main_txt)

    # ② 每个约定文件存在且是薄指针
    for name in POINTERS:
        p = os.path.join(ROOT, name.replace("/", os.sep))
        if not os.path.isfile(p):
            bad.append("缺 %s —— 用该工具的 AI 将读不到入口" % name)
            continue
        t = io.open(p, encoding="utf-8").read()
        if not re.search(r"\]\([^)]*AGENTS\.md\)", t) and "AGENTS.md" not in t:
            bad.append("%s 里没有指向 AGENTS.md 的引用 —— 不是指针" % name)
        # 体积守卫：指针不该超过真源的 40%
        if len(t) > main_size * 0.4:
            bad.append("%s 体积 %d 字节 ≈ AGENTS.md 的 %d%% —— 疑似把全文拷进去了"
                       "（指针应远小于真源，否则又是多份要同步的副本）"
                       % (name, len(t), 100 * len(t) // main_size))
        for kw in MUST_MENTION:
            if kw not in t:
                bad.append("%s 缺关键红线关键词 `%s`" % (name, kw))

    # ③ 真源自身必须提到「换任何 AI 都能用」的机制说明
    if "唯一真源" not in main_txt or "薄指针" not in main_txt:
        bad.append("%s 里没有说明「指针机制」—— 后人会不知道这些文件是什么" % MAIN)

    # ④ 体积纪律（研究：过长会推高成本且不提升成功率）
    n_lines = len(main_txt.splitlines())
    if n_lines > MAIN_MAX_LINES:
        bad.append("%s 有 %d 行 > %d 行上限 —— 研究（ETH Zurich / GitHub 2500 仓）显示"
                   "：过长的 context file 只增加推理成本，不提升成功率。"
                   "把「agent 能自己看出来的」（目录结构、机制描述、已修好的坑）删掉，"
                   "只留「推不出来的」（命令、边界、易错点）"
                   % (MAIN, n_lines, MAIN_MAX_LINES))

    # ⑤ 六域覆盖（GitHub 分析：缺任一域是第二常见的失败模式）
    miss = [k for k, kws in SIX_AREAS.items() if not any(w in main_txt for w in kws)]
    if miss:
        bad.append("%s 缺这些核心域：%s（GitHub 2500 仓分析：缺域是第二常见失败模式）"
                   % (MAIN, " / ".join(miss)))

    # ⑥ 命令要在**前半部分**（研究：把可执行命令放前面，agent 会频繁引用）
    _lines = main_txt.splitlines()
    head = chr(10).join(_lines[:len(_lines) // 2])
    if "verify_all" not in head:
        bad.append("%s 的**前半部分**没有可执行命令 —— 研究建议命令放在前部"
                   "（agent 会频繁引用）" % MAIN)

    print("AI 入口完整性（%s + %d 个工具指针）" % (MAIN, len(POINTERS)))
    print("-" * 78)
    if bad:
        for b in bad:
            print("  NG %s" % b)
        print("-" * 78)
        print("入口不完整 %d 处" % len(bad))
        return 1
    print("  OK %s（%d 字节）· 指针 4 个，均薄且含关键红线" % (MAIN, main_size))
    print("  OK 任一 AI 工具（Codex/Cursor/Copilot/Claude/Gemini）都能找到入口")
    print("-" * 78)
    return 0


if __name__ == "__main__":
    sys.exit(main())
