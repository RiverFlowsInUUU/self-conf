#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""AI 入口完整性 —— 保证「换任何 AI 都能维护本仓」。

守三件事（2026-10-08 立，因入口从 pi 专有的 skill/SKILL.md 改为通用 AGENTS.md）：

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
