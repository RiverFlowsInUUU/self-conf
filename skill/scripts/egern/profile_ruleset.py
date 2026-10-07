#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""看一眼规则集文件到底是什么 —— 条目类型分布 + 会不会强制 DNS 解析。

为什么必须有这个脚本
--------------------
**规则集的名字会骗人。** 实测：blackmatrix7 的 `ChinaMax.list` 听起来最像"中国域名表"，
实际 12,614 条里 12,472 条是 IP-CIDR/IP-CIDR6、域名只有 64 条。该仓库 README 自己写明
`ChinaMax.list` 与 `ChinaMax_Domain.list` 需"共同使用"，只有 `ChinaMax_All_No_Resolve.list`
才可以"单独使用"。**把它当域名表用，国内域名会整片落到 default（走代理）。**

更早一次踩坑是 `Apple_All.list`：里面有 13 条 IP-CIDR 没带 `no-resolve`，
而该规则排在 `default` 之前 ⇒ 每个走到它的域名都被强制本地解析一次（泄露源）。
**这类缺陷用眼睛读 profile 是看不见的，必须下载规则集本身、数条目。**

**文件名也会骗人 —— 尤其 AWAvenue。** 该仓库 `Filters/` 下同一份数据有两种写法：
`AWAvenue-Ads-Rule-Surge.list` 是**裸域名**（`.8le8le.com`，前导点 = 该域及其所有子域），
对应 Surge 的 `DOMAIN-SET` 规则类型；`AWAvenue-Ads-Rule-Surge-RULE-SET.list` 才是 `DOMAIN,xxx`
规则行，对应 `RULE-SET`。**profile 里的 `rule_set` 消费的是后者**（2026-09-22 修正过这个地址）。
⚠️ 本脚本会把裸域名**自动归一化**成 `DOMAIN-SUFFIX,` 再统计（见 `split_entries`），
所以**它看不出这类错** —— 「地址里的文件格式与消费方式是否匹配」只能按官方语法人工核。

因此任何一次「要新增/替换 rule_set」之前，先跑本脚本：

    python profile_ruleset.py ChinaMax.list
    python profile_ruleset.py https://.../Apple_All_No_Resolve.list

判据（三条同时看）：
  1) **域名条目数** —— 这是"能不能兜住域名"的唯一判据，不是文件名、也不是 README 标题。
  2) **IP 条目里有多少条没带 `no-resolve`** —— 不为 0 且规则被启用 ⇒ 会强制解析。
  3) 是否存在 `PROCESS-NAME` / `USER-AGENT` —— Egern 未文档化的类型，可能出现静默失效。

退出码：0 = 干净（无裸 IP 条目）；1 = 含裸 IP 条目（会强制解析）；2 = 参数错误。
"""
import argparse
import io
import os
import re
import sys
# 输出编码垫片：见 _egern_common.force_utf8_stdout —— GBK 控制台下 emoji 会崩成退出码 1
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _egern_common import CACHE_MAX_AGE, fetch_cached, force_utf8_stdout  # noqa: E402


def fetch(src, offline=False):
    """返回 (内容, 来源说明)。src 可以是 URL 或本地路径。

    2026-09-24 收编：这里从前只判"缓存在不在"，而同目录两份审计对**同一个缓存目录**
    （`egern-ruleset-cache`）判 7 天窗口 ⇒ 同一份陈旧文件，一个脚本出声报"按陈旧那份判"，
    另一个把它当"缓存命中"直接拿去数条目。窗口判据现在只在 `_egern_common.fetch_cached` 一处。
    """
    if not src.startswith("http"):
        if not os.path.exists(src):
            return None, "文件不存在"
        return io.open(src, encoding="utf-8", errors="replace").read(), "本地文件"
    body, path, source, detail = fetch_cached(src, offline,
                                              user_agent="egern-dns-audit/1.0", timeout=60)
    if source == "fresh":
        return body, f"已下载并缓存 {path}"
    if source == "cache":
        return body, f"缓存 {path}"
    if source == "stale":
        return body, ("⚠️ 缓存已过 %d 天窗口（%s）⇒ 以上按陈旧那份判 %s"
                      % (CACHE_MAX_AGE // 86400, detail, path))
    if source == "miss":
        return None, "缓存未命中（--offline）"
    return None, f"下载失败: {detail}"


# Surge / Clash / QuantumultX 常见条目类型
DOMAIN_TYPES = {
    "DOMAIN", "DOMAIN-SUFFIX", "DOMAIN-KEYWORD", "DOMAIN-SET",
    "HOST", "HOST-SUFFIX", "HOST-KEYWORD", "HOST-WILDCARD", "DOMAIN-WILDCARD",
}
IP_TYPES = {"IP-CIDR", "IP-CIDR6", "IP-ASN", "GEOIP", "SRC-IP-CIDR", "IP6-CIDR"}


def split_entries(body):
    """把规则集拆成条目列表；兼容 Surge 逗号式、Clash YAML `- ` 式、裸域名式。"""
    out = []
    for raw in body.split("\n"):
        l = raw.strip()
        if not l or l.startswith(("#", "//", ";", "[")):
            continue
        if l.startswith("- "):
            l = l[2:].strip()
        if l.startswith("payload"):
            continue
        # 裸域名（Egern / QuantumultX 的 Domain Set 写法）
        if "," not in l and not l.startswith("."):
            if re.fullmatch(r"[A-Za-z0-9_.*?+-]+\.[A-Za-z]{2,}", l):
                l = "DOMAIN-SUFFIX," + l
        elif l.startswith(".") and "," not in l:
            l = "DOMAIN-SUFFIX," + l.lstrip(".")
        out.append(l)
    return out


def main():
    ap = argparse.ArgumentParser(description="规则集条目类型分布 + 强制解析风险检查")
    ap.add_argument("srcs", nargs="+", help="规则集文件路径或 URL（可多个）")
    ap.add_argument("--offline", action="store_true", help="只用本地缓存，不联网")
    a = ap.parse_args()

    worst = 0
    for src in a.srcs:
        body, how = fetch(src, a.offline)
        print("=" * 88)
        print(f"来源: {src}")
        print(f"取法: {how}")
        if body is None:
            worst = max(worst, 2)
            continue

        entries = split_entries(body)
        dist = {}
        for l in entries:
            dist[l.split(",")[0].strip()] = dist.get(l.split(",")[0].strip(), 0) + 1

        n_bytes = len(body.encode("utf-8"))
        print(f"大小: {n_bytes} 字节 / {len(entries)} 条有效条目")
        print("-" * 88)
        print(f"{'类型':24s} {'条数':>8s}  说明")
        for t, c in sorted(dist.items(), key=lambda kv: -kv[1]):
            if t.upper() in DOMAIN_TYPES:
                note = "域名类 —— 能兜住域名"
            elif t.upper() in IP_TYPES:
                note = "IP 类"
            elif t.upper() in ("PROCESS-NAME", "PROCESS-PATH", "USER-AGENT"):
                note = "⚠️ Egern 未文档化类型，可能静默失效"
            else:
                note = ""
            print(f"{t:24s} {c:>8d}  {note}")

        dom = sum(c for t, c in dist.items() if t.upper() in DOMAIN_TYPES)
        ip = sum(c for t, c in dist.items() if t.upper() in IP_TYPES)
        bare = [l for l in entries
                if l.split(",")[0].strip().upper() in IP_TYPES and "no-resolve" not in l.lower()]

        print("-" * 88)
        print(f"域名条目 {dom} / IP 条目 {ip} / 裸 IP 条目（无 no-resolve）{len(bare)}")
        if dom == 0 and ip > 0:
            print("⚠️ 这是**纯 IP 规则集**：把它当域名直连规则用是无效的"
                  "（国内域名会整片落到 default）。")
        if bare:
            print(f"⚠️ 有 {len(bare)} 条 IP 条目没带 no-resolve ⇒ 每个走到该规则的域名会被"
                  f"强制本地解析一次（可能落到明文 bootstrap）。")
            for l in bare[:5]:
                print(f"     样例: {l}")
            worst = max(worst, 1)
        else:
            print("✅ 没有裸 IP 条目（不会为匹配域名而触发解析）。")
    print("=" * 88)
    return worst


if __name__ == "__main__":
    sys.exit(main())
