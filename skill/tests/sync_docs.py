#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""文档「抄写配置」的生成器 —— 从配置真源重写文档里的 AUTO 段。

为什么有这个（2026-10-05 立）
─────────────────────────────
文档里有几处**抄了配置**的信息（分组清单、分组数、规则数、规则集引用数）。
它们是**副本**：改配置时得同步改，而**漏同步不会报错** —— 页面静默地说谎。
实测已踩三次：组清单漏改（用户核对才发现）· README 的 emoji 丢失 · 引用数过期。

本仓对这类"真源 → 产物"已有成功范式（`make_min.py`：完整版 → `.min`）：
  · 有单一真源 · 有生成产物 · 有 `--check` 漂移闸门 · 产物**不手改**
本脚本把同一范式用到**文档**上 ⇒ 副本从"要靠人记得同步"变成"脚本自动重写"。

AUTO 段语法（HTML 注释，GitHub 渲染时不可见）
─────────────────────────────────────────────
    <!-- auto:KEY -->  旧内容（任意行数）  <!-- /auto:KEY -->

一行内联式（数字类，标记可嵌在句中）：
    现役两侧各 **<!-- auto:group-count -->22<!-- /auto:group-count --> 个分组**

生成器只**替换标记之间的内容**，标记本身与其外的文字一字不动。

已支持的 KEY
────────────
  group-list      分组清单（`cross-kernel-diff.md`，代码块内的多行 · 分隔）
  group-count     分组数（同上，内联数字）
  rule-count      规则条数（同上，内联数字）
  ruleset-refs    `rulesets.md` 的分流版规则集引用数
  clash-group-count / clash-rule-count  mihomo 静态分流版的**可见**组数 / 规则条数（clash 文档）

⚠️ 换行策略（`group-list`）：按 ` · ` 边界打包到不超过 **82 字符**。
   首次 `--apply` 会把现有清单**重排一次**（现状是人工语义分段、无固定规则）；
   此后同一份配置永远产出同一份文本 ⇒ `--check` 稳定通过。
   要调整观感就改 `LIST_WIDTH` 常量，**不要手改文档里的那段**（会被下次生成覆盖）。

用法
────
    python skill/tests/sync_docs.py              # 计划模式：只报哪些段会变
    python skill/tests/sync_docs.py --check      # 闸门：有不一致 exit 1（替代专门的对拍闸门）
    python skill/tests/sync_docs.py --apply      # 写盘

退出码：0 = 一致/已写 · 1 = --check 发现漂移 · 2 = 环境不达标（缺文件/解析失败）。
"""

import argparse
import io
import os
import re
import sys

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

try:
    import yaml
except ImportError:
    print("需要 PyYAML：python -m pip install pyyaml", file=sys.stderr)
    sys.exit(2)

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "skill", "scripts", "surge"))
try:
    from _surge_common import parse_conf, split_csv, strip_comment
except ImportError:                                           # pragma: no cover
    print("❌ 取不到 `_surge_common` —— 环境不达标", file=sys.stderr)
    sys.exit(2)

R_CONF = "surge/profiles/routing.conf"
R_YAML = "egern/profiles/routing.yaml"
L_CONF = "surge/profiles/lazy.conf"
L_YAML = "egern/profiles/lazy.yaml"

LIST_WIDTH = 82          # group-list 的打包宽度（见头注「换行策略」）


# ============================================================================
# 配置真源：提取
# ============================================================================

def _groups_of_conf(rel):
    """Surge .conf → [(组名, 类型)]，按文件顺序。"""
    sec, _ = parse_conf(os.path.join(ROOT, rel.replace("/", os.sep)))
    out = []
    for _ln, raw in sec.get("proxy group", []):
        s = strip_comment(raw)
        if "=" not in s:
            continue
        name, rhs = s.split("=", 1)
        parts = split_csv(rhs)
        if parts and parts[0].strip().lower() in ("select", "smart", "external"):
            out.append((name.strip(), parts[0].strip().lower()))
    return out


def _groups_of_yaml(rel):
    d = yaml.safe_load(open(os.path.join(ROOT, rel.replace("/", os.sep)),
                            encoding="utf-8")) or {}
    return [(list(g.values())[0]["name"], list(g.keys())[0])
            for g in (d.get("policy_groups") or [])]


def _rule_count_conf(rel):
    sec, _ = parse_conf(os.path.join(ROOT, rel.replace("/", os.sep)))
    return sum(1 for _ln, raw in sec.get("rule", []) if strip_comment(raw))


def _rule_count_yaml(rel):
    d = yaml.safe_load(open(os.path.join(ROOT, rel.replace("/", os.sep)),
                            encoding="utf-8")) or {}
    return len(d.get("rules") or [])


def _ruleset_refs_conf(rel):
    """指向规则集的条目数（`RULE-SET` 开头，含规则集引用位）。"""
    sec, _ = parse_conf(os.path.join(ROOT, rel.replace("/", os.sep)))
    return sum(1 for _ln, raw in sec.get("rule", [])
               if strip_comment(raw).upper().startswith("RULE-SET"))


def _ruleset_refs_yaml(rel):
    d = yaml.safe_load(open(os.path.join(ROOT, rel.replace("/", os.sep)),
                            encoding="utf-8")) or {}
    return sum(1 for r in (d.get("rules") or []) if "rule_set" in r)


def pack_list(names, width=LIST_WIDTH):
    """把名字用 ` · ` 连接并按宽度打包成多行（` · ` 处断行，不拆名字）。"""
    lines, cur = [], ""
    for n in names:
        cand = n if not cur else cur + " · " + n
        if cur and len(cand) > width:
            lines.append(cur)
            cur = n
        else:
            cur = cand
    if cur:
        lines.append(cur)
    return lines


def build_values():
    """→ {KEY: 生成内容(字符串，多行用 \\n)}"""
    sg = [n for n, _t in _groups_of_conf(R_CONF)]
    eg = [n for n, _t in _groups_of_yaml(R_YAML)]
    surf_ok = sg == eg
    # 清单取 Surge 侧（两内核顺序本就要求一致；不一致时本脚本不负责裁决，
    # 那是 audit_routing_coverage 的 Z0 与 check_docs_sync 的活）
    vals = {
        "group-list": "\n".join(pack_list(sg)),
        "group-count": str(len(sg)),
        "rule-count": str(_rule_count_conf(R_CONF)),
        "ruleset-refs": str(_ruleset_refs_conf(R_CONF)),
    }
    # mihomo（clash）侧规模 —— 文档里原本手抄，改了配置不会自动变 ⇒ 会静默说谎，故纳入 AUTO。
    # 字典字面量里不能放语句，故在字典构造完成后追加。
    _cpro = os.path.join(ROOT, "clash", "profiles", "routing.yaml")
    if os.path.isfile(_cpro):
        import yaml as _y
        dc = _y.safe_load(io.open(_cpro, encoding="utf-8")) or {}
        vals["clash-group-count"] = str(len([g for g in (dc.get("proxy-groups") or []) if not g.get("hidden")]))
        vals["clash-rule-count"] = str(len(dc.get("rules") or []))
    return vals, surf_ok


# ============================================================================
# AUTO 段：定位与替换
# ============================================================================
# 一段 = `<!-- auto:KEY -->` ... `<!-- /auto:KEY -->`（可跨行）

def find_segments(text):
    """→ [(KEY, start_of_inner, end_of_inner)]（按出现顺序）。"""
    out = []
    for m in re.finditer(r"<!--\s*auto:([A-Za-z0-9_-]+)\s*-->(.*?)<!--\s*/auto:\1\s*-->",
                         text, re.S):
        key = m.group(1)
        s = m.start(2)
        e = m.end(2)
        out.append((key, s, e))
    return out


def rewrite(text, vals, apply_):
    """→ (新文本, [变了的 KEY])。不改动标记本身。"""
    changed = []
    # 从后往前替换，避免位移影响
    segs = find_segments(text)
    for key, s, e in reversed(segs):
        if key not in vals:
            continue
        new = vals[key]
        # 多行段：把内容包在换行里，保持可读
        if "\n" in new:
            new = "\n" + new + "\n"
        if text[s:e] != new:
            changed.append(key)
            text = text[:s] + new + text[e:]
    return text, list(dict.fromkeys(reversed(changed)))


# ============================================================================
# 主流程
# ============================================================================

TARGETS = [
    "skill/reference/shared/cross-kernel-diff.md",
    "README.md",
    "skill/reference/shared/rulesets.md",
    # clash 文档：mihomo 规模此前手抄 ⇒ 改配置会静默说谎，纳入 AUTO 同步
    "skill/reference/clash/branch.md",
]


# ============================================================================
# 基准序表：只「守」不「生成」（表里含人的归纳，无法机械生成）
# ============================================================================
# `rulesets.md` §3 的基准序表把 25 条规则逐位列出。其中：
#   · 位次 → 目标组名  = **配置的副本**（可机械比对）
#   · 区间归纳（`⑤⑥ 内网` / `⑦–⑩ 厂商专属`）、两内核差异说明 = **人的归纳**（生成不了）
# ⇒ 全 AUTO 化会覆盖掉人的部分，所以这里**只做一致性检查、不改表**。
# 2026-10-05 实测：这张表从 ⑬ 起的位次**全错**（上轮改顺序时漏改，10 轮无人发现，
# 而 Z0/sync_docs 都不读它）⇒ 这才补上这道判据。

_CIRCLED = {c: i + 1 for i, c in enumerate("①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳")}
_CIRCLED.update({"㉑": 21, "㉒": 22, "㉓": 23, "㉔": 24, "㉕": 25})


def _actual_targets():
    """配置真源的 25 位目标（组名 / DIRECT / Proxy）。"""
    sec, _ = parse_conf(os.path.join(ROOT, R_CONF))
    out = []
    for _ln, raw in sec.get("rule", []):
        s = strip_comment(raw)
        if not s:
            continue
        parts = split_csv(s)
        ty = parts[0].strip().upper()
        out.append(parts[2].strip() if ty == "RULE-SET"
                   else ("DIRECT" if ty == "GEOIP" else "Proxy"))
    return out


# 表头行 + 表格体（到空行为止）。用普通字符串构造，避免转义坑。
# 表头行 + 表格体（到空行为止）。用 re.escape 避免转义坑。
_HDR = "| 位 | 内容 | 位 | 内容 |"
SECTION_TABLE_RE = re.compile(re.escape(_HDR) + r"(.*?)\n\n", re.S)


def _doc_positions(text):
    """从基准序表提取 {位次: 目标组名}。只取**有 → 的单元格**（区间叙述行无 →，跳过）。"""
    m = SECTION_TABLE_RE.search(text)
    if not m:
        return None
    doc = {}
    for line in m.group(1).split("\n"):
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) < 4:
            continue
        for k in (0, 2):
            pos, txt = cells[k], cells[k + 1]
            if not pos or "位" in pos or "→" not in txt:
                continue
            ids = [_CIRCLED[c] for c in re.findall(r"[①-⑳㉑-㉕]", pos) if c in _CIRCLED]
            tm = re.search(r"→\s*\*{0,2}`?([A-Za-z][A-Za-z ]*)`?\*{0,2}", txt)
            if ids and tm:
                for n in ids:
                    doc[n] = tm.group(1).strip()
    return doc


def check_baseline_table(root):
    """→ [(位次, 表里, 配置里)]，只列不一致的。表缺失/解析不到返回 None（未验证）。"""
    path = os.path.join(root, "skill", "reference", "shared", "rulesets.md")
    if not os.path.isfile(path):
        return None
    doc = _doc_positions(io.open(path, encoding="utf-8").read())
    if not doc:
        return None
    actual = _actual_targets()
    bad = []
    for i, name in sorted(doc.items()):
        if i <= len(actual) and name != actual[i - 1]:
            bad.append((i, name, actual[i - 1]))
    return bad



def main():
    ap = argparse.ArgumentParser(description="文档 AUTO 段生成器（真源=配置）")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--check", action="store_true", help="闸门：有不一致 exit 1")
    g.add_argument("--apply", action="store_true", help="写盘")
    a = ap.parse_args()

    # 前置：四份现役 profile 都在（缺了就是环境不达标，不是"没有漂移"）
    need = [R_CONF, R_YAML, L_CONF, L_YAML] + TARGETS
    miss = [p for p in need if not os.path.isfile(os.path.join(ROOT, p.replace("/", os.sep)))]
    if miss:
        print("❌ 缺文件（环境不达标，不是通过）：%s" % "、".join(miss), file=sys.stderr)
        return 2

    vals, surf_ok = build_values()
    if not surf_ok:
        print("⚠️ 两内核分组顺序不一致 —— 本脚本按 Surge 侧生成；"
              "顺序问题由 Z0 / check_docs_sync 报，不在此处裁决。")

    print("文档 AUTO 段同步（真源 = 配置）")
    print("─" * 72)
    total_changed = []
    for rel in TARGETS:
        path = os.path.join(ROOT, rel.replace("/", os.sep))
        text = io.open(path, encoding="utf-8").read()
        segs = find_segments(text)
        keys = [k for k, _s, _e in segs]
        if not segs:
            print("   ⏭  %-46s 无 AUTO 段" % rel)
            continue
        new, changed = rewrite(text, vals, a.apply)
        mark = "�’" if changed else "✅"
        print("   %s %-46s %d 段 %s" % (mark, rel, len(segs),
                                        ("（变了：%s）" % "、".join(changed)) if changed else ""))
        if changed:
            total_changed += [(rel, k) for k in changed]
        if a.apply and changed:
            io.open(path, "w", encoding="utf-8", newline="").write(new)

    # ── 基准序表：只守不生成（表里含人的归纳）─────────────────────────────
    bt = check_baseline_table(ROOT)
    if bt is None:
        print("   ⚠️ rulesets.md 基准序表 —— 解析不到（结构变了？）跳过")
    elif bt:
        print("   ❌ rulesets.md 基准序表 —— %d 位与配置不一致：" % len(bt))
        for i, doc_name, act in bt:
            print("        第 %d 位：表 `%s` ↔ 配置 `%s`" % (i, doc_name, act))
        total_changed.append(("rulesets.md 基准序表", "位次漂移"))
    else:
        print("   ✅ rulesets.md 基准序表 —— 显式位次与配置逐位一致（%d 位）" % 19)

    print("─" * 72)
    if a.apply:
        print("已写盘：%d 处" % len(total_changed))
        return 0
    if a.check:
        if total_changed:
            print("result: %d 处漂移 —— 跑 `python skill/tests/sync_docs.py --apply` 重写"
                  % len(total_changed))
            return 1
        print("result: 全部一致 —— 文档 AUTO 段与配置真源同步")
        return 0
    print("（计划模式：一个字都不写。加 --apply 落盘，加 --check 作闸门）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
