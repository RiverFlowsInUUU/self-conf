#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""AI 入口唯一性 —— 保证「换任何 AI 都能读同一份文档」。

⚠️ 2026-10-08 修正（此前做错了）：我原以为「每个 AI 工具的约定文件名都要有一份」，
于是造了 CLAUDE.md / GEMINI.md / .cursorrules / copilot-instructions.md 四份
—— **但它们是同一份内容的副本，只有标题行不同**。那是重复，不是兼容。

⚠️ 2026-10-08 二次修正：曾把 GEMINI.md 当「唯一例外」保留（理由：Gemini CLI 默认
只读它），判定「纯指针即可」。**但保留一个工具专属入口本身就是问题** ——
它会被该工具**优先于** AGENTS.md 读取，于是真源被绕过，且多出一份要同步的东西。
事实核查（各家官方文档 / 源码）：
  · Claude Code：**能直接读 AGENTS.md**（"without adding a CLAUDE.md, an import,
    or a setting"）。且官方明确警告：**仓库里有 CLAUDE.md 时，Claude 只读 CLAUDE.md、
    不读 AGENTS.md**。
  · Cursor：官方文档「AGENTS.md … as an alternative to `.cursor/rules`」，且支持嵌套。
  · GitHub Copilot：「Copilot coding agent now supports AGENTS.md」（2025-08-28）。
  · Gemini CLI：源码 `DEFAULT_CONTEXT_FILENAME = 'GEMINI.md'`，AGENTS.md 不在默认
    `context.fileName` 列表里（issue #28227 仍 open，PR #24913 closed without merge）。
    ⇒ 确实读不到 AGENTS.md，**但那不是「要给它单独建一份」的理由** ——
    正确处置是**不建**：让读不到的工具读不到，而不是为它维护第二份入口。
    想用 Gemini CLI 的人，自己在 `~/.gemini/settings.json` 把 `AGENTS.md` 加进
    `context.fileName` 即可 —— 这是**用户侧的一行配置**，不该由本仓建文件来适配。

⇒ 正确做法：**AGENTS.md 是唯一入口，不做任何工具专属兼容。**
   任何工具专属入口文件（含指针）一律**不应存在** —— 它们要么屏蔽真源，
   要么制造第二份要同步的东西。

本判据守：
  ① AGENTS.md 存在、在根、且**内容充实**（不是空壳）
  ② **不应存在**工具专属入口文件（会被优先读取、从而屏蔽真源）
  ③ 体积与六域纪律（研究：过长只增成本；缺域是第二常见失败模式）
  ④ 嵌套 AGENTS.md 的行数上限，且不得重复根文件

退出码：0 = 通过 · 1 = 违规 · 2 = 环境不达标
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
# 嵌套 AGENTS.md（就近生效）。只在「该目录有独立工具链/约定」时加。
NESTED = ["clash/AGENTS.md"]

# ⚠️ 这些文件名会被各自工具**优先于 AGENTS.md** 读取 ⇒ 存在即屏蔽真源，视为违规。
#    （Claude Code 官方：有 CLAUDE.md 时只读它，不读 AGENTS.md）
#    ⚠️ GEMINI.md 同属此类：Gemini CLI 默认只读它、不读 AGENTS.md。
#       曾把它当「允许的指针」保留 —— 那是错的：保留即制造第二份入口。
SHADOWS = ["CLAUDE.md", ".cursorrules", ".github/copilot-instructions.md",
           "GEMINI.md", ".gemini/GEMINI.md", "AGENT.md"]

MAIN_MAX_LINES = 150
SIX_AREAS = {
    "命令": ["verify_all", "python"],
    "测试/门禁": ["门禁", "verify_all", "退出码"],
    "结构": ["self-conf-skills/", "surge/", "profiles"],
    "风格": ["注释", "真源", "生成物"],
    "git/流程": ["CI", "提交", "PR", "发版"],
    "边界": ["从不要", "从不", "红线", "禁止", "🚫"],
}


def main():
    if not os.path.isfile(os.path.join(ROOT, "surge", "profiles", "routing.conf")):
        print("❌ 不在仓库根 —— 环境不达标")
        return 2

    # ① 真源存在
    bad = []
    mp = os.path.join(ROOT, MAIN)
    if not os.path.isfile(mp):
        print("❌ 缺 %s —— AI 入口不存在" % MAIN)
        return 1
    main_txt = io.open(mp, encoding="utf-8").read()

    # ② 屏蔽真源的工具专属入口
    for name in SHADOWS:
        p = os.path.join(ROOT, name.replace("/", os.sep))
        if os.path.exists(p):
            bad.append("存在 %s —— 该文件会被对应工具**优先于 AGENTS.md** 读取，"
                       "从而屏蔽真源（Claude Code 官方：有 CLAUDE.md 时只读 CLAUDE.md；"
                       "Gemini CLI 同理只读 GEMINI.md）。"
                       "删掉它，让工具直接读 AGENTS.md" % name)

    # ③ 体积与六域
    n_lines = len(main_txt.splitlines())
    if n_lines > MAIN_MAX_LINES:
        bad.append("%s 有 %d 行 > %d 行上限 —— 研究（ETH Zurich arXiv 2602.11988 / "
                   "GitHub 2500 仓）显示：过长的 context file 只增加推理成本，"
                   "不提升成功率" % (MAIN, n_lines, MAIN_MAX_LINES))
    miss = [k for k, kws in SIX_AREAS.items() if not any(w in main_txt for w in kws)]
    if miss:
        bad.append("%s 缺这些核心域：%s（GitHub 2500 仓分析：缺域是第二常见失败模式）"
                   % (MAIN, " / ".join(miss)))
    lines = main_txt.splitlines()
    if "verify_all" not in chr(10).join(lines[:len(lines) // 2]):
        bad.append("%s 的**前半部分**没有可执行命令 —— 研究建议命令放在前部" % MAIN)

    # ④ 嵌套文件
    for nf in NESTED:
        np_ = os.path.join(ROOT, nf.replace("/", os.sep))
        if not os.path.isfile(np_):
            bad.append("缺嵌套 %s —— 该目录有独立生成链，agent 会改错文件" % nf)
            continue
        nt = io.open(np_, encoding="utf-8").read()
        if len(nt.splitlines()) > MAIN_MAX_LINES:
            bad.append("%s 有 %d 行 > %d 行上限"
                       % (nf, len(nt.splitlines()), MAIN_MAX_LINES))
        for cand in ("退出码：**0 = 全过", "改配置 = 改两份"):
            if cand in nt:
                bad.append("%s 重复了根 AGENTS.md 的内容（`%s`）"
                           % (nf, cand[:14]))

    print("AI 入口唯一性（唯一真源 %s，不做工具专属兼容）" % MAIN)
    print("-" * 78)
    if bad:
        for b in bad:
            print("  NG %s" % b)
        print("-" * 78)
        print("入口违规 %d 处" % len(bad))
        return 1
    print("  OK %s（%d 行）· 真源唯一" % (MAIN, n_lines))
    for nf in NESTED:
        np_ = os.path.join(ROOT, nf.replace("/", os.sep))
        if os.path.isfile(np_):
            print("  OK 嵌套 %s（%d 行）"
                  % (nf, len(io.open(np_, encoding="utf-8").read().splitlines())))
    print("  OK 无工具专属入口（%d 类已查）· 任一 AI 读同一份 %s"
          % (len(SHADOWS), MAIN))
    print("-" * 78)
    return 0


if __name__ == "__main__":
    sys.exit(main())
