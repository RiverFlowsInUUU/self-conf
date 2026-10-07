#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""地区组正则一致性审计器。

审什么
──────
`surge/profiles/routing.conf` 里有 6 个地区组，它们的关键词是**两份拷贝**：

  · 5 个地区组各自写自己的 `policy-regex-filter`（正向断言）；
  · `Other Regions` 的 `policy-regex-filter` 是**负向断言**，
    把这 5 个组的关键词**逐字又抄了一遍**（`^(?!.*(?:...)).+$` 形态）。

官方 Surge 的 filter 不支持引用变量（filter 只能是字面正则），
所以这份拷贝**在配置层面消灭不掉** —— 只能靠本脚本守。

漏改的后果
──────────
某个地区组新增了关键词 K，但 `Other Regions` 的负向断言没同步，
于是 K 不再被排除 ⇒ 含 K 的节点会**同时**出现在它自己的地区组和 Other Regions 里，
两个组的内容不再互斥。面板上看不出异常，是典型的静默退化。

为什么不能靠"肉眼扫一遍"
────────────────────────
关键词里有 emoji（🇭🇰 / 🇯🇵 …）、中文、`\b` 边界、`(?:...)` 非捕获组，
肉眼比对几十个 token 一定会漏。而漏一个不会报任何错。

判据（三条，都必须是"绝对"而非"近似"）
─────────────────────────────────────
  ① 每个地区组的正向 filter 里的关键词 token，必须**逐字出现**在 Other Regions 的
     负向断言里（集合包含，不是模糊匹配）。
  ② 反向也要查：Other Regions 的负向断言里**不应有**任何不来自这些地区组的
     多余关键词 —— 多余就意味着排除得过宽，某些节点会从所有组里消失。
     ⚠️ 例外：末尾那串「信息行过滤词」（倍率 / 剩余 / 到期 …）是**刻意多加**的，
        它不属于任何地区组，用来把订阅里的信息行节点排除掉。脚本按"白名单"放行。
  ③ 地区组之间**不得关键词重叠** —— 重叠会让同一节点落进两个地区组。

退出码：0 = 通过；1 = 有违规；2 = 环境问题（文件缺失 / 解析失败）。

用法：
    python skill/scripts/surge/audit_region_filters.py surge/profiles/routing.conf
    python skill/scripts/surge/audit_region_filters.py surge/profiles/routing.conf -v
"""

import argparse
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _surge_common import parse_conf, split_csv, strip_comment  # noqa: E402

# 地区组的名字 —— 与 routing.conf 里的组名逐字对应（含 `Other Regions`）。
# ⚠️ 若你在 routing.conf 里改了组名，这里也要改（脚本会报缺失，不会静默通过）。
REGION_GROUPS = ["Hong Kong", "Taiwan", "Japan", "Singapore", "United States"]
OTHER_GROUP = "Other Regions"

# 刻意加在 Other Regions 负向断言末尾的"信息行过滤词"。
# 它们不属于任何地区组，用来排除订阅里常见的「剩余流量：100GB」这类假节点。
INFO_WORDS = ["倍率", "剩余", "到期", "流量", "官网", "订阅", "测试",
              "有效", "禁止", "邮箱", "客服", "地址", "网站", "群组"]

# 负向断言的形态：`(?xi)^(?!.*(?:(...))).+$` —— 取出里面那个 `(?:...)` 组的内容。
_NEG_RE = re.compile(r"\^\(\?!\.\*\(\?:", re.S)


# ============================================================================
# token 化
# ============================================================================

def tokenize_positive(pattern):
    """把正向 filter 拆成关键词 token 列表。

    正向写法形如：
        (?i)🇭🇰|香港|Hong\\s*Kong|\\bHKG?\\b|(?:深|沪|京|广)港
    按**顶层** `|` 切分（不切 `(?:...)` 内部的 `|`），再去掉 `(?i)` 前缀。
    """
    p = pattern.strip()
    p = re.sub(r"^\(\?[a-z]+\)", "", p)          # 去掉 (?i) / (?xi)
    return _split_top_level_alt(p)


def _split_top_level_alt(s):
    """按顶层 `|` 切分，`(...)` 内部的 `|` 不切。"""
    out, buf, depth = [], [], 0
    i = 0
    while i < len(s):
        ch = s[i]
        if ch == "\\" and i + 1 < len(s):
            buf.append(s[i:i + 2]); i += 2; continue
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth = max(0, depth - 1)
        elif ch == "|" and depth == 0:
            out.append("".join(buf).strip()); buf = []; i += 1; continue
        buf.append(ch)
        i += 1
    out.append("".join(buf).strip())
    return [t for t in out if t]


def tokenize_negative(pattern):
    """把 Other Regions 的负向断言拆成关键词 token 列表。

    写成多行（`|-` 块标量）或单行都可能，先归一化空白，
    再取出 `(?!.*(?: ... ))` 里的内容，按顶层 `|` 切分。
    """
    # 归一化：把换行与连续空白压成单个空格 —— 多行写法里 `|` 常跟在行尾
    p = re.sub(r"\s+", " ", pattern.strip())
    m = _NEG_RE.search(p)
    if not m:
        return None
    inner = p[m.end():]
    # 找到与 `(?:` 配对的收尾 `)`
    depth, end = 1, None
    i = 0
    while i < len(inner):
        ch = inner[i]
        if ch == "\\" and i + 1 < len(inner):
            i += 2; continue
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                end = i; break
        i += 1
    if end is None:
        return None
    return _split_top_level_alt(inner[:end])


# ============================================================================
# 主流程
# ============================================================================

def groups_of(path):
    """[Proxy Group] 段 -> {组名: 类型}，顺带取出各组的 policy-regex-filter。"""
    sections, _ = parse_conf(path)
    entries = sections.get("proxy group", [])
    filters, types = {}, {}
    for _lineno, raw in entries:
        s = strip_comment(raw)
        if not s or "=" not in s:
            continue
        name, rhs = s.split("=", 1)
        name = name.strip()
        parts = split_csv(rhs)
        if not parts:
            continue
        types[name] = parts[0].strip().lower()
        for p in parts[1:]:
            if p.lower().startswith("policy-regex-filter="):
                filters[name] = p.split("=", 1)[1].strip()
    return filters, types


def main():
    ap = argparse.ArgumentParser(description="地区组正则一致性审计器")
    ap.add_argument("profile", help="Surge .conf 文件路径（含地区组的配置）")
    ap.add_argument("-v", "--verbose", action="store_true", help="打印每个组的关键词数")
    a = ap.parse_args()

    if not os.path.isfile(a.profile):
        print(f"❌ 找不到文件：{a.profile}", file=sys.stderr)
        return 2

    filters, types = groups_of(a.profile)
    if not filters:
        print(f"❌ {a.profile} 里没有任何 policy-regex-filter —— "
              f"这不是一份分流配置？", file=sys.stderr)
        return 2

    fails, oks = [], []

    # ── 前置：全部地区组必须都在 ──────────────────────────────────────────────────
    want = REGION_GROUPS + [OTHER_GROUP]
    missing = [g for g in want if g not in filters]
    if missing:
        for g in missing:
            fails.append(f"缺少地区组 `{g}`（或它没有 policy-regex-filter）")
        print(f"\n地区组正则一致性审计 · {os.path.basename(a.profile)}")
        print("─" * 62)
        for x in fails:
            print(f"   ❌ {x}")
        print("─" * 62)
        print(f"result: 0 passed, {len(fails)} failed")
        return 1

    # ── ① 各地区组的关键词必须全部出现在 Other Regions 的负向断言里 ─────────
    pos_tokens = {g: tokenize_positive(filters[g]) for g in REGION_GROUPS}
    neg = tokenize_negative(filters[OTHER_GROUP])
    if neg is None:
        fails.append(f"`{OTHER_GROUP}` 的 filter 不是 `^(?!.*(?:...)).+$` 形态，无法解析")
        neg = []
    neg_set = set(neg)

    for g in REGION_GROUPS:
        miss = [t for t in pos_tokens[g] if t not in neg_set]
        if miss:
            fails.append(
                f"`{OTHER_GROUP}` 的负向断言漏了 `{g}` 的 {len(miss)} 个关键词："
                + " / ".join(miss)
                + "  ⇒ 这些节点会同时出现在两个组里（组间不再互斥）")
        elif a.verbose:
            oks.append(f"`{g}` 的 {len(pos_tokens[g])} 个关键词都在 Other Regions 里")

    # ── ② 负向断言里不应有多余关键词（信息行过滤词除外）──────────────────────
    declared = set()
    for g in REGION_GROUPS:
        declared.update(pos_tokens[g])
    extra = [t for t in neg if t not in declared and t not in INFO_WORDS]
    if extra:
        fails.append(
            f"`{OTHER_GROUP}` 的负向断言里有 {len(extra)} 个不属于任何地区组的关键词："
            + " / ".join(extra)
            + "  ⇒ 排除得过宽，含这些词的节点会从**所有**地区组里消失")
    if not extra:
        oks.append(f"`{OTHER_GROUP}` 的 {len(neg)} 个关键词全部有出处"
                   f"（{len(declared)} 个来自 {len(REGION_GROUPS)} 个地区组 + {len(INFO_WORDS)} 个信息行过滤词）")

    # ── ③ 地区组之间关键词不得重叠 ─────────────────────────────────────────
    overlap_found = False
    for i, g1 in enumerate(REGION_GROUPS):
        for g2 in REGION_GROUPS[i + 1:]:
            dup = set(pos_tokens[g1]) & set(pos_tokens[g2])
            if dup:
                overlap_found = True
                fails.append(f"`{g1}` 与 `{g2}` 的关键词重叠：{' / '.join(sorted(dup))}"
                             f"  ⇒ 同一节点会落进两个地区组")
    if not overlap_found:
        oks.append(f"{len(REGION_GROUPS)} 个地区组的关键词两两不重叠")

    # ── ④ 类型必须都是 smart（不是 select/url-test）────────────────────────
    bad_type = [g for g in want if types.get(g) != "smart"]
    if bad_type:
        for g in bad_type:
            fails.append(f"地区组 `{g}` 的类型是 `{types.get(g)}`，应为 `smart`"
                         f"（smart 才会对组内节点逐个测速选优）")
    else:
        oks.append(f"{len(want)} 个地区组类型全部是 smart")

    # ── 输出 ────────────────────────────────────────────────────────────────
    print(f"\n地区组正则一致性审计 · {os.path.basename(a.profile)}")
    print("─" * 62)
    for o in oks:
        print(f"   ✅ {o}")
    for x in fails:
        print(f"   ❌ {x}")
    print("─" * 62)
    print(f"result: {len(oks)} passed, {len(fails)} failed")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
