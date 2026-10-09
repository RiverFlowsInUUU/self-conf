#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CI↔verify_all 清单对账 —— 机器守住「两边闸门清单手工双写」的债。

为什么需要（见 verify_all.py 设计约定「已知挂账」与 gates.md §16.4）：
    「要跑哪些检查」这份清单横跨两个文件：`verify_all.py` 的 `build_gates()`
    是闸门真源，但 `ci.yml` 除了调用 verify_all，还**额外硬编码**了几个直接
    跑的脚本（F821 重复跑 / cp936 重跑 / 两个联网探测）。两边靠人肉保持一致
    —— 一旦一侧增删脚本、另一侧没同步，本地与 CI 跑的就不一样，而没人会
    发现，直到某天本地绿 CI 红（或反过来）才炸出来。本闸门把这份「双写」
    变成**机器对账**：ci.yml 里每个 `python <脚本>` 调用必须能被明确归类，
    否则判负。

对账三条（缺一不可）：
    1. ci.yml 里每个 `python <脚本>` 路径必须真实存在 —— 抓「改名 / 挪目录
       而 ci.yml 没跟上」（DNS 审计 run/→gates/ 那次重组正是这类，当时
       三道审计静默消失，靠人眼才发现）。
    2. 主 Gates 步骤必须调用 `verify_all.py` —— 这是「同源」的锚点，
       被换成任何别的命令即失效。
    3. 除 verify_all 自身外，ci.yml 里每个脚本必须落在两张登记表之一：
         · CI_ONLY   —— 设计上只在 CI 跑（联网探测，抖动会假红，故不进闸门）
         · DUPLICATE —— 刻意在 CI 日志里**再跑一遍**的闸门（要独立可见的一行）
       未登记 = 有人往 ci.yml 加了脚本却没想清楚它与闸门清单的关系 ⇒ 判负。

退出码：0 = 对上 ｜ 1 = 对不上（清单漂移） ｜ 2 = 解析不了 ci.yml（环境/语法）
用法：python self-conf-skills/gates/check_ci_sync.py
"""

import os
import re
import subprocess
import sys

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

_ROOT = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", ".."))
CI_YML = os.path.join(_ROOT, ".github", "workflows", "ci.yml")
VERIFY_ALL = os.path.join(_ROOT, "self-conf-skills", "gates", "verify_all.py")
PY = sys.executable or "python"

# ── 两张登记表：ci.yml 里除 verify_all 外每个脚本都必须在其中一张 ──────────
#    新增 CI 步骤时**必须**在这里登记理由 —— 这不是挡路，是逼你想清楚
#    「它和闸门清单是什么关系」。键 = ci.yml 里的脚本相对路径。
CI_ONLY = {
    "self-conf-skills/gates/clash/check_remote_urls.py":
        "联网取远端规则集可达性；网络抖动会假红 ⇒ 不进闸门，CI 里兜底",
    "self-conf-skills/run/egern/probe_dns_endpoints.py":
        "联网实测每个加密 DNS 端点；抖动假红 ⇒ 不进闸门，CI 里兜底",
}
DUPLICATE = {
    "self-conf-skills/gates/check_undefined_names.py":
        "F821 已是闸门「未定义名扫描」；CI 再跑一遍是为了在日志里有独立可见的一行",
}

_PY_SCRIPT = re.compile(r"python\s+(\S+\.py)")


def _gate_scripts():
    """现抓 verify_all 的闸门脚本集合（勿手抄成死表）。返回 set(相对路径)。"""
    p = subprocess.run([PY, VERIFY_ALL, "--index"],
                       capture_output=True, cwd=_ROOT)
    out = (p.stdout + p.stderr).decode("utf-8", errors="replace")
    if p.returncode not in (0,):
        print("无法解析 verify_all --index（退出码 %d）" % p.returncode)
        sys.exit(2)
    scripts = set()
    for line in out.splitlines():
        s = line.strip()
        # 闸门命令行是缩进行，形如：self-conf-skills/gates/xxx.py [args]
        if s.startswith("self-conf-skills/") and ".py" in s:
            scripts.add(s.split()[0])
    if not scripts:
        print("verify_all --index 没解析出任何闸门脚本 —— 输出格式变了？")
        sys.exit(2)
    return scripts


def _ci_scripts():
    """抽取 ci.yml 里所有 `python <脚本>.py` 的脚本路径（跳过 python -m）。"""
    import yaml
    with open(CI_YML, "r", encoding="utf-8") as f:
        doc = yaml.safe_load(f)
    if not isinstance(doc, dict) or "jobs" not in doc:
        print("ci.yml 解析不出 jobs —— 语法变了？")
        sys.exit(2)
    found = []   # list of (step_name, script_relpath)
    for jname, job in doc.get("jobs", {}).items():
        for step in (job or {}).get("steps", []) or []:
            run = step.get("run") if isinstance(step, dict) else None
            if not run:
                continue
            for m in _PY_SCRIPT.finditer(run):
                found.append((step.get("name", jname), m.group(1)))
    return found


def main():
    print("CI↔verify_all 清单对账")
    print("-" * 78)

    try:
        import yaml  # noqa: F401
    except ImportError:
        print("环境缺 pyyaml，无法解析 ci.yml")
        return 2

    if not os.path.isfile(CI_YML):
        print("找不到 ci.yml：%s" % CI_YML)
        return 2

    gate_set = _gate_scripts()
    ci_calls = _ci_scripts()
    if not ci_calls:
        print("ci.yml 里没解析出任何 `python <脚本>` 调用 —— 步骤结构变了？")
        return 2

    problems = []
    runner_seen = False

    # ── 条款 2 的锚点：主 Gates 步骤必须调用 verify_all.py ──────────────
    named_gates_step = [
        (nm, sc) for nm, sc in ci_calls
        if nm.startswith("Gates") or nm.startswith("Gates (")
    ]
    if not any(sc.endswith("verify_all.py") for _, sc in named_gates_step):
        problems.append("主 Gates 步骤没在调用 verify_all.py（同源锚点失效）")

    for step_name, script in ci_calls:
        abs_path = os.path.join(_ROOT, script)
        # 条款 1：脚本必须真实存在
        if not os.path.isfile(abs_path):
            problems.append("ci.yml 步骤「%s」引用的脚本不存在：%s"
                            "（改名/挪目录没同步？）" % (step_name, script))
            continue
        # verify_all 自身（主 Gates / cp936 重跑）→ runner，放行
        if script.endswith("verify_all.py"):
            runner_seen = True
            continue
        # 条款 3：其余脚本必须被显式登记
        if script in gate_set:
            if script not in DUPLICATE:
                problems.append(
                    "ci.yml 步骤「%s」重复跑闸门 %s，却没在 DUPLICATE 登记理由"
                    "（要么登记，要么它不该在 ci.yml 单独跑）" % (step_name, script))
        else:
            if script not in CI_ONLY:
                problems.append(
                    "ci.yml 步骤「%s」的脚本 %s 既不是闸门、也没在 CI_ONLY 登记"
                    "（加 CI 步骤要想清楚它与闸门清单的关系）" % (step_name, script))

    # 登记表里不许有死条目（脚本删了/改名了，登记要跟着清）
    for script in list(CI_ONLY) + list(DUPLICATE):
        if not os.path.isfile(os.path.join(_ROOT, script)):
            problems.append("登记表里有死条目（脚本已不存在）：%s" % script)

    if not runner_seen:
        problems.append("ci.yml 里没找到任何 verify_all.py 调用")

    if problems:
        for p in problems:
            print("  NG " + p)
        print("\n清单对不上 —— %d 处漂移。修 ci.yml 或登记表，别让两边各说各话。"
              % len(problems))
        return 1

    print("  OK ci.yml %d 处 python 调用全部归类清楚" % len(ci_calls))
    print("      · verify_all runner ×%d"
          % sum(1 for _, sc in ci_calls if sc.endswith("verify_all.py")))
    print("      · 闸门重复跑（DUPLICATE）×%d"
          % sum(1 for _, sc in ci_calls if sc in DUPLICATE))
    print("      · CI-only 联网兜底（CI_ONLY）×%d"
          % sum(1 for _, sc in ci_calls if sc in CI_ONLY))
    print("TOTAL: ci↔verify_all 清单一致")
    return 0


if __name__ == "__main__":
    sys.exit(main())
