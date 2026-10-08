#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""审计 mihomo rule-providers 的**内容**：声明的 behavior 与实际内容是否相符。

为什么需要（对标缺口）：
    surge 有 `audit_ruleset_content.py`、egern 有 `audit_ruleset_noresolve.py`，
    clash 侧此前**一个都没有** —— 而 clash 有 25 份 rule-provider。
    这是「成熟度」拼图上缺的一块。

判据：
    ① behavior 与实际内容相符
       · `domain`    ⇒ 应只有域名条目；出现 IP/CIDR ⇒ 错配
       · `ipcidr`    ⇒ 应只有 IP 条目；出现域名 ⇒ 错配（静默失效）
       · `classical` ⇒ 应只有带类型的规则行（DOMAIN,xxx / IP-CIDR,xxx）；
                       出现裸条目 ⇒ 无法判定，报警
    ② 裸 IP 条目（泄露面⑤）
       远程集里内嵌 IP 条目时，若引用它的规则**不带** `no-resolve`，
       内核会为判定而触发一次本地解析 —— 本仓的 geoip-* 全部带，故应无告警；
       一旦出现即判负。
    ③ 空集 / 取不到 ⇒ 退出码 **2**，绝不静默当通过
    ④ `.mrs` 用头部条目数做完整性校验（对不上 = 存疑，退 2）

复用：`audit_routing_coverage.py` 已有下载/解析/`.mrs` 计数能力，
本脚本直接复用，不在三处各写一份（本仓纪律：判据本体只一份）。

用法：
    python skill/scripts/clash/audit_ruleset_content.py clash/profiles/routing.yaml
    python skill/scripts/clash/audit_ruleset_content.py --offline <profile>

退出码：0 = 内容相符 · 1 = 存在错配 · 2 = 环境/取不到（未验证）
"""

import os
import sys
import argparse

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..", "tests")))

try:
    import yaml
except ImportError:
    print("需要 pyyaml：pip install pyyaml")
    sys.exit(2)

# 复用 audit_routing_coverage 的下载/解析能力
from audit_routing_coverage import load_provider, CACHE_MAX_AGE  # noqa: E402


def _default_root():
    r = os.path.abspath(os.path.join(HERE, "..", ".."))
    if os.path.isdir(os.path.join(r, "clash", "profiles")):
        return os.path.join(r, "clash")
    return r


ROOT = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith("-") else _default_root()


def norm_behavior(prov, name, url):
    """取 provider 的 behavior。"""
    b = prov.get("behavior")
    if b:
        return str(b).strip().lower()
    return "classical"


def audit(path, offline=True, verbose=False):
    try:
        doc = yaml.safe_load(open(path, encoding="utf-8"))
    except Exception as e:
        return (["YAML 解析失败: %s" % e], [], [])

    providers = doc.get("rule-providers") or {}
    rules = doc.get("rules") or []

    # 引用时是否带 no-resolve（按 provider 名）
    noresolve_refs = set()
    for r in rules:
        parts = [x.strip() for x in r.split(",")]
        if len(parts) >= 2 and parts[0] == "RULE-SET":
            if any(x.lower() == "no-resolve" for x in parts[2:]):
                noresolve_refs.add(parts[1])

    problems, notes, unknown = [], [], []
    for name, prov in sorted(providers.items()):
        behavior = norm_behavior(prov, name, prov.get("url", ""))
        res = load_provider(name, prov, offline)
        if not res.get("ok"):
            unknown.append((name, res.get("why", "取不到")))
            continue

        # parse_entries 返回 `(域名条目[(type,value)], IP条目数, 未识别行数)` ——
        # 只有**域名是列表**，IP 与未识别都是**计数**（别再当列表做 len，会 TypeError）。
        doms = res.get("doms") or []
        n_dom = len(doms)
        n_ip = int(res.get("ip") or 0)
        n_unk = int(res.get("unknown") or 0)

        # ① behavior 与实际内容是否相符
        if behavior == "ipcidr" and n_dom > 0 and n_ip == 0:
            problems.append(
                "`%s` 声明 ipcidr 但内容全是域名条目（%d 条）⇒ 静默失效" % (name, n_dom))
        elif behavior == "domain" and n_ip > 0 and n_dom == 0:
            problems.append(
                "`%s` 声明 domain 但内容全是 IP 条目（%d 条）⇒ 静默失效" % (name, n_ip))
        elif behavior == "classical" and n_unk > 0:
            notes.append(
                "`%s` 有 %d 条裸条目（无类型前缀）⇒ classical 下无法判定" % (name, n_unk))

        # ② 裸 IP 条目（泄露面⑤）
        if n_ip > 0 and name not in noresolve_refs:
            problems.append(
                "`%s` 含 %d 条 IP 条目，但引用它的规则未带 no-resolve ⇒ 会触发多余解析"
                % (name, n_ip))

        if verbose:
            notes.append("`%s`（%s）域名 %d / IP %d / 裸 %d — 源 %s"
                         % (name, behavior, n_dom, n_ip, n_unk, res.get("src", "?")))

    return (problems, notes, unknown)


def main():
    ap = argparse.ArgumentParser(
        description="审计 mihomo rule-providers 的内容（behavior 与实际是否相符）")
    ap.add_argument("profiles", nargs="+", help="要审计的 profile 路径")
    ap.add_argument("--offline", action="store_true", help="离线档（不联网下载）")
    ap.add_argument("-v", "--verbose", action="store_true", help="逐份报告")
    args = ap.parse_args()

    print("mihomo 规则集内容审计")
    print("-" * 78)
    total_bad = 0
    has_unknown = False
    for p in args.profiles:
        if not os.path.exists(p):
            print("  NG 文件不存在: %s" % p)
            total_bad += 1
            continue
        problems, notes, unknown = audit(p, offline=args.offline, verbose=args.verbose)
        name = os.path.basename(p)
        if unknown:
            has_unknown = True
            print("  ?? %s —— %d 份取不到（不判通过）" % (name, len(unknown)))
            for n, why in unknown[:6]:
                print("       %s：%s" % (n, why))
            if len(unknown) > 6:
                print("       ... 另 %d 份" % (len(unknown) - 6))
        if problems:
            total_bad += len(problems)
            print("  NG %s —— %d 处错配" % (name, len(problems)))
            for i in problems:
                print("       %s" % i)
        if not problems and not unknown:
            # ⚠️ 零 provider ⇒ 「全部相符」是空集上的全称命题 ⇒ 恒真（真空通过）。
            #    这里直接读一次配置数 provider，避免假绿。（第六轮审查问题 8）
            try:
                import yaml as _y
                _n_prov = len((_y.safe_load(open(p, encoding="utf-8")) or {})
                              .get("rule-providers") or {})
            except Exception:
                _n_prov = -1
            if _n_prov == 0:
                print("  NG %s —— provider 数为 0：没有可核对的规则集"
                      "（配置被清空或解析失败？空集不算通过）" % name)
                total_bad += 1
                continue
            print("  OK %s（全部 provider 的 behavior 与内容相符）" % name)
        for n in notes[:12]:
            print("       · %s" % n)

    print("-" * 78)
    if has_unknown:
        print("存在取不到的规则集 ⇒ 未验证，不是通过")
        return 2
    if total_bad:
        print("内容错配 %d 处" % total_bad)
        return 1
    print("内容相符")
    return 0


if __name__ == "__main__":
    sys.exit(main())
