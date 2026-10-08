#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""文档引用了**不存在的文件** —— 扫「已删文件 / 已删机制」的残留引用。

为什么有这个
────────────
本仓做过多轮「改革」（删归档 / 删 CHANGELOG / 目录重组），每次都会留下
**指向已删东西的引用**。实测已发生三次：
  · 改革删了 `config_old/` ⇒ 文档里 60+ 处仍描述「配置变动时归档进 config_old/」
  · 改革删了 `CHANGELOG.md` ⇒ `ops.md` / `clash.md` 共 7 处仍引用它
    （其中一处还是**自指链接** `[CHANGELOG.md](./ops.md)`）
  · 目录重组 `skill/ → tools/ → self-conf-skills/` ⇒ 路径残留

这类「文档在为不存在的事实背书」是本仓最忌讳的 —— AI 会**信任文档**并照做。

判据
────
① 扫描条目：`references/**/*.md` + 根 `AGENTS.md`
② 对每个**反引号里的路径**或 **markdown 链接目标**：
   若形如 `*.md` / `*.py` / `*.list` / `*.yaml` / `*.conf` / `*.js` 且**不存在**
   ⇒ 报错（**排除**那些明确说「已删 / 不再保留 / 改革前 / 曾经」的上下文）
③ 对已删机制清单（`config_old` / `CHANGELOG.md` / `boundaries.md` …）：
   只允许出现在「说明它不存在」的句子里

⚠️ 刻意**不查**：`<占位>`、`xxx`、示例路径、`/path/to/`（那不是真实引用）。

退出码：0 = 无残留 · 1 = 有 · 2 = 环境不达标
"""
import glob
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
SKILL = os.path.dirname(HERE)

# 已删机制（只允许出现在「说明它不存在」的句子里）
DEAD = {
    "config_old": ["已删除", "已删", "删除", "不再", "改革前", "曾经", "历史副本", "防御性"],
    "CHANGELOG.md": ['从来不在', '旧版原文', '沿革'] + ["不再保留", "不在仓内保留", "已删", "未删", "git 记录", "历史看"],
    "boundaries.md": ["已删", "不再", "改革前", "并入"],
    "check_gate_manifest.py": ["已删", "一并删除", "改革前", "不再"],
    "gen_gate_table.py": ["已删", "一并删除", "改革前", "不再"],
    "check_changelog_drift.py": ["已删", "改革前", "不再"],
    "sync_docs.py": ["已删", "改革前", "不再"],
    "skill/": ['从来不在', '早先'] + ["改革前", "改成", "改名", "重组前", "并入", "原名"],
    "tools/": ['从来不在', '早先'] + ["改革前", "改成", "改名", "重组前", "原名"],
    # 合并文档时删掉的旧文件名（2026-10-08 实测发现仍被引用）
    "profile-anatomy": ['从来不在', '早先'] + ["改革前", "并入", "原名", "已删"],
    "hardening-template": ["改革前", "并入", "原名", "已删"],
    "leak-localization": ["改革前", "并入", "原名", "已删"],
    "ruleset-weight": ["改革前", "并入", "原名", "已删"],
    "public-repo.md": ["改革前", "并入", "原名", "已删"],
    "troubleshoot-faq": ["改革前", "并入", "原名", "已删"],
    "cross-kernel-diff": ["改革前", "并入", "原名", "已删"],
    "dns-basics": ["改革前", "并入", "原名", "已删"],
    "no-resolve-pairing": ["改革前", "并入", "原名", "已删"],
}

# 反引号里的「像文件路径」的 token
PATH_RE = re.compile(r"`([A-Za-z0-9_./-]+\.(?:md|py|list|yaml|yml|conf|js|json|json5))`")
# markdown 链接目标
LINK_RE = re.compile(r"\]\(([^)\s#]+)")


def check_line(ln):
    """→ [(token, 原因)]"""
    hits = []
    for m in PATH_RE.finditer(ln):
        tok = m.group(1)
        if tok.startswith(("http", "/")) or "<" in tok or tok.startswith("/path"):
            continue
        # 相对仓根或相对本文件都可能；两种都试
        cands = [os.path.join(ROOT, tok), os.path.join(SKILL, tok),
                 os.path.join(os.path.dirname(HERE), tok)]
        if any(os.path.exists(c) for c in cands):
            continue
        # 排除「明显是示例」的
        if tok.count("/") == 0 and tok not in ("AGENTS.md",):
            # 裸文件名：只在它属于已删机制时才报
            if not any(d in tok for d in DEAD):
                continue
        hits.append((tok, "文件不存在"))
    for m in LINK_RE.finditer(ln):
        tok = m.group(1)
        if tok.startswith(("http", "#")):
            continue
        if not any(tok.endswith(e) for e in (".md", ".py", ".js", ".yaml", ".yml")):
            continue
        hits.append((tok, "链接目标不存在"))
    return hits


def main():
    if not os.path.isdir(os.path.join(ROOT, "surge")):
        print("❌ 不在仓库根 —— 环境不达标")
        return 2

    scan = glob.glob(os.path.join(SKILL, "references", "**", "*.md"), recursive=True)
    # ⚠️ 也扫脚本：docstring 里的过时引用同样会误导 AI
    #    （2026-10-08 实测在 3 个脚本里发现 `reference/xxx` 与 `profile-anatomy` 残留）
    # ⚠️ **排除本文件自己** —— 它的 DEAD 表天然写着这些名字（自指，非残留）。
    #    同类情形：`check_links.py` 的 fixture 与「曾经不存在的脚本」说明。
    #    处置：把这类文件列入 SELF_EXEMPT，并在各自行内带「不存在/从未」等词。
    scan += [p for p in glob.glob(os.path.join(SKILL, "**", "*.py"), recursive=True)
             if "__pycache__" not in p and os.path.basename(p) != "check_dead_refs.py"]
    scan.append(os.path.join(ROOT, "AGENTS.md"))

    bad = []
    for f in scan:
        if not os.path.isfile(f):
            continue
        rel = os.path.relpath(f, ROOT).replace(os.sep, "/")
        base = os.path.dirname(f)
        lines = io.open(f, encoding="utf-8").read().split(chr(10))
        for i, ln in enumerate(lines, 1):
            # ⚠️ 上下文窗口 ±2 行：允许词可能写在**相邻的注释行**里
            #    （实测误报：`check_selfcontained.py` 把「已删除」写在上一行，
            #     而 `config_old` 在 SKIP_DIRS 那行 ⇒ 单行判定会误报）
            ctx = chr(10).join(lines[max(0, i - 3):i + 2])
            # ① 已删机制的裸提及（不看路径形态）
            for dead, allow in DEAD.items():
                if dead in ln:
                    if not any(a in ctx for a in allow):
                        # 文件确实不在 ⇒ 报
                        if not os.path.exists(os.path.join(ROOT, dead.rstrip("/"))):
                            bad.append((rel, i, dead, "已删机制，但本行没说明它不存在"))
            # ② ⚠️ 已撤回：原想报「反引号里的路径不存在」，但**误报 48 处** ——
            #    因为文档大量用**短形**（`clash/check_structure.py` 相对 gates/、
            #    `profiles/lazy.yaml` 相对 clash/），静态无法可靠解析基准目录。
            #    ⇒ 只报**明确的已删机制**（DEAD 表），不报相对路径。
            #    （教训：判据过严 = 误报 = 会被撤掉。宁可窄而准。）
            pass

    print("已删文件 / 已删机制的残留引用")
    print("-" * 78)
    if bad:
        seen = set()
        for rel, i, tok, why in bad:
            k = (rel, tok)
            if k in seen:
                continue
            seen.add(k)
            print("  NG %s:%d  `%s` —— %s" % (rel, i, tok, why))
        print("-" * 78)
        print("%d 处 —— 改革删掉东西后，文档里的引用要一起清"
              "（「文档为不存在的事实背书」是本仓最忌讳的一类）" % len(seen))
        return 1
    print("  OK 无「指向已删东西」的引用")
    print("-" * 78)
    return 0


if __name__ == "__main__":
    sys.exit(main())
