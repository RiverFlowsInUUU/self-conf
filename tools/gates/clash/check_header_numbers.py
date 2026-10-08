#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""头注数字新鲜度 —— 注释/文档里写死的规模数字必须与脚本实际输出一致。

为什么单独要这一项（本仓踩过的坑）：
    脚本头注、README、profile 头注里常常写着「22 个策略组 / 25 份规则集 /
    27 条规则」这类数字。它们是**手写的**，改了策略组或规则之后如果不
    同步更新，就会变成过期信息 —— 而门禁一条都不查，全绿。

    本仓实测：my_clash.js 头注长期写着「20 组 / 20 集 / 26 条」，
    而脚本实际输出是 22 / 25 / 27。直到人工核对才被发现。

    这类漂移必然复发（数字天然会随改动过期），故必须落成判据。

判据：
    · 跑 override/*.js 的 main() 拿真实规模（组数 / 规则集数 / 规则数）
    · 在脚注文件自身、README、profile 头注里找对应数字
    · 出现与实际不符的**旧数字**即判负
    · 只认「明确的规模声明」上下文，避免误伤无关数字

退出码：0 = 一致 · 1 = 存在过期数字 · 2 = 环境问题
用法：python tools/gates/clash/check_header_numbers.py [仓库根]
"""

import os
import sys as _sys
_sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'scripts', 'clash'))
# 共用模块定位：`_*_common` 统一在 tools/lib/（重组后不再与本脚本同目录）
import sys as _sys, os as _os
_d = _os.path.dirname(_os.path.abspath(__file__))
for _cand in (_os.path.normpath(_os.path.join(_d, "..", "..", "lib")),
              _os.path.normpath(_os.path.join(_d, "..", "lib")), _d):
    if any(_os.path.isfile(_os.path.join(_cand, _m)) for _m in
           ("_surge_common.py", "_egern_common.py", "_clash_common.py")):
        _sys.path.insert(0, _cand)
        break

from _clash_common import default_root  # noqa: E402  全仓唯一实现
import re
import sys



try:
    import yaml
except ImportError:
    yaml = None

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..", "scripts", "clash")))




ROOT = sys.argv[1] if len(sys.argv) > 1 else default_root()

# (脚本, 关键规模上下文的正则, 说明)
# 只匹配「N 个策略组」「N 份规则集」「N 条规则」这类明确声明
CONTEXT = [
    (r"(\d+)\s*个策略组", "groups"),
    (r"(\d+)\s*份规则集", "providers"),
    (r"(\d+)\s*条规则", "rules"),
]

# ── 子项拆分（第二轮外部审查第 3 / 4 条）
# 此前「10 份规则集（5 份 MRS + 5 份 yaml）」只校验总数 10 ⇒ 拆分写成 5+5 也放行，
# 实际是 6+4。这里把「N 份 MRS」「N 份 yaml」的声明也拉进来对拍。
SUBITEM = [
    (r"(\d+)\s*份\s*MRS", "mrs"),
    (r"(\d+)\s*份\s*yaml", "yaml"),
]

# 每个脚本对应的规模键
SCRIPTS = ["my_clash.js", "my_clash_lazy.js"]

# 要扫描的文件（相对 ROOT）
SCAN = [
    "override/my_clash.js",
    "override/my_clash_lazy.js",
    "profiles/routing.yaml",
    "profiles/lazy.yaml",
]


def static_sizes(path):
    """静态 profile 的真实规模。

    ⚠️ 静态版比脚本输出多 3 个组（Low Mult. / Auto / High Mult.，
    是 Smart 的三档子组，模板专属）。这是**已知差异**不是过期，
    故静态文件用自身实际值做真值，不用脚本输出的组数。
    """
    if yaml is None:
        return None
    try:
        c = yaml.safe_load(open(path, encoding="utf-8"))
    except Exception:
        return None
    return {
        "groups": len(c.get("proxy-groups") or []),
        "providers": len(c.get("rule-providers") or {}),
        "rules": len(c.get("rules") or []),
    } | _split(c.get("rule-providers") or {})


def _split(providers):
    """rule-providers 的 MRS / yaml 拆分 —— 给「N 份 MRS + N 份 yaml」这类声明当真源。"""
    mrs = yaml_ = 0
    for v in (providers or {}).values():
        if not isinstance(v, dict):
            continue
        u = str(v.get("url") or v.get("path") or "")
        f = str(v.get("format") or "").lower()
        if f == "yaml" or u.endswith((".yaml", ".list")):
            yaml_ += 1
        else:
            mrs += 1
    return {"mrs": mrs, "yaml": yaml_}


def real_sizes(script_path):
    try:
        from _clash_common import run_main
    except Exception as e:
        print("无法导入 _clash_common: %s" % e)
        return None
    try:
        out = run_main(script_path)
    except Exception as e:
        print("  ! %s 执行失败: %s" % (os.path.basename(script_path), str(e)[:120]))
        return None
    return {
        "groups": len(out.get("proxy-groups") or []),
        "providers": len(out.get("rule-providers") or {}),
        "rules": len(out.get("rules") or []),
    } | _split(out.get("rule-providers") or {})


def main():
    print("头注数字新鲜度检查")
    print("-" * 78)

    # 取各脚本的真实规模
    real = {}
    for sc in SCRIPTS:
        p = os.path.join(ROOT, "override", sc)
        if not os.path.exists(p):
            continue
        r = real_sizes(p)
        if r:
            real[sc] = r
            print("  %s 实际：%d 组 / %d 集 / %d 条"
                  % (sc, r["groups"], r["providers"], r["rules"]))

    if not real:
        print("  未能取得任何脚本的真实规模 ⇒ 未验证，不是通过")
        return 2

    bad = []
    for rel in SCAN:
        p = os.path.join(ROOT, rel)
        if not os.path.exists(p):
            continue
        try:
            txt = open(p, encoding="utf-8").read()
        except Exception:
            continue

        # 真值选择：
        #   · profiles/*   → 用静态文件自身实际值（含 Smart 三档，已知差异）
        #   · override/*   → 用脚本输出真值，且**按行**判断说的是哪个脚本
        #                    （README 里 lazy 与 routing 两行并存，按文件名会误判）
        static_truth = None
        if rel.startswith("profiles/"):
            static_truth = static_sizes(p)
            if not static_truth:
                continue

        for i, line in enumerate(txt.split(chr(10)), 1):
            stripped = line.strip()
            if not (stripped.startswith(("#", "//", ";", "|")) or stripped.startswith("*")):
                continue
            # 产品线判断：文件名优先（my_clash_lazy.js 的行里未必有 "lazy" 字样），
            # 只有 README 这类混排文件才退回按行判断。
            if "lazy" in rel:
                is_lazy = True
            elif "my_clash" in rel or "routing" in rel:
                is_lazy = False
            else:
                is_lazy = "lazy" in line.lower()
            key = "my_clash_lazy.js" if is_lazy else "my_clash.js"
            if static_truth is not None:
                truth = static_truth
            else:
                truth = real.get(key)
                if not truth:
                    continue
            for pat, kind in CONTEXT:
                for m in re.finditer(pat, line):
                    n = int(m.group(1))
                    want = truth[kind]
                    if n != want:
                        bad.append((rel, i, kind, n, want, stripped[:70]))
            # 子项：只在 truth 里有对应键时才判（避免对不带拆分声明的文件误报）
            for pat, kind in SUBITEM:
                if kind not in truth:
                    continue
                for m in re.finditer(pat, line, re.I):
                    n = int(m.group(1))
                    want = truth[kind]
                    if n != want:
                        bad.append((rel, i, kind, n, want, stripped[:70]))

    if bad:
        # 去重
        seen = set()
        uniq = []
        for b in bad:
            k = (b[0], b[1], b[2], b[3])
            if k not in seen:
                seen.add(k)
                uniq.append(b)
        print("-" * 78)
        print("过期数字 %d 处（文档写的 vs 脚本实际）：" % len(uniq))
        for rel, ln, kind, got, want, ctx in uniq[:20]:
            print("  NG %s:%d  %s 写 %d，实际 %d" % (rel, ln, kind, got, want))
            print("       %s" % ctx)
        if len(uniq) > 20:
            print("  ... 另 %d 处" % (len(uniq) - 20))
        print("-" * 78)
        print("修法：把文档里的数字改成实际值；或若该处本就不是规模声明，"
              "调整 check_header_numbers.py 的上下文正则")
        return 1

    print("-" * 78)
    print("一致 —— 头注/文档里的规模数字与脚本实际输出相符")
    return 0


if __name__ == "__main__":
    sys.exit(main())
