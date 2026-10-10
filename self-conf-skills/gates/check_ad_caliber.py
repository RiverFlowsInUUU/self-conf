#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""两版 `AD` 组口径判据 —— 按**版本分表**断言，不搞一刀切。

为什么要有这一项（2026-10-10 补）
─────────────────────────────────
本仓分流版与懒人版的 `AD` 组**口径刻意不同**：

| 版本 | `AD` 成员 | 理由 |
|:--|:--|:--|
| 分流版 `routing` | `REJECT` + `DIRECT` | 可放行（用户可能想让某条广告规则直连） |
| 懒人版 `lazy`   | 仅 `REJECT`      | 「不留放行的口子」—— 目标用户不需要、也不该有这个开关 |

此前这条差异**只有注释与文档**（`clash/override/my_clash_lazy.js` 的注释、
`profiles/<kern>.md` 的表格），**没有任何机器判据** —— 是本仓唯一一条
「有意差异」没有判据守着的（见 `pitfalls.md` 坑 10）。

⇒ 风险形态：把懒人版的 `AD` 改成 `REJECT + DIRECT`（或反之）**仍然全绿**，
而它改变的是「广告拦截能不能被用户手动放行」这一语义。

判据设计（刻意避开两种错误写法）
────────────────────────────────
⚠️ **不写「`AD` 必须有 ≥1 个成员」** —— 那对两版都成立，等于没判。
⚠️ **不写「`AD` 必须含 `DIRECT`」** —— 那会要求懒人版变成分流版（一刀切套错形态）。
✅ **按版本名分表取期望值**（本文件 `AD_CALIBER`），逐版断言**精确集合**。

覆盖三内核：Surge（`AD = select, …`）/ Egern（`policy_groups[].select`）/
mihomo（`proxy-groups`）。三内核同一版本必须同口径。

退出码：0 = 全过 · 1 = 有判负 · 2 = 前置不达标（读不到 profile）
"""
import os
import re
import sys

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

_sys_d = os.path.dirname(os.path.abspath(__file__))
for _cand in (os.path.join(_sys_d, "..", "lib"), _sys_d):
    _cand = os.path.normpath(_cand)
    if os.path.isfile(os.path.join(_cand, "paths.py")):
        sys.path.insert(0, _cand)
        break
from paths import repo_root  # noqa: E402

# ── 口径表：**唯一真源**。改口径只改这里 ──────────────────────────────
AD_CALIBER = {
    "routing": ["REJECT", "DIRECT"],   # 分流版：可放行
    "lazy": ["REJECT"],                # 懒人版：单成员，不留口子
}


def _surge_members(text):
    """取 `AD = select, <成员…>, key=value…` 的成员列表。"""
    m = re.search(r"^AD\s*=\s*select\s*,(.*)$", text, re.M)
    if not m:
        return None
    out = []
    for tok in m.group(1).split(","):
        tok = tok.strip()
        if not tok or ("=" in tok and not tok.startswith("=")):
            break                      # 遇到参数（icon-url=…）即成员结束
        out.append(tok)
    return out


def _egern_members(text):
    """Egern：`- select:` 块的 `name: AD` 下 `policies:` 列表。"""
    import yaml
    data = yaml.safe_load(text) or {}
    for item in data.get("policy_groups") or []:
        if not isinstance(item, dict) or len(item) != 1:
            continue
        gtype, body = next(iter(item.items()))
        if isinstance(body, dict) and body.get("name") == "AD":
            return list(body.get("policies") or [])
    return None


def _clash_members(text):
    """mihomo：`proxy-groups` 里 `name: AD` 的 `proxies`。"""
    import yaml
    data = yaml.safe_load(text) or {}
    for g in data.get("proxy-groups") or []:
        if g.get("name") == "AD":
            return list(g.get("proxies") or [])
    return None


# (内核, 产品线, 相对路径, 解析器)
FILES = [
    ("surge", "routing", "surge/profiles/routing.conf", _surge_members),
    ("surge", "lazy", "surge/profiles/lazy.conf", _surge_members),
    ("egern", "routing", "egern/profiles/routing.yaml", _egern_members),
    ("egern", "lazy", "egern/profiles/lazy.yaml", _egern_members),
    ("mihomo", "routing", "clash/profiles/routing.yaml", _clash_members),
    ("mihomo", "lazy", "clash/profiles/lazy.yaml", _clash_members),
]


def main():
    # 可选位置参数 = 仓库根。给了就用它（判别力回归的沙箱副本靠它指向副本，
    # 否则 `repo_root()` 会从本脚本位置上溯、永远定位到**原仓** ⇒ 对副本注错无效）。
    root = sys.argv[1] if len(sys.argv) > 1 else repo_root()
    ok, bad, missing = [], [], []
    seen = {}                       # (产品线, 内核) -> 成员集合

    for kern, fam, rel, parse in FILES:
        p = os.path.join(root, rel.replace("/", os.sep))
        if not os.path.isfile(p):
            missing.append(rel)
            continue
        try:
            members = parse(open(p, encoding="utf-8").read())
        except Exception as e:
            bad.append("%s：解析失败 %s" % (rel, e))
            continue
        if members is None:
            bad.append("%s：找不到 `AD` 组" % rel)
            continue
        seen[(fam, kern)] = (rel, members)

    if missing:
        print("❌ 前置不达标：读不到 %d 份 profile —— %s" % (len(missing), missing))
        return 2

    for (fam, kern), (rel, members) in sorted(seen.items()):
        want = AD_CALIBER[fam]
        got = list(members)
        if got == want:
            ok.append("%-7s %-8s AD = %s" % (fam, kern, got))
        else:
            bad.append("%-7s %-8s AD = %s，**应为** %s（%s）"
                       % (fam, kern, got, want, rel))

    # 跨内核一致：同一产品线三内核必须同口径
    for fam in AD_CALIBER:
        vals = {k: tuple(v[1]) for (f, k), v in seen.items() if f == fam}
        if len(set(vals.values())) > 1:
            bad.append("%s：三内核 AD 口径不一致 —— %s"
                       % (fam, {k: list(v) for k, v in vals.items()}))

    for m in ok:
        print("  ✅ %s" % m)
    for m in bad:
        print("  ❌ %s" % m)
    print("\nTOTAL: %d passed, %d failed" % (len(ok), len(bad)))
    if bad:
        print("   口径表在本文件顶部 `AD_CALIBER` —— 两版刻意不同，见 docstring。")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
