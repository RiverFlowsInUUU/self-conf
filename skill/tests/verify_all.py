#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""一键收尾闸门 —— 动线⑤ 的闸门命令合并成 1 条，并行跑、出汇总表。

为什么存在：
    SKILL.md 动线⑤原来列一堆独立命令，AI 逐条调用 = 多次工具调用、多段输出
    折进上下文，且任何一次漏跑/跑错参数都算事故。本脚本与 `.github/workflows/ci.yml`
    的步骤**同源**（改 CI 步骤时必须同步这里，反之亦然），并行执行后只输出一张
    「闸门 | 结果 | 耗时」汇总表，红的才展开输出尾部 —— 正常情况一段话看完全部结论。

用法：
    python skill/tests/verify_all.py            # 全量并行，全绿退出码 0
    python skill/tests/verify_all.py -v         # 无论红绿都打印每个闸门的输出尾部
    python skill/tests/verify_all.py --index    # 只读列出闸门清单（不跑、不判负），供引用时现抓

设计约定：
    · 与 CI 同源是铁律 —— 本地绿但 CI 红属于竞态/环境差，不允许有"第三套判据"。
      ⚠️ **已知挂账**：闸门清单靠人工双写（ci.yml ↔ 本文件），机器对账未做（对账脚本
      自身也是维护面）。**推翻挂账的触发条件**：一旦出现「一侧增删闸门、另一侧未同步」
      且事后确认是人工漏同步造成的本地/CI 结论分歧，就必须补上清单对账断言。
    · 退出码语义（全仓统一，见 reference/shared/troubleshoot-faq.md §8.2）：
      0 = 判据全过 ｜ 1 = 有判负 ｜ 2 = 前置环境不达标（**计入失败，先修环境再看判据**）
      ｜ 3 = SKIP（未能验证 → 不计入失败但必须明示）。
      3 的准入 = 「没读到远端真值」。**任何脚本不得因故障/未知错误返回 3**（故障走 2、
      断言不过走 1）——本脚本对 3 是全闸门通用判定，滥用 3 会被静默吞成假绿。
      SKIP 独立占用 3：2 已被全仓铁律占用为「环境不达标」，复用会让环境故障被吞成
      SKIP → 假绿（0930 二轮外部审查）。
    · check_releases 需 GITHUB_TOKEN：缺省时自动回退 `gh auth token`。都没有、或 API
      离线/限流/上游 5xx/非 JSON 时返回 3，本脚本以 ⚠️ 明示「未验证」并不计入失败
      （0929 一轮审查：原实现按输出文本嗅探、且被跳过仍 exit 1，提示与实际矛盾，
      现按退出码判定）。
      ⚠️ 本地与 CI 对 3 的口径**有意不同**：本地允许 SKIP（可能真离线 → exit 0 + ⚠️），
      CI 侧 3 视为失败（CI 带 token，读不到远端即 CI 环境异常）——这是**严格化**，不是
      "第三套判据"；CI 侧偶发 3（共享 runner IP 被 GitHub 限流）→ 重跑即可。
    · make_min 漂移检查 = `make_min.py --check`（0929 起）：--check 直接比对磁盘 .min 与
      生成器输出，有差异即非 0。旧写法「计划模式 + git diff」两半恒空/恒 0，是永远绿的
      空操作（2026-09-29 外部审查实锤后废除，原『git 无漂移』闸门随之合并）。
    · CI 另有一道**运行时编码闸门**（`.github/workflows/ci.yml` 的 `Encoding gate (cp936)`）：
      以 `PYTHONIOENCODING=cp936` 跑一遍本脚本，在 Linux 上等价复现 Windows(ACP=936) 的
      管道路径 —— 脚本 print 非 GBK 字符却无编码保护时当场崩、当场红。
      它与 `check_portability.py` 的 E4 **互补、不可互相替代**：
        - 本闸门测**运行时真相**、零假阳性，但只覆盖 `build_gates()` 跑到的脚本，
          且只覆盖**执行到的**分支（只在失败分支打印 emoji 的脚本仍测不到）；
        - E4 是静态近似，全覆盖（含 CI 不跑的审计脚本），但会漏报也会假阳性。
      两者叠加才封住「脚本忘加保护 → 崩成退出码 1 → 被读成判负」这条假语义路径。
      前提是 `run_one` 对 PYTHONIOENCODING 用 `setdefault`（显式继承，见该处注释）。
"""

import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PY = sys.executable or 'python'


def _token():
    """check_releases 用：环境变量 → gh auth token → None。"""
    if os.environ.get('GITHUB_TOKEN'):
        return os.environ['GITHUB_TOKEN']
    try:
        r = subprocess.run(['gh', 'auth', 'token'], capture_output=True, text=True, timeout=15)
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout.strip()
    except Exception:
        pass
    return None


def build_gates():
    """与 ci.yml 步骤一一对应；(名称, argv, 额外环境)。

    self-conf 适配：本仓由两仓**复制**整合而成，不继承原仓 git 历史与
    GitHub Release。故对依赖这两者的判据做**显式豁免**（不是静默跳过）：
      · min-pair 的 V7「一天一版」 —— 需完整 git 历史，复制仓不成立
      · releases 方案               —— 需本仓自己的 Release，整合仓没有
    豁免项在输出里会点名，不冒充通过。
    另：追加 mihomo（clash/）专属门禁，使总入口真正覆盖三内核。
    """
    import os as _os
    _skip_v7 = {'SKIP_V7': '1'}
    gates = [
        ('secrets 扫描', [PY, 'skill/tests/check_secrets.py'], {}),
        ('portability', [PY, 'skill/tests/check_portability.py'], {}),
        ('min-pair 一致', [PY, 'skill/tests/check_min_pair.py'], _skip_v7),
        ('README 徽章', [PY, 'skill/tests/check_badges.py'], {}),
        ('markdown 链接', [PY, 'skill/tests/check_links.py', '.'], {}),
        # ⚠️ self-conf 豁免：检查的是「原仓自己的 Release 发布纪律」，
        #    整合仓没有对应的 Release，查也无意义。
        # ('releases 方案', [PY, 'skill/tests/check_releases.py'],
        #  {'GITHUB_TOKEN': _token() or ''}),
        ('Surge DNS lazy', [PY, 'skill/scripts/surge/check_surge_dns.py', 'surge/profiles/lazy.conf'], {}),
        ('Surge DNS routing', [PY, 'skill/scripts/surge/check_surge_dns.py', 'surge/profiles/routing.conf'], {}),
        ('Egern DNS 双份', [PY, 'skill/scripts/egern/check_egern_dns.py',
                            'egern/profiles/lazy.yaml', 'egern/profiles/routing.yaml'], {}),
        ('.min 漂移', [PY, 'skill/tests/make_min.py', '--check'], {}),
        ('地区组判别力', [PY, 'skill/tests/check_region_filters.py'], {}),
        ('profile 结构', [PY, 'skill/tests/check_structure.py'], {}),
        ('文档 AUTO 同步', [PY, 'skill/tests/sync_docs.py', '--check'], {}),
        # ── mihomo（clash/）专属门禁：整合后纳入总入口，三内核一视同仁 ──
        ('clash 结构', [PY, 'skill/tests/clash/check_structure.py'], {}),
        ('clash min 版一致', [PY, 'skill/tests/clash/check_min_pair.py'], {}),
        ('clash 脚本/静态对拍', [PY, 'skill/tests/clash/check_script_sync.py'], {}),
        ('clash 规则集生成物', [PY, 'skill/scripts/clash/build_rules.py', '--check'], {}),
    ]
    return gates


def run_one(name, argv, extra_env):
    t0 = time.perf_counter()
    env = dict(os.environ)
    env.update({k: v for k, v in extra_env.items() if v})
    if 'GITHUB_TOKEN' in extra_env and not extra_env['GITHUB_TOKEN']:
        env.pop('GITHUB_TOKEN', None)
    # 运行时编码兜底：子进程默认以 UTF-8 输出，兜住 E4 静态判不到的情形（函数返回值 /
    # 运行时数据 / 多层 wrapper 等盲区）。已自带 reconfigure 或 import 编码垫片的脚本会覆盖
    # 本变量，行为不变。
    # ⚠️ 与 E4 **互补而非替代**：E4 是静态门禁、只读源码，不受这里影响 —— 因此注入不会
    #    掩盖 E4 能抓的问题。（早前「注入会掩盖」的判断已由 2026-10-02 实测推翻。）
    # ⚠️ 必须 setdefault，**不可**写成硬赋值 `env[...] = 'utf-8'`：CI 的「Encoding gate (cp936)」
    #    正是靠 `PYTHONIOENCODING=cp936` 从父进程传下来、再经这里**原样继承**给子进程，
    #    才能复现 Windows(ACP=936) 的管道路径。硬赋值会把继承来的 cp936 抹成 utf-8 ⇒
    #    那道闸门永远绿（空操作）。2026-10-02 实测：父进程设 cp936 时子进程仍报
    #    `CHILD-ENC: utf-8`、emoji 照常输出 —— 闸门形同虚设。
    #    「显式指定优先、缺省才兜底」也是这条兜底本该有的语义。
    env.setdefault('PYTHONIOENCODING', 'utf-8')
    try:
        r = subprocess.run(argv, cwd=ROOT, capture_output=True, text=True,
                           encoding='utf-8', errors='replace', env=env, timeout=600)
        return {'name': name, 'argv': argv, 'code': r.returncode,
                'dt': time.perf_counter() - t0,
                'out': (r.stdout or '') + (r.stderr or '')}
    except Exception as e:                                   # noqa: BLE001
        return {'name': name, 'argv': argv, 'code': -1,
                'dt': time.perf_counter() - t0, 'out': f'{type(e).__name__}: {e}'}


def print_index():
    """--index：只读列出闸门清单（现抓 build_gates()），**不判负、不跑闸门、退出码 0**。

    存在理由：闸门清单在 `ci.yml` 与 `docs` 里各有一份**手写副本**（已挂账），手抄必然漂移。
    要引用清单时**用本命令现抓**，别把它复制成第三份死表 —— 尤其**不要回填进 CI**（那等于把
    漂移面原样请回来）。输出仅供**人读 + 文档引用**。
    """
    gates = build_gates()
    print(f'闸门清单：{len(gates)} 道（现抓自 build_gates()，勿手抄成死表）\n')
    for i, (name, argv, env) in enumerate(gates, 1):
        need = '  [需 GITHUB_TOKEN]' if 'GITHUB_TOKEN' in env else ''
        print(f'{i:>2}. {name}{need}')
        print(f'      {" ".join(argv[1:])}')
    print(f'\nCI 侧为 10 个 step（Surge 双 profile 合并在同一 run 内）—— 末位那个'
          f'「Encoding gate (cp936)」以本脚本为入口复跑一遍，故**不进 build_gates()**'
          f'（进去即递归）；与上表按 step 聚合后形状不同，属已知挂账，见本文件头注。')
    sys.exit(0)


def main():
    if '--index' in sys.argv:
        print_index()
    verbose = '-v' in sys.argv
    gates = build_gates()
    print(f'并行跑 {len(gates)} 道闸门（与 ci.yml 同源）…\n')
    with ThreadPoolExecutor(max_workers=min(len(gates), 8)) as ex:
        results = list(ex.map(lambda g: run_one(*g), gates))

    width = max(len(r['name']) for r in results)
    print(f"{'闸门':<{width}}  结果  耗时")
    print('-' * (width + 16))
    for r in results:
        mark = {0: '✅', 3: '⚠️', 2: '🔧'}.get(r['code'], '❌')
        print(f"{r['name']:<{width}}  {mark}   {r['dt']:.1f}s")
    print()

    # 退出码语义（全仓统一，troubleshoot-faq.md §8.2）：
    #   0 = 判据全过；1 = 有判负；2 = 前置环境不达标（计入失败）；3 = SKIP（未验证）
    failed = [r for r in results if r['code'] not in (0, 3)]
    env_fail = [r for r in results if r['code'] == 2]
    skipped = [r for r in results if r['code'] == 3]
    if not failed and not verbose:
        print('全部通过 —— 详细输出用 -v 查看。' if not skipped
              else '闸门全过（有 SKIP 项，见下）。')
    if failed or skipped or verbose:
        for r in results:
            if verbose or r['code'] != 0:
                tail = '\n'.join(r['out'].splitlines()[-30:]) or '(无输出)'
                print(f"──── {r['name']} (exit {r['code']}) {'─' * 30}")
                print(tail)
                print()
    if env_fail:
        print('🔧 以下闸门前置环境不达标（退出码 2）—— 先修环境，别读判据：'
              + '、'.join(r['name'] for r in env_fail))
    if skipped:
        print('⚠️ 以下闸门被跳过（未验证 ≠ 绿）：'
              + '、'.join(r['name'] for r in skipped))

    sys.exit(1 if failed else 0)


if __name__ == '__main__':
    main()
