#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""§节号引用的歧义检查（**话题感知**）。

为什么有这个
────────────
`references/` 是**多篇文档合并**而成的（改革时 43 篇 → 8 篇），
每篇各自带 `### 1 ·` / `### 4 ·` 编号 ⇒ 同一文件里同一编号出现多次。

但不是所有重复都危险：
  · **同话题内引用**（读着话题 A 的 §2，说「见 §4」）⇒ 读者自然找 A 的 §4，**可接受**
  · **跨话题引用**（从话题 C 引 §4，而 A / B / C 都有 §4）⇒ **真歧义**，会引错

判据：对每个 `§N` 引用，看它**所在的话题**（最近的 `## `）内 §N 是否唯一：
  ① 唯一 ⇒ 通过
  ② 该话题内不唯一，或该话题内**没有** §N 而别的話題有 ⇒ 报歧义（提示改用标题名）

⚠️ 只查 `§N` 形式；「见〈匹配顺序〉」这种**用标题名**的引用一律放行（推荐写法）。

退出码：0 = 无歧义 · 1 = 有 · 2 = 环境不达标
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
REF = os.path.join(ROOT, "self-conf-skills", "references")

# 话题（## ）与节（### / ####）
TOPIC_RE = re.compile(r"^##\s+(.+?)\s*$", re.M)
HEAD_RE = re.compile(r"^(#{3,4})\s*(\d+(?:\.\d+)?)\s*[·.\s]\s*(.+?)\s*$", re.M)
REF_RE = re.compile(r"§\s*(\d+(?:\.\d+)?)")


def main():
    if not os.path.isdir(REF):
        print("❌ 找不到 references/ —— 环境不达标")
        return 2

    bad = []
    checked = 0
    for f in sorted(glob.glob(os.path.join(REF, "**", "*.md"), recursive=True)):
        rel = os.path.relpath(f, ROOT).replace(os.sep, "/")
        txt = io.open(f, encoding="utf-8").read()

        # 话题边界
        topics = [(m.start(), m.group(1)) for m in TOPIC_RE.finditer(txt)]
        if not topics:
            topics = [(0, "(全文)")]

        # 每个节的 (位置, 编号, 标题)
        heads = [(m.start(), m.group(2), m.group(3)) for m in HEAD_RE.finditer(txt)]

        def topic_of(pos):
            cur = topics[0][1]
            for start, name in topics:
                if start <= pos:
                    cur = name
                else:
                    break
            return cur

        # 每话题内各编号的出现次数
        per_topic = {}
        for pos, num, title in heads:
            per_topic.setdefault(topic_of(pos), {}).setdefault(num, []).append(title)

        for m in REF_RE.finditer(txt):
            num = m.group(1)
            checked += 1
            # ⚠️ 若这一行写了**文件名**（`clash.md §13` / [`ops.md`](./ops.md) §4）
            #    ⇒ 是跨文件引用，文件名已消歧 ⇒ 放行。
            _ls = txt.rfind(chr(10), 0, m.start()) + 1
            _le = txt.find(chr(10), m.start())
            _line = txt[_ls:_le if _le > 0 else len(txt)]
            if re.search(r"\.md|references/|profiles/", _line):
                continue
            where = topic_of(m.start())
            in_topic = per_topic.get(where, {}).get(num, [])
            if len(in_topic) == 1:
                continue                      # 本话题内唯一 ⇒ 可接受
            if len(in_topic) > 1:
                bad.append((rel, where, num, "本话题内 %d 个候选：%s"
                            % (len(in_topic), " / ".join(x[:20] for x in in_topic))))
                continue
            # 本话题内没有 ⇒ 是否别的话题有？
            others = [t for t, d in per_topic.items() if num in d]
            if others:
                bad.append((rel, where, num, "本话题内无，别的话题有（%s）"
                            % "、".join(x[:16] for x in others[:3])))

    print("§节号引用的歧义检查（话题感知）")
    print("-" * 78)
    if bad:
        for rel, where, num, why in bad[:40]:
            print("  NG %s  「%s」内的 §%s —— %s" % (rel, where[:22], num, why))
        if len(bad) > 40:
            print("  ... 另有 %d 处" % (len(bad) - 40))
        print("-" * 78)
        print("%d 处真歧义（核对 %d 个引用）—— 改用**标题名**引用"
              "（如「见〈匹配顺序〉」），或写明文件名（如 `dns.md §4`）" % (len(bad), checked))
        return 1
    print("  OK 核对 %d 个 §引用，无跨话题歧义" % checked)
    print("-" * 78)
    return 0


if __name__ == "__main__":
    sys.exit(main())
