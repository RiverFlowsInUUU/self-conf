#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""由覆写脚本重新生成静态 profile（完整版 + .min 版）。

为什么必须有这个脚本（本仓踩过的坑）：
    改了 `override/*.js` 之后要同步重生成 `clash/profiles/*.yaml` 与 `.min.yaml`。
    此前靠临时脚本手工做，**误用追加模式把 routing.yaml 纵向堆了 7 份**
    （3294 行、7 个历史版本叠在一个文件里）。

    PyYAML 只保留最后一份，所以门禁全绿、肉眼看不出来 ——
    但用户拿到的是一个畸形文件。**手工步骤固化成脚本，才能杜绝这类错误。**

本脚本的两个硬保证：
    ① 一律**覆盖写**（"w" 模式），绝不追加
    ② 生成后立即**自检**：YAML 顶层键不得重复、组数/规则数与脚本输出一致

用法：
    python self-conf-skills/run/clash/build_profiles.py [--check]

退出码：0 = 成功/已是最新 · 1 = 有问题
"""

import os
import shutil
import re
import sys
import json
import subprocess

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

try:
    import yaml
except ImportError:
    print("需要 pyyaml：pip install pyyaml")
    sys.exit(1)

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
# 共用模块定位：`_*_common` 统一在 self-conf-skills/lib/（重组后不再与本脚本同目录）
import sys as _sys, os as _os
_d = _os.path.dirname(_os.path.abspath(__file__))
for _cand in (_os.path.normpath(_os.path.join(_d, "..", "..", "lib")),
              _os.path.normpath(_os.path.join(_d, "..", "lib")), _d):
    if any(_os.path.isfile(_os.path.join(_cand, _m)) for _m in
           ("_surge_common.py", "_egern_common.py", "_clash_common.py")):
        _sys.path.insert(0, _cand)
        break

from _clash_common import run_main  # noqa: E402




def repo_root():
    r = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
    return r


def clash_root():
    r = repo_root()
    if os.path.isdir(os.path.join(r, "clash", "profiles")):
        return os.path.join(r, "clash")
    return r


ROOT = clash_root()

# (脚本, 静态完整版, .min 版)
TARGETS = [
    ("my_clash.js", "routing.yaml", "routing.min.yaml"),
    ("my_clash_lazy.js", "lazy.yaml", "lazy.min.yaml"),
]

# 模板专属：脚本侧没有的 Smart 三档子组（机制差异，必须从静态版继承）
TEMPLATE_ONLY = ("Low Mult.", "Auto", "High Mult.")
# DNS 里交给客户端决定的键
SKIP_DNS_KEYS = {"listen"}

HEADER_ROUTING = """# ============================================================================
#  routing · 分流版（由 override/my_clash.js 生成）
# ============================================================================
#  ⚠️ 本文件由 self-conf-skills/run/clash/build_profiles.py **自动生成**，请勿手工编辑。
#     改配置请改 override/my_clash.js 后重跑本脚本。
#
#  规模：%d 个策略组 / %d 份规则集 / %d 条规则
#
# ⚠️ 导入前要改一处：
#    `proxy-providers.Airport.url` —— 换成你自己的订阅地址。
#    不换的话所有走代理的流量不通（占位地址是 example.com，不是真实服务）。
#
# 🧠 Smart 三档（本模板专属，脚本侧无此结构）：
#    Smart 为 fallback，依次回落到三个隐藏的 url-test 子组 ——
#      Low Mult.   倍率 < 1 的节点（0.01 / 0.1 / 0.5 …）· 最省钱，优先
#      Auto        正常倍率节点（节点名无倍率标记）
#      High Mult.  倍率 > 1 的节点（1.5倍 / 2倍 / 3.0x …）· 最贵，兜底
#    子组靠 filter 在运行时筛节点，故不依赖生成期可见节点名。
#
# 🔒 IPv6 显式关闭（ipv6: false + dns.ipv6: false）：不返回 AAAA 记录，
#    双栈站点自动回落 IPv4，避免本机真实 IPv6 绕过 TUN 出网。
# ============================================================================
"""

HEADER_LAZY = """# ============================================================================
#  lazy · 懒人版（由 override/my_clash_lazy.js 生成）
# ============================================================================
#  ⚠️ 本文件由 self-conf-skills/run/clash/build_profiles.py **自动生成**，请勿手工编辑。
#     改配置请改 override/my_clash_lazy.js 后重跑本脚本。
#
#  规模：%d 个策略组 / %d 份规则集 / %d 条规则
#
# ⚠️ 导入前要改一处：
#    `proxy-providers.Airport.url` —— 换成你自己的订阅地址。
#
# 🔒 IPv6 显式关闭（ipv6: false + dns.ipv6: false）。
# ============================================================================
"""


class Dumper(yaml.SafeDumper):
    def increase_indent(self, flow=False, indentless=False):
        return super().increase_indent(flow, False)


def _str_rep(dumper, data):
    BS = chr(92)
    if any(m in data for m in (BS, "(?", "^", "$", ".*")):
        return dumper.represent_scalar("tag:yaml.org,2002:str", data, style="'")
    return dumper.represent_scalar("tag:yaml.org,2002:str", data)


Dumper.add_representer(str, _str_rep)
Dumper.add_representer(dict, lambda d, x: d.represent_mapping("tag:yaml.org,2002:map", x.items()))


def inherit_template_only(script_groups, static_groups):
    """把静态版里脚本没有的模板专属组（Smart 三档）继承过来。"""
    have = {g["name"] for g in script_groups}
    out = list(script_groups)
    for g in static_groups:
        if g.get("name") in TEMPLATE_ONLY and g["name"] not in have:
            out.append(g)
    # 插到 Smart 之后，保持面板顺序
    idx = next((i for i, g in enumerate(out) if g["name"] == "Smart"), None)
    if idx is not None:
        extra = [g for g in out if g.get("name") in TEMPLATE_ONLY]
        out = [g for g in out if g.get("name") not in TEMPLATE_ONLY]
        out[idx + 1:idx + 1] = extra
    return out


def main():
    check = "--check" in sys.argv
    root = ROOT
    bad = 0

    for script, full_rel, min_rel in TARGETS:
        sp = os.path.join(root, "override", script)
        fp = os.path.join(root, "profiles", full_rel)
        mp = os.path.join(root, "profiles", min_rel)
        if not os.path.exists(sp):
            print("  NG 脚本缺失: override/%s" % script)
            bad += 1
            continue

        try:
            out = run_main(sp)
        except Exception as e:
            print("  NG %s 执行失败: %s" % (script, str(e)[:150]))
            bad += 1
            continue

        # 静态版现有内容（用于继承模板专属组）
        st = {}
        if os.path.exists(fp):
            try:
                st = yaml.safe_load(open(fp, encoding="utf-8")) or {}
            except Exception:
                st = {}

        groups = out.get("proxy-groups") or []
        if st.get("proxy-groups"):
            groups = inherit_template_only(groups, st["proxy-groups"])
        # Smart 三档必须**接进** Smart.proxies（fallback 顺序即优先级）。
        # 此前只继承了三个子组的定义，Smart.proxies 仍是脚本侧的 ["DIRECT"]，
        # 于是三档形同虚设 —— 声明了却没接上，比不声明更隐蔽。
        for g in groups:
            if g.get("name") == "Smart" and st.get("proxy-groups"):
                old = g.get("proxies") or []
                if old == ["DIRECT"] or not old:
                    g["proxies"] = ["Low Mult.", "Auto", "High Mult."]
        out["proxy-groups"] = groups

        # ⚠️ 静态形态**强制** include-all（而非 include-all-proxies）：
        #    静态 profile 自带 proxy-providers，而 include-all-proxies **不含
        #    provider 节点** ⇒ 地区组会一个节点都拿不到（用户填了订阅也不出节点）。
        #    脚本形态由 HAS_PROVIDERS 动态判断，静态形态无输入可判断，故固定取
        #    include-all（= proxies + providers，两种来源都能进组）。
        for g in out.get("proxy-groups") or []:
            if g.get("include-all-proxies"):
                g.pop("include-all-proxies", None)
                g["include-all"] = True

        # proxy-providers 段：脚本不生成（它用 include-all 直接吃节点），但
        # **静态 profile 必须有订阅槽位** —— 用户导入后要靠它填自己的订阅地址。
        # 此前从脚本输出重建时把它丢了，两份配置都没了 proxy-providers，
        # 而头注还让用户去改 `proxy-providers.Airport.url` ⇒ 用户无从下手。
        if "proxy-providers" not in out and st.get("proxy-providers"):
            out["proxy-providers"] = st["proxy-providers"]

        # tun 段：**不生成也不继承** —— 本仓只管 DNS 防泄露（dns 段）；
        # 是否开 TUN 与怎么设置（stack / 路由 / 劫持端口）交给客户端决定。
        # 覆写脚本形态本就没有 tun（客户端自管），静态 profile 保持一致，
        # 避免替用户做决定或与客户端设置冲突。
        out.pop("tun", None)

        order = ["ipv6", "proxy-providers", "proxy-groups", "rule-providers", "rules", "dns"]
        rest = [k for k in out if k not in order]
        final = {k: out[k] for k in order if k in out}
        for k in rest:
            final[k] = out[k]

        body = yaml.dump(final, Dumper=Dumper, allow_unicode=True,
                         default_flow_style=False, sort_keys=False, width=250, indent=2)

        ng = len(groups)
        nr = len(out.get("rule-providers") or {})
        nrl = len(out.get("rules") or [])
        # 保留 `#! version=` 头：本仓三内核口径一致（surge / egern 已有），
        # 若生成时丢掉，重生成一次就没了（与 tun 那次同类的覆盖丢失）。
        _ver = ""
        if os.path.exists(fp):
            with open(fp, encoding="utf-8") as _fh:
                _first = _fh.readline()
            if _first.startswith("#! version="):
                _ver = _first.strip() + chr(10)

        header = (HEADER_ROUTING if "routing" in full_rel else HEADER_LAZY) % (ng, nr, nrl)
        want = _ver + header + chr(10) + body

        have = open(fp, encoding="utf-8").read() if os.path.exists(fp) else None
        if have == want:
            print("  OK %s（已是最新：%d 组 / %d 集 / %d 条）" % (full_rel, ng, nr, nrl))
        elif check:
            print("  NG %s 已过期（脚本 %s 有更新）" % (full_rel, script))
            bad += 1
            continue
        else:
            # ① 硬保证：覆盖写
            open(fp, "w", encoding="utf-8", newline="\n").write(want)
            print("  ++ %s（已重新生成：%d 组 / %d 集 / %d 条）" % (full_rel, ng, nr, nrl))

        # .min 版：同一份数据去掉注释
        min_txt = _ver + yaml.dump(final, Dumper=Dumper, allow_unicode=True,
                                   default_flow_style=False, sort_keys=False, width=250, indent=2)
        have_m = open(mp, encoding="utf-8").read() if os.path.exists(mp) else None
        if have_m != min_txt:
            if check:
                print("  NG %s 已过期" % min_rel)
                bad += 1
                continue
            open(mp, "w", encoding="utf-8", newline="\n").write(min_txt)
            print("  ++ %s（已重新生成）" % min_rel)
        else:
            print("  OK %s（已是最新）" % min_rel)

        # ② 硬保证：自检（防纵向堆叠这类畸形）
        raw = open(fp, encoding="utf-8").read()
        keys = [l.split(":")[0] for l in raw.split("\n")
                if l and not l[0].isspace() and not l.startswith("#") and ":" in l]
        dup = {k for k in keys if keys.count(k) > 1}
        if dup:
            print("  NG %s 顶层键重复（疑似重复粘贴）：%s" % (full_rel, sorted(dup)))
            bad += 1
            continue
        try:
            parsed = yaml.safe_load(raw)
        except Exception as e:
            print("  NG %s YAML 解析失败: %s" % (full_rel, e))
            bad += 1
            continue
        if not parsed.get("proxy-providers"):
            print("  NG %s 缺 proxy-providers（用户无从填订阅）" % full_rel)
            bad += 1
            continue
        _sm = next((g for g in parsed.get("proxy-groups", [])
                    if g.get("name") == "Smart"), None)
        if _sm and "Low Mult." in {g.get("name") for g in parsed.get("proxy-groups", [])}                 and (_sm.get("proxies") or []) == ["DIRECT"]:
            print("  NG %s Smart 未接上三档（声明了却没连）" % full_rel)
            bad += 1
            continue
        if parsed.get("tun"):
            print("  NG %s 仍带 tun 段（应由客户端决定）" % full_rel)
            bad += 1
            continue
        if len(parsed.get("proxy-groups") or []) != ng or len(parsed.get("rules") or []) != nrl:
            print("  NG %s 自检不一致（解析结果与脚本输出不符）" % full_rel)
            bad += 1
            continue
        print("     自检通过：无重复键 · 解析后 %d 组 / %d 条" % (ng, nrl))

    print("-" * 78)
    if bad:
        print("有 %d 项需要处理" % bad)
        return 1
    print("全部完成")
    return 0


if __name__ == "__main__":
    sys.exit(main())
