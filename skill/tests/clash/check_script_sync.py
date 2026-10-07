#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""脚本输出 vs 静态 profile 对拍 —— 同一套配置的两种交付形态必须逐位一致。

为什么单独要这一项（本仓特有，姊妹仓没有）：
    本仓每份 profile 都有两个交付形态：
      · 静态文件  profiles/routing.yaml  —— 下载即用
      · 覆写脚本  override/my_clash.js   —— 挂到任意订阅上
    两者是**同一套配置**的两种形态，脚本的输出就应该是静态文件的样子。

    一旦漂移，用户会遇到「照文档用脚本订阅，效果跟直接导入配置不一样」，
    而且两边都能正常跑、都不报错 —— 只能靠对拍发现。

判据：
    · 以空订阅执行脚本（无 proxies、无 proxy-providers）
    · 取其 proxy-groups / rule-providers / rules / dns / ipv6
    · 与静态 profile 的对应字段比对（比 Python 对象，不看注释/缩进）
    · 已知差异走白名单（模板专属的 Smart 三档子组；DNS 的 listen 端口）

退出码：0 = 一致 · 1 = 有漂移 · 2 = 环境/解析问题
用法：python skill/tests/check_script_sync.py [仓库根]
"""

import os
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
    sys.exit(2)

def _default_root():
    """仓库根；整合仓里 clash 配置位于 clash/ 子目录，自动识别。"""
    r = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", ".."))
    if os.path.isdir(os.path.join(r, "clash", "profiles")):
        return os.path.join(r, "clash")
    return r

ROOT = sys.argv[1] if len(sys.argv) > 1 else _default_root()
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "scripts", "clash")))
try:
    from _clash_common import run_main
except Exception:
    run_main = None

# (脚本, 对应静态 profile) —— 模板专属、脚本里没有的组名
PAIRS = [
    ("override/my_clash.js", "profiles/routing.yaml"),
    ("override/my_clash_lazy.js", "profiles/lazy.yaml"),
]

# 静态模板专属：Smart 三档子组（脚本侧 Smart 是单组 fallback）
# 这是**有意**的差异：模板能用 filter 在运行时分档，脚本做不到（生成期看不到节点名）
TEMPLATE_ONLY_GROUPS = {"Low Mult.", "Auto", "High Mult."}

# 已知且**有意**的差异：(组名, 说明)。命中则不判负，但仍打印提醒。
# Smart 是唯一一处：模板靠 filter 在运行时分三档，脚本做不到（生成期看不到节点名），
# 故脚本侧是单组 fallback、模板侧是三档 —— 这是内核机制决定的，不是漂移。
EXPECTED_DIFF = {
    "Smart": "模板三档 fallback vs 脚本单组 fallback（机制差异，非漂移）",
}
# 交给客户端决定的键，不参与比对
SKIP_DNS_KEYS = {"listen"}


def norm_dns(d, keys):
    """去掉交给客户端决定的键（如 DNS 监听端口）后再比对。"""
    return {k: v for k, v in (d or {}).items() if k not in keys}


def run_script(path):
    """执行脚本取结果（走共用模块，处理 node 定位与编码）。"""
    if run_main is None:
        raise RuntimeError("无法导入 _clash_common")
    return run_main(path)


def main():
    print("脚本输出 vs 静态 profile 对拍")
    print("-" * 78)
    bad = 0
    for script, profile in PAIRS:
        sp = os.path.join(ROOT, script)
        pp = os.path.join(ROOT, profile)
        if not (os.path.exists(sp) and os.path.exists(pp)):
            print("  NG 缺文件: %s 或 %s" % (script, profile))
            bad += 1
            continue
        try:
            out = run_script(sp)
        except Exception as e:
            print("  NG %s 执行失败: %s" % (script, e))
            bad += 1
            continue
        st = yaml.safe_load(open(pp, encoding="utf-8"))

        errs = []
        notes = []

        # 规则：逐位一致
        if out.get("rules") != (st.get("rules") or []):
            errs.extend(diff(out.get("rules") or [], st.get("rules") or [], "rules"))

        # 规则集：URL 必须一致（键名可差，取 URL 集合比）
        su = {v.get("url") for v in (out.get("rule-providers") or {}).values()}
        pu = {v.get("url") for v in (st.get("rule-providers") or {}).values()}
        if su != pu:
            errs.append("规则集 URL 不同: 仅脚本 %s / 仅静态 %s"
                        % (sorted(su - pu), sorted(pu - su)))

        # 策略组：脚本组 + 模板专属组 = 静态组
        sg = {g["name"] for g in out.get("proxy-groups") or []}
        pg = {g["name"] for g in st.get("proxy-groups") or []}
        if not (sg | TEMPLATE_ONLY_GROUPS) >= pg:
            errs.append("静态有脚本无的组: %s" % sorted(pg - sg - TEMPLATE_ONLY_GROUPS))

        # 其余组（非模板专属）的子节点必须一致
        sgm = {g["name"]: g.get("proxies") or [] for g in out.get("proxy-groups") or []}
        pgm = {g["name"]: g.get("proxies") or [] for g in st.get("proxy-groups") or []}
        for n in sorted(sg & pg):
            if n in TEMPLATE_ONLY_GROUPS:
                continue
            a = sgm.get(n) or []
            b = pgm.get(n) or []
            if a != b:
                if n in EXPECTED_DIFF:
                    notes.append("已知差异 %s: %s" % (n, EXPECTED_DIFF[n]))
                else:
                    errs.append("组 %s 子节点不同: 脚本 %s vs 静态 %s" % (n, a, b))

        # DNS：除 listen 外逐键一致
        if norm_dns(out.get("dns"), SKIP_DNS_KEYS) != norm_dns(st.get("dns"), SKIP_DNS_KEYS):
            errs.extend(diff(norm_dns(out.get("dns"), SKIP_DNS_KEYS),
                             norm_dns(st.get("dns"), SKIP_DNS_KEYS), "dns"))

        # ipv6
        if out.get("ipv6") != st.get("ipv6"):
            errs.append("ipv6 不同: 脚本 %s vs 静态 %s" % (out.get("ipv6"), st.get("ipv6")))

        if errs:
            bad += 1
            print("  NG %s vs %s —— %d 处" % (script, profile, len(errs)))
            for e in errs[:12]:
                print("       ", e)
            if len(errs) > 12:
                print("        ... 另 %d 处" % (len(errs) - 12))
        else:
            if notes:
                for nt in notes:
                    print("     ~ %s" % nt)
            print("  OK %s" % script)
    print("-" * 78)
    if bad:
        print("漂移 %d 处" % bad)
        return 1
    print("全部一致")
    return 0


if __name__ == "__main__":
    sys.exit(main())
