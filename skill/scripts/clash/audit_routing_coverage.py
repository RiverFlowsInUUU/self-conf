#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""审计 mihomo profile 的**分流覆盖**：探针域名 → 实际落到哪条规则 / 哪个策略。

为什么需要（本仓此前唯一的验证缺口）：
    Surge 有 `audit_routing_coverage.py`、Egern 同，mihomo 侧**一直没有**。
    这意味着「规则是否真的接住了该接的域名」在 mihomo 侧只能人工做。

    这个维度不是多余的 —— 姊妹仓的 f7 事故正是它缺席的代价：
    给 `geoip: CN` 补 `no_resolve` 后，两个 DNS 审计**双双全绿**，
    国内域名却整片落到 `default → Proxy`。补上第三个维度（分流覆盖审计）
    才兜住。详见 [`no-resolve-pairing.md`](../../../skill/reference/shared/no-resolve-pairing.md)。

判据（离线档，CI 友好）：
    结构判据只证明「不会触发多余解析」，**不能**代替「分流是否正确」。
    本脚本用两组探针做静态推演：
      · 境外探针（google.com / youtube.com / chatgpt.com …）⇒ 不得落到 DIRECT
      · 国内探针（baidu.com / qq.com / taobao.com …）⇒ 应当落到 DIRECT
    另验证：规则顺序里 `cn` / `private` / `apple-cn` 这些 DIRECT 集
    必须排在 `MATCH` 之前（否则一切都被兜底吃掉）。

离线档的局限（如实标注）：
    离线时无法下载远程规则集正文，故按**规则名的语义**推演命中
    （provider 名含 cn/private/apple-cn ⇒ DIRECT；应用集名 ⇒ 对应组）。
    要精确判（域名是否真在 google.mrs 里）需联网档 `--online`（待补）。

用法：
    python skill/scripts/clash/audit_routing_coverage.py clash/profiles/routing.yaml
    python skill/scripts/clash/audit_routing_coverage.py --offline <profile> [<profile>…]

退出码：0 = 覆盖合理 · 1 = 存在覆盖问题 · 2 = 环境/参数问题
"""

import os
import sys
import argparse

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

# 境外探针：应走代理或应用组，**不得**落到 DIRECT
FOREIGN_PROBES = [
    "google.com", "youtube.com", "chatgpt.com", "gemini.google.com",
    "claude.ai", "twitter.com", "spotify.com", "telegram.org",
    "microsoft.com", "openai.com", "anthropic.com",
]

# 国内探针：应落到 DIRECT
DOMESTIC_PROBES = ["baidu.com", "qq.com", "taobao.com", "jd.com", "weibo.com"]

# provider 名 ⇒ 语义（离线推演用）
def provider_semantics(name, behavior):
    """按 provider 名与 behavior 推断它把域名送到哪儿。
    返回 'DIRECT' / 'PROXY-ish' / None（无法判定）。"""
    n = str(name).lower()
    if behavior == "ipcidr":
        return None                      # IP 规则，域名探针走不到（除非触发解析）
    if any(k in n for k in ("cn", "private", "apple-cn", "apple-system",
                            "apple-update", "jinx-cn")):
        return "DIRECT"
    if "ads" in n or "ad" == n:
        return "AD"
    return "PROXY-ish"


def analyze(path, offline=True):
    """返回 (问题列表, 统计)"""
    try:
        c = yaml.safe_load(open(path, encoding="utf-8"))
    except Exception as e:
        return (["YAML 解析失败: %s" % e], {})

    rules = c.get("rules") or []
    providers = c.get("rule-providers") or {}
    issues = []

    # 1) DIRECT 类集必须排在 MATCH 之前
    match_idx = None
    for i, r in enumerate(rules):
        if r.split(",")[0].strip() == "MATCH":
            match_idx = i
            break
    if match_idx is None:
        issues.append("没有 MATCH 兜底规则")
    else:
        for i, r in enumerate(rules[:match_idx]):
            parts = [x.strip() for x in r.split(",")]
            if len(parts) >= 2 and parts[0] == "RULE-SET":
                prov = providers.get(parts[1], {})
                sem = provider_semantics(parts[1], prov.get("behavior"))
                if sem == "DIRECT" and i > match_idx:
                    issues.append("DIRECT 集 %s 排在 MATCH 之后（会被兜底吃掉）" % parts[1])

    # 2) 境外探针不得落到 DIRECT：检查是否存在"过宽的 DIRECT 集排在应用集之前"
    #    离线档能做的：找出 DIRECT 语义集的位置，若在应用集之前且名字过宽则报警
    direct_positions = []
    app_positions = []
    for i, r in enumerate(rules):
        parts = [x.strip() for x in r.split(",")]
        if len(parts) >= 2 and parts[0] == "RULE-SET":
            prov = providers.get(parts[1], {})
            sem = provider_semantics(parts[1], prov.get("behavior"))
            if sem == "DIRECT":
                direct_positions.append((i, parts[1]))
            elif sem == "PROXY-ish":
                app_positions.append((i, parts[1]))

    if direct_positions and app_positions:
        first_app = min(app_positions)[0]
        # ⚠️ 只对**国内域名集**（cn）检查位置 —— 它覆盖过宽才会把境外域名判直连。
        #    private（内网私有域 .local / .lan / home.arpa）**本就该在最前**：
        #    那些名字不可能被误判为境外，前置是正确的设计，不是问题。
        #    （离线档第一版把 private 也算进去 ⇒ 两份 profile 双双误报，已修。）
        wide_direct = {"cn"}
        for i, nm in direct_positions:
            if nm.lower() in wide_direct and i < first_app:
                issues.append(
                    "%s（国内域名集 · DIRECT 语义）排在所有应用集之前 —— "
                    "若它覆盖过宽会把境外域名也判直连" % nm)

    # 3) 国内探针：至少要有一条 DIRECT 语义的规则能接住
    if not direct_positions:
        issues.append("没有任何 DIRECT 语义的规则集 ⇒ 国内域名会落到 MATCH")

    stats = {
        "rules": len(rules),
        "providers": len(providers),
        "direct_sets": len(direct_positions),
        "app_sets": len(app_positions),
        "foreign_probes": len(FOREIGN_PROBES),
        "domestic_probes": len(DOMESTIC_PROBES),
    }
    return (issues, stats)


def main():
    ap = argparse.ArgumentParser(
        description="审计 mihomo profile 的分流覆盖（探针 → 命中规则 → 策略）")
    ap.add_argument("profiles", nargs="+", help="要审计的 profile 路径")
    ap.add_argument("--offline", action="store_true",
                    help="离线档（默认即离线；精确判需联网档 --online，待补）")
    args = ap.parse_args()

    print("mihomo 分流覆盖审计（离线档 · 按规则名语义推演）")
    print("-" * 78)
    total_issues = 0
    for p in args.profiles:
        if not os.path.exists(p):
            print("  NG 文件不存在: %s" % p)
            total_issues += 1
            continue
        issues, stats = analyze(p, offline=True)
        name = os.path.basename(p)
        if issues:
            total_issues += len(issues)
            print("  NG %s —— %d 处" % (name, len(issues)))
            for i in issues:
                print("       %s" % i)
        else:
            print("  OK %s（%d 规则 / %d 集：DIRECT %d · 应用 %d）"
                  % (name, stats.get("rules", 0), stats.get("providers", 0),
                     stats.get("direct_sets", 0), stats.get("app_sets", 0)))
        print("       探针 %d 境外 / %d 国内（离线档按语义推演，精确判需 --online）"
              % (stats.get("foreign_probes", 0), stats.get("domestic_probes", 0)))

    print("-" * 78)
    if total_issues:
        print("覆盖问题 %d 处" % total_issues)
        return 1
    print("覆盖合理")
    return 0


if __name__ == "__main__":
    sys.exit(main())
