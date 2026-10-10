#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""豁免用量判据 —— profile 里声明的 `# audit-waive:` 必须**确实被用到**。

为什么要有这一项（2026-10-10 补）
─────────────────────────────────
豁免机制（`# audit-waive: <检查号> <理由>`）此前只能「加」，没有判据管「它还有效吗」：

· **漏声明的后果**：本来豁免的检查项突然报 HIGH ⇒ 整轮判负。这个方向**会叫**，没问题。
· **多声明 / 陈旧声明的后果**：某个检查项**已经不再触发**（配置改好了、判据改了），
  而豁免行还留着 ⇒ 它**静默地**削弱着判据 —— 将来该项真的出问题时，
  会被这条陈旧豁免降级成 `WAIVED:`，**不再判负**。这个方向**不会叫**。

⇒ 本判据补的就是「不会叫」的那个方向：**声明的豁免必须有对应的实际触发**。

判据
────
对每份带 `# audit-waive:` 的 profile：跑对应内核的 DNS 审计器，
要求「声明的检查号集合」⊆「实际被豁免的检查号集合」。
多出来的 = 陈旧豁免 ⇒ 判负，提示删掉或说明为何保留。

⚠️ 刻意**不判「实际 waived 数 == 声明数」的反方向**（即审计器豁免了没声明的项）——
   那由审计器自身的机制保证（豁免只从 profile 读），不需第二条判据。

退出码：0 = 全过 · 1 = 有陈旧豁免 · 2 = 前置不达标（脚本缺失/跑不起来）
"""
import os
import re
import subprocess
import sys

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

_d = os.path.dirname(os.path.abspath(__file__))
for _c in (os.path.join(_d, "..", "lib"), _d):
    _c = os.path.normpath(_c)
    if os.path.isfile(os.path.join(_c, "paths.py")):
        sys.path.insert(0, _c)
        break
from paths import repo_root  # noqa: E402

WAIVE_RE = re.compile(r"#\s*audit-waive:\s*(\d+)\s+(.*)")
# ⚠️ 解析的是**报告文本**里的豁免段落，不是源码里的 `WAIVED:` 数据结构 ——
#    `check_surge_dns.py` 的 `WAIVED:{level}` 只存在于内存中，打印出来是中文
#    「⚪ 已豁免 · N 条」段，条目形如 `     [ 1] 描述`（检查号带前导空格）。
#    第一版误按 `WAIVED:[A-Z]+:(\d+)` 解析 ⇒ 恒解析不到 ⇒ 把现役配置全判成
#    「陈旧豁免」（实测：明明报了 2 waived 却判负）。这是判据自身的错，不是配置的错。
WAIVED_ITEM = re.compile(r"^\s*\[\s*(\d+)\]\s+\S", re.M)

# (profile, 审计器) —— 只有带豁免的这两份需要判
TARGETS = [
    ("surge/profiles/routing.conf", "self-conf-skills/gates/surge/check_surge_dns.py"),
    ("surge/profiles/lazy.conf", "self-conf-skills/gates/surge/check_surge_dns.py"),
]


def waived_ids(report):
    """从报告文本里取出「已豁免」段落中的检查号集合。

    ⚠️ 必须先切出豁免段落再解析 —— 报告其它段落也有 `[N]` 条目（如 `[12] …`），
       直接全文匹配会把「正常通过的检查」也算成豁免，导致判据恒绿（假闸门）。
       段落边界：从「已豁免 · N 条」起，到下一个分隔线（`─{4,}`）止。
    """
    ids = set()
    lines = report.splitlines()
    inside = False
    for ln in lines:
        if "已豁免" in ln and "条" in ln:
            inside = True
            continue
        if inside:
            if re.match(r"^\s*─{4,}", ln) or ln.strip().startswith("result:"):
                inside = False
                continue
            m = WAIVED_ITEM.match(ln)
            if m:
                ids.add(int(m.group(1)))
    return ids


def main():
    # 可选位置参数 = 仓库根（判别力回归的沙箱副本靠它指向副本 ——
    # 否则 `repo_root()` 从本脚本位置上溯，永远定位到原仓，对副本注错不生效）
    root = sys.argv[1] if len(sys.argv) > 1 else repo_root()
    ok, bad, skip = [], [], []

    for rel, gate in TARGETS:
        prof = os.path.join(root, rel.replace("/", os.sep))
        # ⚠️ 审计器从**本脚本所在仓库**取，不从 `root` 取 —— `root` 可能是
        #    判别力回归的沙箱副本（只拷了被审文件、没拷工具）。审计器是「工具」，
        #    被审的数据（profile）才该来自 `root`。
        gp = os.path.join(_d, gate.split("self-conf-skills/gates/", 1)[-1]
                          .replace("/", os.sep))
        if not (os.path.isfile(prof) and os.path.isfile(gp)):
            skip.append("%s（profile 或审计器缺失：%s / %s）" % (rel, prof, gp))
            continue
        text = open(prof, encoding="utf-8", errors="replace").read()
        declared = {int(m.group(1)) for m in WAIVE_RE.finditer(text)}
        if not declared:
            continue                      # 没声明豁免，本判据不适用
        p = subprocess.run([sys.executable, gp, rel], cwd=root,
                           capture_output=True, text=True, encoding="utf-8")
        out = (p.stdout or "") + (p.stderr or "")
        used = waived_ids(out)
        stale = sorted(declared - used)
        if stale:
            bad.append("%s：检查号 %s 声明了豁免，但审计器**没有**相应豁免 "
                       "⇒ 陈旧豁免（它正在静默削弱判据）。删掉该 `# audit-waive:` 行，"
                       "或说明为何保留" % (rel, stale))
        else:
            ok.append("%s：声明的豁免 %s 全部命中实际触发" % (rel, sorted(declared)))

    for m in ok:
        print("  ✅ %s" % m)
    for m in bad:
        print("  ❌ %s" % m)
    for m in skip:
        print("  ⚠️ 未验证 %s" % m)
    print("\nTOTAL: %d passed, %d failed" % (len(ok), len(bad)))
    if bad:
        return 1
    return 3 if skip else 0


if __name__ == "__main__":
    sys.exit(main())
