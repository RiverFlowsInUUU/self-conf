#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""判别力回归 —— 注错样例常驻跑，守住「闸门改坏了还能全绿」这个盲区。

为什么需要（本仓已知挂账，见 gates.md §9.3 / §16.4）：
    一道闸门「跑一遍是绿的」证明不了它有效 —— 现役配置永远是好的，
    判据被改坏后照样全绿，直到真出事那天给不出诊断。判别力只能靠
    「喂坏配置、断言判负」来证明。此前仓里只有跨内核的
    `check_region_filters.py` 把判负样例做进了常驻 CI；本闸门把剩下
    4 道**判负样例已人工实测**的闸门补上同等回归：

      1. `check_structure`          —— 插入引用了未定义规则集的规则
      2. `check_min_pair`           —— 往 .min 里加一行规则（内容漂移）
      3. `check_script_sync`        —— 静态 profile 与脚本规则长度不一致
      4. `build_rules.py --check`   —— 真源 .list 有更新、生成物未重跑

怎么做的（照抄 check_region_filters 的断言口径）：
    临时目录里搭一份最小仓库副本（真仓工作副本一个字节不动），对副本
    注入已知错误，断言「退出码 = 1 且输出含预期标记」两条 —— 因为闸门
    崩了（如 NameError / UnicodeEncodeError）同样以退出码 1 结束，
    只有输出标记能证明它判的是**这条**错。退出码 2 是闸门自己的
    环境失败，不计入判负。

退出码：0 = 全部判负（判别力在位）· 1 = 有闸门没判负（判别力失效，必须查）
       2 = 基线不绿或环境缺失（判据本身有问题，不是判别力问题）
用法：python self-conf-skills/gates/check_negative_fixtures.py
"""

import os
import shutil
import subprocess
import sys
import tempfile

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

_ROOT = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", ".."))
PY = sys.executable or "python"


def _has_node():
    return shutil.which("node") is not None


def _build_sandbox(dst):
    """把 4 道闸门所需扫描面的最小文件集拷进沙箱。

    只拷会注错、会被读的文件，不拷 .git / 门禁脚本本身
    —— 门禁脚本跑在原仓（保证读到的是当前版本），ROOT 指向沙箱。
    """
    files = [
        "AGENTS.md",                    # lib/paths.py 上溯标志物
        "surge/profiles/routing.conf",  # lib/paths.py 上溯标志物
        "surge/profiles/lazy.conf",
        "surge/profiles/routing.min.conf",
        "surge/profiles/lazy.min.conf",
        "egern/profiles/lazy.yaml",
        "egern/profiles/routing.yaml",
        "egern/profiles/lazy.min.yaml",
        "egern/profiles/routing.min.yaml",
        "clash/profiles/lazy.yaml",
        "clash/profiles/routing.yaml",
        "clash/profiles/lazy.min.yaml",
        "clash/profiles/routing.min.yaml",
        "clash/override/my_clash.js",
        "clash/override/my_clash_lazy.js",
        "rules/emby.list", "rules/emby.yaml",
        "rules/apple_system.list", "rules/apple_system.yaml",
        "rules/AI.list", "rules/AI_Domains.yaml",
        "self-conf-skills/lib/paths.py",
        "self-conf-skills/run/clash/build_rules.py",
    ]
    for rel in files:
        src = os.path.join(_ROOT, rel)
        out = os.path.join(dst, rel)
        os.makedirs(os.path.dirname(out), exist_ok=True)
        shutil.copyfile(src, out)


def _mutate(path, old, new):
    """按字节替换注入错误；注错没命中锚点直接算环境失败（exit 2）。"""
    with open(path, "r", encoding="utf-8", newline="") as f:
        text = f.read()
    if old not in text:
        print("  注错锚点没找到：%s 里的 %r" % (path, old[:60]))
        sys.exit(2)
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(text.replace(old, new, 1))


def _run(argv):
    p = subprocess.run(argv, capture_output=True)
    out = (p.stdout + p.stderr).decode("utf-8", errors="replace")
    return p.returncode, out


def _case(name, mutate, argv, marker):
    """一条判负用例：注错 → 断言「退出码=1 且输出含标记」两条。"""
    mutate()
    rc, out = _run(argv)
    problems = []
    if rc != 1:
        problems.append("退出码 %d（应为 1）" % rc)
    if marker not in out:
        problems.append("输出无标记 %r" % marker)
    if problems:
        print("  NG %-28s %s" % (name, "；".join(problems)))
        print("       输出尾部：")
        for line in out.strip().splitlines()[-4:]:
            print("       " + line)
        return False
    print("  OK %-28s 判负 exit=1 + 标记 %r" % (name, marker))
    return True


def main():
    print("判别力回归（判负样例常驻）")
    print("-" * 78)

    missing = []
    if not _has_node():
        missing.append("node（check_script_sync 要执行 override 脚本）")
    try:
        import yaml  # noqa: F401
    except ImportError:
        missing.append("pyyaml")
    if missing:
        print("环境缺依赖，无法验证判别力：" + "、".join(missing))
        return 2

    sb = tempfile.mkdtemp(prefix="self-conf-negfix-")
    try:
        _build_sandbox(sb)

        GATES = os.path.join(_ROOT, "self-conf-skills", "gates")
        clash_sb = os.path.join(sb, "clash")

        # ---- 基线：未注错时每道都必须放行，否则判据本身有问题（非判别力问题）
        baselines = [
            ("check_structure",
             [PY, os.path.join(GATES, "clash", "check_structure.py"), clash_sb]),
            ("check_min_pair",
             [PY, os.path.join(GATES, "check_min_pair.py"), sb]),
            ("check_script_sync",
             [PY, os.path.join(GATES, "clash", "check_script_sync.py"), clash_sb]),
            ("build_rules --check",
             [PY, os.path.join(sb, "self-conf-skills", "run", "clash",
                               "build_rules.py"), "--check"]),
        ]
        for nm, argv in baselines:
            rc, out = _run(argv)
            if rc != 0:
                print("基线不绿：%s 在未注错的副本上退出码 %d —— 判据本身有问题，"
                      "不是判别力问题。输出尾部：" % (nm, rc))
                for line in out.strip().splitlines()[-6:]:
                    print("  " + line)
                return 2
        print("  基线 4/4 绿（未注错的副本全部放行）")

        passed = 0

        # 1 · check_structure：规则引用了未定义的规则集
        c1 = _case(
            "check_structure",
            lambda: _mutate(
                os.path.join(clash_sb, "profiles", "lazy.yaml"),
                "  - RULE-SET,Jinx-CN,DIRECT\n",
                "  - RULE-SET,ghost-set,DIRECT\n"),
            baselines[0][1],
            "规则引用了未定义的规则集: ghost-set")
        passed += c1

        # 2 · check_min_pair：.min 里加一行规则（与完整版漂移）
        c2 = _case(
            "check_min_pair",
            lambda: _mutate(
                os.path.join(clash_sb, "profiles", "lazy.min.yaml"),
                "rules:\n",
                "rules:\n  - DOMAIN-SUFFIX,negfix-probe.example,DIRECT\n"),
            baselines[1][1],
            "去注释后仍有差异")
        passed += c2

        # 3 · check_script_sync：静态 profile 的规则比脚本少一条
        c3 = _case(
            "check_script_sync",
            lambda: _mutate(
                os.path.join(clash_sb, "override", "my_clash_lazy.js"),
                '    "RULE-SET,Jinx-CN,DIRECT",\n',
                ""),
            baselines[2][1],
            "长度不同")
        passed += c3

        # 4 · build_rules --check：真源 .list 有更新、生成物未重跑
        c4 = _case(
            "build_rules --check",
            lambda: _mutate(
                os.path.join(sb, "rules", "AI.list"),
                "# NAME: AI_Domains (AI 全量整合集 · Surge ruleset)\n",
                "# NAME: AI_Domains (AI 全量整合集 · Surge ruleset)\nnegfix-probe.example\n"),
            baselines[3][1],
            "已过期")
        passed += c4

        print("\nTOTAL: %d discriminating, %d not" % (passed, 4 - passed))
        return 0 if passed == 4 else 1
    finally:
        shutil.rmtree(sb, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
