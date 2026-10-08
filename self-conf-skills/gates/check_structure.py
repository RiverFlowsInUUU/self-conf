#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""profile 结构完整性 —— 段必须唯一、且按既定模板序排列。

为什么要有这一道（2026-10-05 事故）
───────────────────────────────────
一次「把 SYSTEM 提到白名单之前」的编辑，因为用行号切片替换时算错了区间，
把 `[Host]` / `[URL Rewrite]` 到 `[Rule]` 之间的一大段吃掉了，结果：
  · `[Host]` / `[URL Rewrite]` 各出现 **两次**
  · `[Rule]` 的内容被**复制了一整份**（RULE-SET 从 9 条变 17 条）
  · 而**全部 11 道闸门照常全绿**：
      - `check_surge_dns.py` 只审 DNS 键，不看结构
      - `check_min_pair.py` 比对「完整版 ↔ .min」，而**两份都坏** ⇒ 比对自然通过
      - `make_min.py` 照常生成（它不校验段唯一性）
  ⇒ 这个事故只被「人眼读文件」发现。本闸门把「人眼」变成「判据」。

判据（两条，都是绝对判据）
──────────────────────────
  ① **段唯一** —— 同一个段标题在文件里只能出现一次。
     Surge `.conf` 的段是 `[名字]`；重复即结构损坏（Surge 对重复段的处理未文档化，
     即便容忍，也说明编辑过程出过错、内容几乎必然有重复或丢失）。
  ② **段序合法** —— 段必须按既定模板序出现，且**只能是该序的子序列**
     （允许省略某段，不允许插到别处）。既定序见 TEMPLATE_ORDER。
     事故里 `[Rule]` 的内容被插到了 `[Host]` 之后 ⇒ 该条会抓住。

适用范围：本仓**四份** Surge profile（`profiles/*.conf`，含 `.min`）。
  Egern 侧是 YAML，结构由解析器保证（重复键 PyYAML 会直接报错），不经本闸门。
  ⚠️ 只检查现役四件；历史版本在 git 里，仓内不保留归档快照，
     不承诺符合今天的模板序。

退出码：0 = 全部合法 · 1 = 有违规 · 2 = 文件缺失/参数错误。
用法：python self-conf-skills/gates/check_structure.py [仓库根]
"""

import os
import re
import sys

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# 段标题：`[General]` / `[Proxy Group]` 等；允许行尾注释
SECTION_RE = re.compile(r"^\s*\[([^\]\[]+)\]\s*(?:[#;].*)?$")

# 既定模板序（本仓四份 profile 共用）。子序列判定用，故只需相对先后正确。
TEMPLATE_ORDER = [
    "General",
    "SSID Setting",
    "Proxy",
    "Proxy Group",
    "Rule",
    "Host",
    "URL Rewrite",
]

PROFILES = [
    "surge/profiles/lazy.conf",
    "surge/profiles/lazy.min.conf",
    "surge/profiles/routing.conf",
    "surge/profiles/routing.min.conf",
]


def sections_of(path):
    """→ [(行号, 段名)]，按出现顺序。"""
    out = []
    with open(path, encoding="utf-8", errors="replace") as f:
        for i, line in enumerate(f, 1):
            m = SECTION_RE.match(line)
            if m:
                out.append((i, m.group(1).strip()))
    return out


def check_file(root, rel):
    """→ [(判据, 通过?, 说明)]"""
    path = os.path.join(root, rel.replace("/", os.sep))
    if not os.path.isfile(path):
        return [("存在", False, "文件缺失：%s" % rel)]
    secs = sections_of(path)
    names = [n for _ln, n in secs]
    out = []

    # ① 段唯一
    dup = sorted({n for n in names if names.count(n) > 1})
    if dup:
        detail = "；".join(
            "%s 出现 %d 次（行 %s）" % (
                n, names.count(n),
                "、".join(str(ln) for ln, x in secs if x == n))
            for n in dup)
        out.append(("① 段唯一", False, "重复段：" + detail))
    else:
        out.append(("① 段唯一", True, "%d 个段，无重复" % len(names)))

    # ② 段序合法（TEMPLATE_ORDER 的子序列）
    pos = {n: i for i, n in enumerate(TEMPLATE_ORDER)}
    unknown = [n for n in names if n not in pos]
    if unknown:
        out.append(("② 段序", False, "出现模板外的段：%s（既定序：%s）"
                    % ("、".join(sorted(set(unknown))), " → ".join(TEMPLATE_ORDER))))
        return out

    idx = [pos[n] for n in names]
    if idx != sorted(idx):
        # 找出第一处逆序
        bad = next((i for i in range(1, len(idx)) if idx[i] < idx[i - 1]), None)
        out.append(("② 段序", False,
                    "段序错误：第 %d 行 `[%s]` 出现在 `[%s]` 之后 —— 既定序 %s"
                    % (secs[bad][0], secs[bad][1], secs[bad - 1][1],
                       " → ".join(TEMPLATE_ORDER))))
    else:
        out.append(("② 段序", True, " → ".join(names)))
    return out


def main():
    root = sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    root = os.path.abspath(root)

    print("profile 结构完整性审计（段唯一 + 段序合法）")
    print("─" * 72)
    fails = 0
    missing = 0
    for rel in PROFILES:
        res = check_file(root, rel)
        for crit, ok, note in res:
            if not ok and "文件缺失" in note:
                missing += 1
            print("   %s %-26s %-10s %s" % ("✅" if ok else "❌", rel, crit, note))
            if not ok:
                fails += 1
    print("─" * 72)
    if missing:
        print("❌ 前置不达标：%d 份 profile 缺失 ⇒ 未验证，不是通过" % missing)
        return 2
    if fails:
        print("result: %d failed —— 结构损坏（成因多为编辑时行号/切片算错）"
              % fails)
        return 1
    print("result: 全部通过 —— 四份 profile 的段唯一且顺序合法")
    return 0


if __name__ == "__main__":
    sys.exit(main())
