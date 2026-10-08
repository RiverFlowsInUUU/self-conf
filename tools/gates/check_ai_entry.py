#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""AI 入口完整性 —— 保证「换任何 AI 都能读同一份文档」。

⚠️ 2026-10-08 修正（此前做错了）：我原以为「每个 AI 工具的约定文件名都要有一份」，
于是造了 CLAUDE.md / GEMINI.md / .cursorrules / copilot-instructions.md 四份
—— **但它们是同一份内容的副本，只有标题行不同**。那是重复，不是兼容。

事实核查（各家官方文档）：
  · Claude Code：**能直接读 AGENTS.md**（"without adding a CLAUDE.md, an import,
    or a setting"）。且官方明确警告：**仓库里有 CLAUDE.md 时，Claude 只读 CLAUDE.md、
    不读 AGENTS.md** ⇒ 那个「指针 CUAUDE.md」不只是多余，它会**屏蔽**真源。
  · Cursor：官方文档「AGENTS.md … as an alternative to `.cursor/rules`」，且支持嵌套。
  · GitHub Copilot：「Copilot coding agent now supports AGENTS.md」（2025-08-28）。
  · Gemini CLI：**默认只读 GEMINI.md**（AGENTS.md 不在默认 context.fileName 列表里，
    见 gemini-cli issue #28227）⇒ 这是**唯一**需要一行指针的。

⇒ 正确做法：**一个 AGENTS.md 是真源；只有 Gemini CLI 需要一个不复制内容的一行指针。**

本判据守：
  ① AGENTS.md 存在、在根、且**内容充实**（不是空壳）
  ② **不应存在**会被优先读取、从而屏蔽真源的文件（CLAUDE.md 是典型）
  ③ GEMINI.md（若存在）必须是**纯指针**——不得复制真源内容
  ④ 体积与六域纪律（研究：过长只增成本；缺域是第二常见失败模式）
  ⑤ 嵌套 AGENTS.md 的行数上限，且不得重复根文件

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
SHADOWS = ["CLAUDE.md", ".cursorrules", ".github/copilot-instructions.md"]

# 唯一允许存在的指针（Gemini CLI 默认不读 AGENTS.md）
POINTERS = ["GEMINI.md"]

MAIN_MAX_LINES = 150
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
    mp = os.path.join(ROOT, MAIN)
    if not os.path.isfile(mp):
        print("❌ 缺 %s —— AI 入口不存在" % MAIN)
        return 1
    main_txt = io.open(mp, encoding="utf-8").read()

    # ② 屏蔽真源的文件
    for name in SHADOWS:
        p = os.path.join(ROOT, name.replace("/", os.sep))
        if os.path.exists(p):
            bad.append("存在 %s —— 该文件会被对应工具**优先于 AGENTS.md** 读取，"
                       "从而屏蔽真源（Claude Code 官方：有 CLAUDE.md 时只读 CLAUDE.md）。"
                       "删掉它，让工具直接读 AGENTS.md" % name)

    # ③ 指针必须是纯指针（不复制内容）
    for name in POINTERS:
        p = os.path.join(ROOT, name)
        if not os.path.isfile(p):
            continue
        t = io.open(p, encoding="utf-8").read()
        if "AGENTS.md" not in t:
            bad.append("%s 里没有指向 AGENTS.md 的引用" % name)
        # 纯指针：体积应远小于真源
        if len(t) > len(main_txt) * 0.35:
            bad.append("%s 体积 %d 字节 ≈ AGENTS.md 的 %d%% —— 疑似复制了内容。"
                       "指针只能有「去读 AGENTS.md」一句，"
                       "复制就会产生第二份要同步的东西"
                       % (name, len(t), 100 * len(t) // len(main_txt)))
        for kw in ("verify_all",):
            if kw in t:
                bad.append("%s 里出现了 `%s` —— 那是真源的内容，指针不该重复"
                           % (name, kw))

    # ④ 体积与六域
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

    # ⑤ 嵌套文件
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

    print("AI 入口完整性（唯一真源 %s）" % MAIN)
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
    for name in POINTERS:
        p = os.path.join(ROOT, name)
        if os.path.isfile(p):
            print("  OK 指针 %s（%d 字节，纯指针）"
                  % (name, os.path.getsize(p)))
    print("  OK 无屏蔽真源的文件 · 任一 AI 读同一份 %s" % MAIN)
    print("-" * 78)
    return 0


if __name__ == "__main__":
    sys.exit(main())
