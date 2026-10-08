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
import sys as _sys
_sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'scripts', 'clash'))
from _clash_common import default_root  # noqa: E402  全仓唯一实现
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
    print("需要 pyyaml：pip install pyyaml")
    sys.exit(2)


ROOT = sys.argv[1] if len(sys.argv) > 1 else default_root()

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

    # ④ tun 段：本仓**不带** —— 只管 DNS 防泄露（dns 段），
    #    TUN 是否开启与怎么设置（stack / 路由 / 劫持端口）交给客户端决定。
    #    静态 profile 与覆写脚本输出一致，都不含 tun。
    #    （泄露面③「旁路设备」因此由客户端的 TUN 接管，不由本仓配置负责。）
    if c.get("tun"):
        errs.append("仍带 tun 段（应由客户端决定，本仓只管 DNS 防泄露）")

    # ⑤ geoip-* 规则必须带 no-resolve
    #    geoip-* 的 behavior 是 ipcidr（IP 规则），不带就会为判定「目标 IP 是否
    #    命中」先触发一次本地解析（泄露面④）。
    #    源码依据：rules/parser.go `case "RULE-SET": isSrc, noResolve := RC.ParseParams(params)`
    #    —— RULE-SET 确实解析该参数并传给 NewRuleSet，故对 RULE-SET 写法有效。
    for r in c.get("rules") or []:
        p_ = [x.strip() for x in r.split(",")]
        if p_ and p_[0] == "RULE-SET" and p_[1].startswith("geoip-"):
            if "no-resolve" not in [x.lower() for x in p_[2:]]:
                errs.append("geoip 规则缺 no-resolve: %s" % r)

    # ⑥ nameserver 必须写 IP 字面量（不能用主机名）
    #    官方：default-nameserver「必须为 IP」，用途就是解析 DNS 服务器的域名。
    #    nameserver 写成主机名时，要靠 default-nameserver 去解析它 ——
    #    那是一次 100% 会发生的明文引导查询（泄露面①）。写 IP 即可消除。
    for ep in (dns.get("nameserver") or []):
        host = str(ep).replace("https://", "").replace("http://", "")
        host = host.split("/")[0].split("#")[0]
        if host and not re.match(r"^\d+\.\d+\.\d+\.\d+$", host) and not host.startswith("["):
            errs.append("nameserver 用了主机名（应为 IP 字面量）: %s" % ep)

    # ⑦ 零 dat 依赖：不得引入 geosite.dat / geoip.dat
    #
    #    为什么单列一条（与姊妹仓「纪律落成判据」的做法一致 ——
    #    它的 check_surge_dns.py 里就有一整条判「加密 DNS 端点必须 IP 字面量」，
    #    同一条纪律在那里也是判据，不是文档里的一句话）：
    #
    #    · 顶层出现 `geox-url` / `geo-auto-update` / `geo-update-interval`
    #      ⇒ mihomo 会去下载并加载 GeoSite.dat / GeoIP.dat
    #    · 规则里出现 `GEOSITE,xxx` / `GEOIP,xxx` ⇒ 直接查那两个数据库
    #    · `nameserver-policy` 的键用 `geosite:xxx` ⇒ 同上
    #
    #    ⚠️ 这不排斥 `.mrs`：geoip-private / geoip-cn 等是 MetaCubeX 的
    #       **独立远程集文件**（format: mrs），与 dat 数据库无关，是本仓想要的。
    #       判据只拦 dat，不拦 mrs。
    for k in ("geox-url", "geo-auto-update", "geo-update-interval"):
        if k in c:
            errs.append("引入了 dat 依赖（顶层键 %s）" % k)
    for r in c.get("rules") or []:
        tp = r.split(",")[0].strip()
        if tp in ("GEOSITE", "GEOIP"):
            errs.append("规则用了原生 %s（应改 RULE-SET 远程集）: %s" % (tp, r))
    for k in (dns.get("nameserver-policy") or {}):
        if str(k).startswith("geosite:"):
            errs.append("nameserver-policy 键用了 geosite:（应改 rule-set:）: %s" % k)

    # ⑧ IPv6
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
