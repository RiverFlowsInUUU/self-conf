#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CHANGELOG 漂移检查 —— 「改了东西没往 CHANGELOG 里记」的自动拦截。

背景（本仓第 3 次复发）：
  · 第十一轮：5 条修完全没进 CHANGELOG
  · 第十二轮：补了**第十一轮**的那五条，**本轮自己的五条一条没记**
  · 根因不是"忘了写"，而是**自检口径错位**：当时那条自检只验
    「CHANGELOG 里存在某个今天日期的条目」——而那条是上一轮留下的，
    于是"存在"永远为真，"内容对不对"从没被验过。

本判据验的是**内容**：取「已改动但还没写进 CHANGELOG 的文件」作为素材，
要求 CHANGELOG 最新一个 `## YYYY-MM-DD` 条目至少点名其中一个（或命中主题词）。
**一个都没提 ⇒ 判负。** 不做逐字比对，避免误报 —— 只在"整轮隐形"时红。

素材来源优先级：
  1. 工作区未提交改动（`git diff --name-only HEAD`）—— 最贴近真实场景
  2. 若无未提交改动，退回最近 N 条 commit（`--commits`，默认 3）

退出码：0 通过 / 1 判负 / 2 环境不具备 / 3 未验证（无 .git）
"""
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, '..', '..'))
CLOG = os.path.join(ROOT, 'skill', 'reference', 'shared', 'CHANGELOG.md')

# 这些是"记账载体本身"，不需要被 CHANGELOG 点名
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
    """返回 (changed_files, subjects) —— 素材与其来源描述。"""
    rc, out = _git('diff', '--name-only', 'HEAD')
    if rc == 0 and out.strip():
        files = set()
        for line in out.splitlines():
            line = line.strip()
            if line and (line.endswith(_SRC_EXT) or '/' in line):
                files.add(os.path.basename(line))
        # 未提交模式下改动可能已 staged：`git diff HEAD` 已含 staged+unstaged
        return files, ['（工作区未提交改动）']

    rc, out = _git('log', '-%d' % n_commits, '--name-only',
                   '--pretty=format:__C__%s')
    if rc != 0:
        return None, []
    files, subjects, skip = set(), [], False
    for line in out.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith('__C__'):
            subjects.append(line[5:])
            continue
        if _CJK_ONLY.match(line):          # 纯中文（commit 正文片段），不是路径
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
    if not os.path.isfile(CLOG):
        print('❌ 找不到 CHANGELOG.md：%s' % CLOG)
        return 2

    changed, subjects = _pick_sources(n_commits)
    if changed is None:
        print('⚠️ git 查询失败 —— CHANGELOG 漂移**未验证**')
        return 3

    changed = {c for c in changed if c and c not in EXEMPT}
    if not changed:
        print('✅ 没有需要记录的改动素材')
        return 0

    text = open(CLOG, encoding='utf-8').read()
    hits = list(re.finditer(r'(?m)^## (\d{4}-\d{2}-\d{2})', text))
    if not hits:
        print('❌ CHANGELOG 里找不到任何 `## YYYY-MM-DD` 条目')
        return 1
    # ⚠️ 同一天可能有多段（今天就有 3 段：第十轮 / 第十一轮 / 第十二+十三轮）。
    #    只取"第一个同日段"会把后面的记录漏判 ⇒ 合并**该日期的所有段**。
    first_date = hits[0].group(1)
    seg_parts = []
    for idx, h in enumerate(hits):
        if h.group(1) != first_date:
            continue
        i0 = h.start()
        i1 = hits[idx + 1].start() if idx + 1 < len(hits) else len(text)
        seg_parts.append(text[i0:i1])
    date = first_date
    seg = '\n'.join(seg_parts)

    mentioned = sorted(c for c in changed if c in seg)
    if mentioned:
        print('✅ CHANGELOG 最新条目（%s）点名了本轮改动：%s'
              % (date, '、'.join(mentioned)))
        return 0

    # 宽松一层：看看有没有命中本轮主题词
    core = []
    for s in subjects:
        for tok in re.findall(r'[\u4e00-\u9fff]{2,8}', s):
            if tok in ('审查', '修复', '一轮', '二轮', '三轮') or tok.endswith('漂移'):
                continue
            core.append(tok)
    if any(t in seg for t in core):
        print('✅ CHANGELOG 最新条目（%s）命中本轮主题词' % date)
        return 0

    print('❌ CHANGELOG 最新条目（%s）既没点名本轮改动的任何文件，'
          '也没出现本轮主题词 —— 这轮修正在历史里是隐形的' % date)
    print('   本轮改了这些文件（应至少点名其一）：')
    for c in sorted(changed):
        print('     - %s' % c)
    for s in subjects:
        print('   来源：%s' % s)
    return 1


if __name__ == '__main__':
    # ⚠️ 本仓专门有一道「Encoding gate (cp936)」门：中文 Windows 下 stdout 是 gbk，
    #    print 非 GBK 字符（✅❌⚠️）会 UnicodeEncodeError 并以退出码 1 结束，
    #    而 1 恰是判负码 ⇒ 打印崩溃会被读成「判负」，判据根本没跑却看着像失败。
    #    每个独立脚本都得自己护住，不能指望总入口。
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass
    sys.exit(main(sys.argv[1:]))
