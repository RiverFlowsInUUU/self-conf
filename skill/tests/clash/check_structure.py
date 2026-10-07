#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""profile 结构检查 —— 策略组引用、规则指向、DNS 广告拦截双条件。

守三件事：

① 无悬空引用
    策略组的 `proxies` 里每个名字，要么是另一个已定义的组，要么是内置
    策略（DIRECT / REJECT / PASS / GLOBAL）。写错一个字就是死引用，
    mihomo 不报错、直接当无效成员略过 —— 该组的出口就悄悄变了。

② 规则指向存在的组 + 规则集已定义
    `RULE-SET,<provider>,<policy>` 的 provider 必须在 rule-providers 里有定义，
    policy 必须是已定义的组或内置策略。

③ DNS 广告拦截的两个必要条件都满足
    缺任一条拦截就不生效，且**不报错**，所以必须机器判：
      a) nameserver-policy 里有 rule-set: 广告集 → rcode://success
      b) 同一个广告集在 fake-ip-filter 里也列了一遍
    且 a 中的广告项必须排在 `private,cn` / `geosite:private,cn` 之前。

④ IPv6 已显式关闭
    顶层 ipv6 与 dns.ipv6 都应为 false。否则双栈站点可能走真实 IPv6 出网，
    出口 IP 与节点不符。

退出码：0 = 全部通过 · 1 = 有违规 · 2 = 目录/解析问题
用法：python skill/tests/check_structure.py [仓库根]
"""

import os
import sys

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

try:
    import yaml
except ImportError:
    print("需要 pyyaml：pip install pyyaml")
    sys.exit(2)

def _default_root():
    """定位 clash 配置目录（含 profiles/ 与 override/）。

    两种布局都支持：
      · 整合仓 self-conf：配置在 <root>/clash/ 下
      · 单仓 Clash：配置就在 <root> 下

    探测顺序：当前工作目录 → 脚本自身位置。
    优先用 CWD 是因为 CI 从仓库根调用，而 __file__ 在符号链接 /
    不同调用方式下可能算错（实测 GitHub Actions 上 __file__ 探测失败）。
    """
    cands = []
    cwd = os.getcwd()
    cands.append(cwd)
    cands.append(os.path.join(cwd, "clash"))
    here = os.path.dirname(os.path.abspath(__file__))
    up = here
    for _ in range(5):
        cands.append(up)
        cands.append(os.path.join(up, "clash"))
        up = os.path.dirname(up)
    for c in cands:
        if os.path.isdir(os.path.join(c, "profiles")) and os.path.isdir(os.path.join(c, "override")):
            return os.path.abspath(c)
    return os.path.abspath(cwd)

ROOT = sys.argv[1] if len(sys.argv) > 1 else _default_root()

PROFILES = [
    "profiles/lazy.yaml",
    "profiles/lazy.min.yaml",
    "profiles/routing.yaml",
    "profiles/routing.min.yaml",
]

BUILTIN = {"DIRECT", "REJECT", "PASS", "GLOBAL", "PROXY"}


def check_profile(path):
    errs = []
    name = os.path.basename(path)
    c = yaml.safe_load(open(path, encoding="utf-8"))

    groups = c.get("proxy-groups") or []
    gnames = {g.get("name") for g in groups}
    provs = set((c.get("rule-providers") or {}).keys())
    # proxies 里定义的节点名也是合法成员（含占位节点 Node-A / Node-B）
    pnames = {p.get("name") for p in (c.get("proxies") or [])}

    # ① 悬空引用
    for g in groups:
        for m in (g.get("proxies") or []):
            if m not in gnames and m not in BUILTIN and m not in pnames:
                errs.append("悬空引用: 组 %s -> %s" % (g.get("name"), m))

    # ② 规则指向
    for r in c.get("rules") or []:
        p = r.split(",")
        if p[0].strip() == "RULE-SET":
            if len(p) < 3:
                errs.append("规则格式错: %s" % r)
                continue
            prov = p[1].strip()
            pol = p[2].strip()
            if prov not in provs:
                errs.append("规则引用了未定义的规则集: %s" % prov)
            if pol not in gnames and pol not in BUILTIN:
                errs.append("规则指向了不存在的组: %s" % pol)
        elif p[0].strip() == "MATCH":
            pol = p[1].strip() if len(p) > 1 else ""
            if pol not in gnames and pol not in BUILTIN:
                errs.append("MATCH 指向了不存在的组: %s" % pol)

    # ③ DNS 广告拦截双条件
    dns = c.get("dns") or {}
    npol = dns.get("nameserver-policy") or {}
    ffil = [str(x) for x in (dns.get("fake-ip-filter") or [])]

    ads_np = [k for k in npol if str(npol[k]).startswith("rcode://")]
    ads_ff = [x for x in ffil if x.startswith("rule-set:")]

    if not ads_np:
        errs.append("DNS 层广告拦截缺失：nameserver-policy 无 rcode://success")
    if not ads_ff:
        errs.append("DNS 层广告拦截缺失：fake-ip-filter 未列出广告规则集")
    else:
        np_sets = {k.replace("rule-set:", "") for k in ads_np}
        ff_sets = {x.replace("rule-set:", "") for x in ads_ff}
        if np_sets != ff_sets:
            errs.append("广告集两处不一致：policy=%s / fake-ip=%s"
                        % (sorted(np_sets), sorted(ff_sets)))

    # 广告项必须排在 private,cn 之前
    keys = list(npol.keys())
    cn_idx = [i for i, k in enumerate(keys) if "private,cn" in k or "cn" == k.split(":")[-1]]
    ads_idx = [i for i, k in enumerate(keys) if k in ads_np]
    if cn_idx and ads_idx and min(ads_idx) > min(cn_idx):
        errs.append("广告 policy 排在 cn 之后 —— 会先命中 cn 而拿不到空回答")

    # ④ IPv6
    if c.get("ipv6") is not False:
        errs.append("顶层 ipv6 未显式关闭")
    if dns.get("ipv6") is not False:
        errs.append("dns.ipv6 未显式关闭")

    return name, errs


def main():
    print("profile 结构检查")
    print("-" * 78)
    total = 0
    for rel in PROFILES:
        p = os.path.join(ROOT, rel)
        if not os.path.exists(p):
            print("  NG %s 不存在" % rel)
            total += 1
            continue
        name, errs = check_profile(p)
        if errs:
            total += len(errs)
            print("  NG %s —— %d 处" % (name, len(errs)))
            for e in errs:
                print("       ", e)
        else:
            print("  OK %s" % name)
    print("-" * 78)
    if total:
        print("违规 %d 处" % total)
        return 1
    print("全部通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
