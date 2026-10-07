#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""地区组审计器的**判别力**回归 —— 用判负 fixture 证明脚本真的在工作。

为什么必须有这一道
──────────────────
`audit_region_filters.py` 判的是「地区组 filter 有没有把节点归对」
（关键词是否同步进 `Other Regions` 的负向断言 / 是否覆盖常见写法 / 是否互斥）。
它平时跑在**现役配置**上、输出一片 ✅ ——
但「一片 ✅」有两种可能，且**从输出上看不出来**：

  ① 现役配置真的同步了；          ← 我们要的
  ② 审计器根本没工作（组名改了、负向断言解析失败、异常被吞成 0）。← 静默假绿

所以只测「好配置通过」是**证明不了判别力**的。本闸门拿**故意损坏**的
fixture 喂进去，**期望它们被报错并判负**；再拿现役配置做一次正向对照。
两侧合计才知道审计器「既会放行、也会拦住」。

覆盖范围：三内核 ×（现役放行 + fixture 判负）= 6 条用例
─────────────────────────────────────────────────────
  Surge  `skill/scripts/surge/audit_region_filters.py`  + surge/fixtures/
  Egern  `skill/scripts/egern/audit_region_filters.py`  + egern/fixtures/
  clash  `skill/scripts/clash/audit_region_filters.py`  + clash/fixtures/
    └─ mihomo 侧 2026-10-07 补入：此前它的 6 个地区组**完全无人管**
       （`reference/clash/profile-anatomy.md` §8.3 明确记着"mihomo 侧目前没有这个比对器"）。

⚠️ 为什么不能只断言退出码
────────────────────────
`_surge_common.force_utf8_stdout` 的注释写过一次事故：审计器**崩了**（emoji 触发
`UnicodeEncodeError`）同样以退出码 1 结束 —— 而 fixture 期望的**恰恰也是 1**。
两者的区别只能在**输出**里看。所以本闸门对 fixture 的断言是**两条**：
  ① 退出码 == 1（判负）；
  ② stdout/stderr 里出现那个**故意注入**的关键词（如 `港区`）—— 证明是"报出了这一条"，
     不是"崩在别处"。
退出码 2（环境/解析失败）被单独判为**闸门自身失败**，绝不当作"判负成功"。

注入的关键词为什么选 `港区`
──────────────────────────
它必须：① 是合法正则、② 不与其他地区组关键词重叠（否则会额外触发判据③，
报错原因就不唯一了）、③ 现役配置里不存在。
`港区` 满足三条（见 fixture 头注）。

⚠️ clash 侧 fixture 的损坏方向**相反**
─────────────────────────────────────
Surge / Egern 的 fixture 是往 `Hong Kong` 里**多加**一个未同步词 `港区`；
clash 侧的判据是「关键词**覆盖**」，加词测不出来 —— 故它**删掉**本该有的词
（`Taiwan` 删 `台`、`Japan` 删 `日`/`JP`、`Other Regions` 删 `Taiwan|Tai`）。
两种方向都要有：加词测"排除得过窄"，删词测"覆盖不全"。

退出码：0 = 判别力成立；1 = 有断言不成立；2 = 前置环境不达标（fixture / profile 缺失）。
用法：python skill/tests/check_region_filters.py [仓库根]
"""

import os
import subprocess
import sys

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PY = sys.executable or "python"

# 注入进 Surge / Egern fixture 的那个"未同步关键词"。
# ⚠️ clash 侧 fixture 的损坏方式**相反**（删词而非加词），故定位标记另取，见下。
INJECTED = "港区"

# (名称, argv, 期望退出码, 期望输出里出现的定位标记)
# 标记 = 「真报出了这一条」的证据，用来把「报出并判负」与「崩在别处也返回 1」分开。
# ⚠️ 三个脚本的诊断粒度不同，标记也不同（都足以证明"报的是这条判据"，不是环境崩溃）：
#   · Surge 侧逐 **token** 比对，能点名到关键词 ⇒ 标记 = 注入词 `港区`；
#   · Egern 侧做 **整串**比对（见其 docstring「为什么是逐字包含」），只能点名到组 ⇒
#     标记 = 组名 `Hong Kong`；
#   · clash 侧逐 **词** 比对（判据②）并能点名到组（判据⑤）⇒ 标记 = `Taiwan` 组名。
#     ⚠️ 为什么不是 `台`：它是合法正则且能被点名，但**只有一个字符**，
#        在"崩了"的输出里撞上的概率不为零（如堆栈里的中文字），会削弱标记的定位价值；
#        组名 `Taiwan` 是 ASCII、且必然出现在判据⑤的报错句里 —— 见下方 CASES 注释。
CASES = [
    ("Surge 现役配置 → 应放行",
     [PY, "skill/scripts/surge/audit_region_filters.py", "surge/profiles/routing.conf"], 0, None),
    ("Surge 判负 fixture → 应判负",
     [PY, "skill/scripts/surge/audit_region_filters.py",
      "skill/tests/surge/fixtures/bad_region_filter.conf"], 1, INJECTED),
    ("Egern 现役配置 → 应放行",
     [PY, "skill/scripts/egern/audit_region_filters.py", "egern/profiles/routing.yaml"], 0, None),
    ("Egern 判负 fixture → 应判负",
     [PY, "skill/scripts/egern/audit_region_filters.py",
      "skill/tests/egern/fixtures/bad_region_filter.yaml"], 1, "Hong Kong"),
    # ── clash（mihomo）侧 —— 2026-10-07 补入，此前该内核的地区组完全无人管 ──────
    ("clash 现役配置 → 应放行",
     [PY, "skill/scripts/clash/audit_region_filters.py", "clash/profiles/routing.yaml"], 0, None),
    ("clash 判负 fixture → 应判负",
     [PY, "skill/scripts/clash/audit_region_filters.py",
      "skill/tests/clash/fixtures/bad_region_filter.yaml"], 1, "Taiwan"),
]


def run(argv):
    env = dict(os.environ)
    env.setdefault("PYTHONIOENCODING", "utf-8")
    r = subprocess.run(argv, cwd=ROOT, capture_output=True, text=True,
                       encoding="utf-8", errors="replace", env=env, timeout=120)
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def main():
    root = sys.argv[1] if len(sys.argv) > 1 else ROOT
    root = os.path.abspath(root)

    # 前置：六份输入文件都在。缺文件 ⇒ 环境不达标（2），不是判负。
    needed = [
        "surge/profiles/routing.conf",
        "egern/profiles/routing.yaml",
        "skill/tests/surge/fixtures/bad_region_filter.conf",
        "skill/tests/egern/fixtures/bad_region_filter.yaml",
        "clash/profiles/routing.yaml",
        "skill/tests/clash/fixtures/bad_region_filter.yaml",
    ]
    missing = [p for p in needed if not os.path.isfile(os.path.join(root, p))]
    if missing:
        sys.stderr.write("❌ 缺输入文件（环境不达标，不是判负）：%s\n" % "、".join(missing))
        return 2

    print("地区组审计器 · 判别力回归（判负 fixture + 现役正向对照）")
    print("─" * 68)

    fails = 0
    for name, argv, want, marker in CASES:
        code, out = run(argv)
        if code == 2:
            print(f"   🔧 {name}：审计器报**环境/解析失败**（退出码 2）——"
                  f"闸门自身不成立，先修环境")
            fails += 1
            continue
        ok = (code == want)
        detail = f"退出码 {code}（期望 {want}）"
        # 判负用例再加一条：输出里必须出现定位标记 —— 证明"真报出了这一条"，
        # 而不是"崩在别处也返回 1"。
        if marker:
            saw = marker in out
            ok = ok and saw
            detail += f" · 输出{'含' if saw else '**不含**'}定位标记 `{marker}`"
        print(f"   {'✅' if ok else '❌'} {name}：{detail}")
        if not ok:
            fails += 1
            tail = "\n".join(out.splitlines()[-8:])
            if tail:
                print("      ── 尾部输出 ──")
                for ln in tail.splitlines():
                    print("      " + ln)

    print("─" * 68)
    if fails:
        print(f"result: {len(CASES) - fails} passed, {fails} failed"
              f" —— 审计器的**判别力**不成立：判负 fixture 没被拦住 = 现役的 ✅ 不可信")
    else:
        print(f"result: {len(CASES)} passed, 0 failed"
              f" —— 审计器既放行现役配置、又拦住漏同步的 fixture，判别力成立")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
