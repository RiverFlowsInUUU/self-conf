#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CHANGELOG 漂移检查 —— 「改了东西没往 CHANGELOG 里记」的自动拦截。

背景（本仓第 3 次复发）：
  · 第十三轮：本轮五条一条没记（补的段落写的是**第十二轮**的内容）
  · 根因不是"忘了写"，而是**自检口径错位**：当时只验「存在今日条目」
    —— 而那条是上一轮留下的 ⇒ "存在"永远为真，"内容对不对"从没被验。
  ==> 本判据验的是**内容**，它已接进 verify_all（47 道之一）。

## 判据

取「已改动但还没写进 CHANGELOG 的文件」作为素材，要求 CHANGELOG 最新一个
`## YYYY-MM-DD` 条目至少点名其中一个（或命中本轮 commit 主题词）。
**一个都没提 ⇒ 判负。** 不做逐字比对（误报太多），只在"整轮隐形"时红。

素材来源优先级：
  1. 工作区未提交改动（`git diff --name-only HEAD`）—— 最贴近真实场景
  2. 若无，则回退最近 N 条 commit（`--commits N`，默认 3）

⚠️ **已知边界（第十四轮审查问题 3，未修，记录在案）**：
  · 命中判定是"basename 在当天段落正文出现"，若把文件名写进**同一天另一小段**
    或 HTML 注释里，仍会被算作"已记录" ⇒ 在 CI 里可能偏绿。
  · 只有 untracked 改动（未 `git add`）时会回落到 commit 模式 ⇒ 新建未 add 的脚本能溜过。
  · 没有豁免/跳过路径（只有 `--commits N`）。
  ⇒ 这三条是**已知的宽**，不是"已收严"。修它需要区分"真实提及"与"注释里提到"，
     本轮时间不够，先记账，不假装已解决。

退出码：0 通过 / 1 判负 / 2 环境不具备 / 3 未验证（无 .git）
"""
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, '..', '..'))

# ⚠️ 第十四轮审查问题 6：clash 侧还有**第二份** CHANGELOG（沿革用）。
#    只查 shared 那份 ⇒ clash 范围的改动与任何 CHANGELOG 都解耦 ⇒ 照样能隐形。
CLOGS = [
    os.path.join(ROOT, 'skill', 'reference', 'shared', 'CHANGELOG.md'),
    os.path.join(ROOT, 'skill', 'reference', 'clash', 'CHANGELOG.md'),
]

# 记账载体本身，不需要被 CHANGELOG 点名
EXEMPT = {'CHANGELOG.md'}

_SRC_EXT = ('.py', '.md', '.yml', '.yaml')
_CJK_ONLY = re.compile(r'^[\u4e00-\u9fff（）\s，。、：—－]+$')


def _git(*args):
    env = dict(os.environ)
    env['PYTHONIOENCODING'] = 'utf-8'
    env['LC_ALL'] = 'C.UTF-8'
    try:
        r = subprocess.run(['git'] + list(args), cwd=ROOT,
                           capture_output=True, timeout=30, env=env)
    except Exception:
        return -1, ''
    blob = r.stdout or b''
    try:
        return r.returncode, blob.decode('utf-8')
    except UnicodeDecodeError:
        return r.returncode, blob.decode('utf-8', 'replace')


def _pick_sources(n_commits):
    """返回 (changed_files, subjects)。"""
    rc, out = _git('diff', '--name-only', 'HEAD')
    if rc == 0 and out.strip():
        files = set()
        for line in out.splitlines():
            line = line.strip()
            if line and (line.endswith(_SRC_EXT) or '/' in line):
                files.add(os.path.basename(line))
        return files, ['（工作区未提交改动）']

    rc, out = _git('log', '-%d' % n_commits, '--name-only',
                   '--pretty=format:__C__%s')
    if rc != 0:
        return None, []
    files, subjects = set(), []
    for line in out.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith('__C__'):
            subjects.append(line[5:])
            continue
        if _CJK_ONLY.match(line):
            continue
        if line.endswith(_SRC_EXT) or '/' in line:
            files.add(os.path.basename(line))
    return files, subjects


def main(argv):
    n_commits = 3
    if '--commits' in argv:
        try:
            n_commits = int(argv[argv.index('--commits') + 1])
        except Exception:
            pass

    if not os.path.isdir(os.path.join(ROOT, '.git')):
        print('⚠️ 不是 git 工作副本 —— CHANGELOG 漂移**未验证**')
        return 3

    clogs = [c for c in CLOGS if os.path.isfile(c)]
    if not clogs:
        print('❌ 找不到任何 CHANGELOG.md')
        return 2

    changed, subjects = _pick_sources(n_commits)
    if changed is None:
        print('⚠️ git 查询失败 —— CHANGELOG 漂移**未验证**')
        return 3

    changed = {c for c in changed if c and c not in EXEMPT}
    if not changed:
        print('✅ 没有需要记录的改动素材')
        return 0

    text = '\n'.join(open(c, encoding='utf-8').read() for c in clogs)
    hits = list(re.finditer(r'(?m)^## (\d{4}-\d{2}-\d{2})', text))
    if not hits:
        print('❌ CHANGELOG 里找不到任何 `## YYYY-MM-DD` 条目')
        return 1
    # 同一天可能有多段（今天就有 3 段）⇒ 合并**该日期的所有段**
    first_date = hits[0].group(1)
    parts = []
    for idx, h in enumerate(hits):
        if h.group(1) != first_date:
            continue
        i0 = h.start()
        i1 = hits[idx + 1].start() if idx + 1 < len(hits) else len(text)
        parts.append(text[i0:i1])
    seg = '\n'.join(parts)
    date = first_date

    mentioned = sorted(c for c in changed if c in seg)
    if mentioned:
        print('✅ CHANGELOG 最新条目（%s）点名了本轮改动：%s'
              % (date, '、'.join(mentioned)))
        return 0

    core = []
    for s in subjects:
        for tok in re.findall(r'[\u4e00-\u9fff]{2,8}', s):
            if tok in ('审查', '修复', '补记') or tok.endswith('漂移'):
                continue
            core.append(tok)
    if any(t in seg for t in core):
        print('✅ CHANGELOG 最新条目（%s）命中本轮主题词' % date)
        return 0

    print('❌ CHANGELOG 最新条目（%s）既没点名本轮改动的任何文件，'
          '也没出现本轮主题词 —— 这轮修正在历史里是隐形的' % date)
    for c in sorted(changed):
        print('     - %s' % c)
    for s in subjects:
        print('   来源：%s' % s)
    return 1


if __name__ == '__main__':
    # ⚠️ 本仓有「Encoding gate (cp936)」门：中文 Windows 下 stdout 是 gbk，
    #    print ❌ 会 UnicodeEncodeError 并以 exit 1 结束，而 1 恰是判负码
    #    ⇒ 打印崩溃会被误读成"判负"。每个独立脚本都得自己护住。
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass
    sys.exit(main(sys.argv[1:]))
