#!/usr/bin/env python3
"""闸门：`policy-priority` / `priorities` 权重的存在性与一致性。

为什么需要它
────────────
「凡 smart 组都必须带低倍率权重（系数 0.15）、且七个组同值同正则」这条不变量
在本仓写进了三处**散文**（`ops.md` 「发版规矩」区、`references/profiles/surge.md` 的 §13、
`references/profiles/egern.md` 的 §3），却**没有任何脚本读 `policy-priority`**。

后果（2026-10-07 实测确认）：删掉任意一个 smart 组的 `policy-priority`，
13 道闸门**全绿** —— 权重口径静默丢失，低倍率优先这个产品卖点无声失效。
这正是 `check_structure.py` 诞生时那类「全绿但已损坏」事故的同构案例。

断言（分流版两内核）
──────────────────
S1  Surge `smart` 类型的组，必须带 `policy-priority="<regex>:<coefficient>"`。
S2  Egern `smart` 类型的组，必须带 `priorities: {"<regex>": <coefficient>}`。
S3  同一内核内，全部 smart 组的**正则字符串**必须逐字相同。
S4  同一内核内，全部 smart 组的**系数**必须完全相同。
S5  跨内核：Surge 的正则 ↔ Egern 的正则必须逐字相同（转义形态归一后比较）。
S6  跨内核：系数必须相同。
S7  组名集合跨内核必须一致（漏一组 = 该组静默失去权重）。

⚠️ 懒人版**不在判据范围内**：它的 `Proxy` 虽是 `smart` 类型，但**刻意不带权重** ——
   懒人版只有一个总出口，没有「低倍率优先」这个口径（见 lazy.conf 的 `Proxy` 注释）。
   本闸门只审分流版；若把懒人版也纳入，会把它判成缺陷。

退出码：0 = 全部成立 · 1 = 有断言不成立 · 2 = 前置环境不达标（文件缺失/解析失败）。
用法：python self-conf-skills/gates/check_priority_weight.py [仓库根]
"""

import os
import re
import sys

# Windows 中文环境的控制台与管道默认 GBK(cp936)：emoji 一 print 就 UnicodeEncodeError、
# 进程以退出码 1 结束 —— 与"期望判负"的用例撞码会假绿。统一钉成 UTF-8。
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import yaml  # CI 已装（ci.yml: pip install pyyaml）

# Surge 侧：`Name = smart, ..., policy-priority="<regex>:<coeff>", ...`
SURGE_PRIO_RE = re.compile(r'policy-priority="([^"]*)"')


def parse_surge(path):
    """返回 {组名: (regex, coeff) 或 None}，只收录 `smart` 类型的组。

    None 表示该 smart 组**没写** policy-priority。
    """
    groups = {}
    in_pg = False
    with open(path, encoding="utf-8") as f:
        for line in f:
            s = line.strip()
            if s.startswith("["):
                in_pg = s == "[Proxy Group]"
                continue
            if not in_pg or not s or s.startswith("#") or " = " not in s:
                continue
            name, rest = s.split(" = ", 1)
            if not rest.strip().startswith("smart,"):
                continue
            m = SURGE_PRIO_RE.search(rest)
            if not m:
                groups[name.strip()] = None
                continue
            spec = m.group(1)
            # "<regex>:<coeff>" —— 从**最后一个**冒号切，正则里可能有裸冒号
            regex, _, coeff = spec.rpartition(":")
            groups[name.strip()] = (regex, coeff)
    return groups


def parse_egern(path):
    """返回 {组名: (regex, coeff) 或 None}，只收录 `smart` 类型的组。"""
    groups = {}
    with open(path, encoding="utf-8") as f:
        doc = yaml.safe_load(f)
    for item in doc.get("policy_groups", []) or []:
        if not isinstance(item, dict) or "smart" not in item:
            continue
        g = item["smart"] or {}
        name = g.get("name")
        pr = g.get("priorities")
        if not isinstance(pr, dict) or not pr:
            groups[name] = None
            continue
        # 现役口径是单键映射；多键则按排序拼成可比字符串，仍能对拍一致性
        if len(pr) != 1:
            groups[name] = (repr(sorted(pr.items())), "MULTI")
            continue
        (regex, coeff), = pr.items()
        groups[name] = (regex, str(coeff))
    return groups


def norm_regex(rx):
    """把两侧的正则字符串归一成可比形态。

    Surge 里写在双引号内、Egern 写在 YAML 标量里 —— 同一串正则的**反斜杠转义层数**
    不同（`\\.` vs `\\\\.`）。归一只为比对，不改变各侧存储。
    """
    return rx.replace("\\\\", "\\")


def main():
    root = sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    root = os.path.abspath(root)

    surge_path = os.path.join(root, "surge", "profiles", "routing.conf")
    egern_path = os.path.join(root, "egern", "profiles", "routing.yaml")

    for p in (surge_path, egern_path):
        if not os.path.exists(p):
            print(f"❌ 前置不达标：{p} 不存在")
            return 2

    try:
        surge = parse_surge(surge_path)
        egern = parse_egern(egern_path)
    except Exception as exc:  # noqa: BLE001
        print(f"❌ 前置不达标：解析失败 —— {exc}")
        return 2

    if not surge or not egern:
        print("❌ 前置不达标：任一侧 smart 组集合为空（解析口径可能已过时）")
        return 2

    bad = []

    # S1 / S2：存在性
    for name, val in sorted(surge.items()):
        if val is None:
            bad.append(f"S1 Surge `{name}` 是 smart 组但**未写** policy-priority")
    for name, val in sorted(egern.items()):
        if val is None:
            bad.append(f"S2 Egern `{name}` 是 smart 组但**未写** priorities")

    have_s = {n: v for n, v in surge.items() if v}
    have_e = {n: v for n, v in egern.items() if v}

    # S3 / S4：同内核内一致
    for tag, have, side in (("S3", have_s, "Surge"), ("S4", have_s, "Surge"),
                            ("S3", have_e, "Egern"), ("S4", have_e, "Egern")):
        vals = {v[0 if tag == "S3" else 1] for v in have.values()}
        if len(vals) > 1:
            label = "正则" if tag == "S3" else "系数"
            bad.append(f"{tag} {side} 各 smart 组的{label}不一致：{sorted(vals)}")

    # S5 / S6：跨内核一致
    if have_s and have_e:
        sr = {norm_regex(v[0]) for v in have_s.values()}
        er = {norm_regex(v[0]) for v in have_e.values()}
        if sr != er:
            bad.append(f"S5 跨内核正则不一致：Surge={sorted(sr)} Egern={sorted(er)}")
        sc = {v[1] for v in have_s.values()}
        ec = {v[1] for v in have_e.values()}
        if sc != ec:
            bad.append(f"S6 跨内核系数不一致：Surge={sorted(sc)} Egern={sorted(ec)}")

    # S7：组名集合一致
    if set(surge) != set(egern):
        only_s = sorted(set(surge) - set(egern))
        only_e = sorted(set(egern) - set(surge))
        bad.append(f"S7 smart 组名集合跨内核不一致：仅 Surge={only_s} 仅 Egern={only_e}")

    n = len(surge)
    if bad:
        for b in bad:
            print(f"❌ {b}")
        print(f"\n共 {len(bad)} 条不成立（Surge {n} 个 smart 组 / Egern {len(egern)} 个）")
        return 1

    spec = next(iter(have_s.values()))
    print(f"✅ S1–S7 全部成立 —— {n} 个 smart 组均带权重，"
          f"正则/系数同值同形，跨内核一致")
    print(f"   正则 {spec[0]}  ·  系数 {spec[1]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
