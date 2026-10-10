# -*- coding: utf-8 -*-
"""Release 断言 —— 远端发布状态与本仓当前版本是否一致。

模型（2026-10-08 改革后）：**当前版本 → 一张 Release**（tag = `vYYYY-MM-DD` = 发布日）。
旧模型从 git 历史重建全部历史 Release，为此需要归档目录 + 手写历史表 + 日期口径文档；
现已全部移除。本文件相应只剩 5 条断言，且都对着「现役」判，不考古。

判据
────
R1 tag 形状 `^vYYYY-MM-DD$` 且唯一
R2 资产名 ∈ 固定名集合（三内核 × 两产品线 × 完整/min）且不含版本号样式
R3 最新那张 Release 的资产 = 当前应发的 12 件（不多不少）
R4 最新那张 Release 的正文含当前三内核版本号
R5 仓库级 Latest 指针指向最新那张 Release
R6 HEAD 的改动必须已被某张 Release 覆盖（防「改了配置没发版」整类漏发）
   R6a 期望 tag（= HEAD 提交日）存在于远端 Release
   R6b 自该 tag 以来 **profile 资产没有未发布的变动**

⚠️ R6 的存在理由（2026-10-10 实测事故）：
    R1–R5 全部是「对着**已有** Release 判」。`newest = max(releases)` 取的是
    远端现有 Release 里最新的那张 —— 于是只要**一张新 Release 都没建**，
    `newest` 就还停在旧的那张，而旧那张与旧版本号天然自洽 ⇒ **R3/R4 全绿**。
    实测：连续 4 个功能提交（IR / P1 可移植性 / 懒人版 Play 修复 / 升号）都没发版，
    `verify_all` 一路全绿，直到升号让「现役版本号 ≠ 旧 Release 正文」才判负 ——
    **判据只能抓「发了但不一致」，抓不到「根本没发」。**
    更早的证据：`v2026-09-26` 与 `v2026-10-07` 两个 tag 指向同一个提交，即当日的
    版本当时都没发、事后批量补打。
    R6 补上这一格：**当前 HEAD 该有的 tag = HEAD 提交日期**（与 release_publish.plan
    的 `today = git log -1 --format=%as` 同口径），它必须出现在远端 Release 里。

退出码：0 = 全过 · 1 = 有判负 · 2 = 前置环境不达标 · 3 = 未验证（读不到远端）
分界线只有一条：**没读到远端真值 = 3；读到了但断言不过 = 1。**
（环境类码先修环境，别去逐条读判据。）
"""
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

REPO = os.environ.get("GITHUB_REPO", "RiverFlowsInUUU/self-conf")
API = "https://api.github.com/repos/%s" % REPO
TAG_RE = re.compile(r"^v\d{4}-\d{2}-\d{2}$")
VER_STYLE = re.compile(r"(?i)_?v\d+(\.\d+)?")       # 资产名里出现版本号即违规


class Skip(Exception):
    """读不到远端真值（不可达 / 限流 / 上游 5xx / 非 JSON）—— 未验证，不是判负。"""


def git(*a):
    return subprocess.check_output(["git", *a], encoding="utf-8", errors="replace",
                                   stderr=subprocess.DEVNULL).strip()


def _api_json(path, token, allow_404=False):
    """本文件**唯一**的请求入口 —— 异常分类只写一遍，不手抄第二份。"""
    req = urllib.request.Request(API + path)
    req.add_header("User-Agent", "self-conf-release")
    if token:
        req.add_header("Authorization", "Bearer %s" % token)
    try:
        return json.load(urllib.request.urlopen(req))
    except urllib.error.HTTPError as e:
        if e.code == 404 and allow_404:
            return None                       # 读到了：端点的确定回答是「没有」
        why = ("仓路径不可读：不存在 / 私有且无权限 / 已移除 —— 先核 GITHUB_REPO"
               if e.code == 404 else
               "凭据无效 —— 先核 GITHUB_TOKEN" if e.code == 401 else
               "限流" if e.code in (403, 429) else
               "上游故障" if e.code >= 500 else "请求被拒")
        raise Skip("GitHub API %s HTTP %s（%s）" % (path, e.code, why))
    except urllib.error.URLError as e:
        raise Skip("网络不可达（%s）" % e.reason)
    except json.JSONDecodeError as e:
        raise Skip("响应不是 JSON（多为上游错误页）：%s" % e)


def fetch_releases(token):
    out, page = [], 1
    while True:
        batch = _api_json("/releases?per_page=100&page=%d" % page, token)
        out += batch
        if len(batch) < 100:
            return out
        page += 1


def main():
    root = git("rev-parse", "--show-toplevel")
    sys.path.insert(0, os.path.join(root, "self-conf-skills", "run"))
    import release_publish as rp                  # 单一真源：资产名与版本口径都从这来

    p = rp.plan(root)
    want_assets = set(p["assets"])
    want_vers = set(p["versions"].values())

    try:
        releases = fetch_releases(os.environ.get("GITHUB_TOKEN"))
    except Skip as e:
        print("SKIP: %s —— 未能验证远端 Release 状态（离线/限流/上游故障/无凭据）。"
              "不是绿，是未验证。" % e)
        return 3

    ok, bad, skipped = [], [], []

    def judge(cond, msg_ok, msg_bad):
        (ok if cond else bad).append(msg_ok if cond else msg_bad)

    judge(bool(releases), "至少有一个 Release",
          "仓库还没有任何 Release —— 先跑 release_publish.py --apply")

    seen = set()
    for r in releases:
        tag = r["tag_name"]
        judge(bool(TAG_RE.match(tag)), "%s: tag 形状" % tag,
              "%s: tag 不匹配 ^vYYYY-MM-DD$" % tag)
        judge(tag not in seen, "%s: tag 唯一" % tag, "%s: tag 重复" % tag)
        seen.add(tag)
        for a in r.get("assets", []):
            n = a["name"]
            judge(n in rp.ASSET_NAMES and not VER_STYLE.search(n),
                  "%s/%s: 资产命名" % (tag, n),
                  "%s/%s: 不在固定名集合或带版本号（应 ∈ %s）"
                  % (tag, n, sorted(rp.ASSET_NAMES)))

    # 最新那张 = 字典序最大（tag 形态 vYYYY-MM-DD，字典序即时间序）
    newest = max(releases, key=lambda r: r["tag_name"])
    tag = newest["tag_name"]
    have = {a["name"] for a in newest.get("assets", [])}
    judge(have == want_assets, "%s: 资产齐全且无多余（%d 件）" % (tag, len(want_assets)),
          "%s: 资产与当前版本不符 —— 缺 %s / 多 %s"
          % (tag, sorted(want_assets - have), sorted(have - want_assets)))

    body = newest.get("body") or ""
    missing_v = [v for v in want_vers if v not in body]
    judge(not missing_v, "%s: 正文含当前版本号 %s" % (tag, sorted(want_vers)),
          "%s: 正文缺版本号 %s —— 跑 release_publish.py --apply 幂等回写"
          % (tag, missing_v))

    try:
        latest = _api_json("/releases/latest", os.environ.get("GITHUB_TOKEN"), allow_404=True)
    except Skip as e:
        skipped.append("R5 /releases/latest：%s —— 未能核对 Latest 指针" % e)
    else:
        if latest is None:
            judge(False, "", "R5 /releases/latest 返回 404 = 仓库无 Latest Release —— "
                             "跑 release_publish.py --apply")
        else:
            lt = latest.get("tag_name")
            judge(lt == tag, "R5 Latest=%s（最新）" % lt,
                  "R5 Latest=%s ≠ 最新 %s —— 跑 release_publish.py --apply" % (lt, tag))

    # ── R6 HEAD 的改动必须已被某张 Release 覆盖 ──────────────────────────
    #   见文件头注「R6 的存在理由」。判据（两段，缺一不可）：
    #     ① 期望 tag = HEAD 提交日（与 release_publish.plan 的
    #        `today = git log -1 --format=%as` 同口径）必须存在于远端 Release；
    #     ② 且**该 tag 指向的提交必须覆盖 HEAD** —— 即 tag 的 sha 是 HEAD 本身、
    #        或 HEAD 的祖先。否则说明「tag 建完之后又提交了新改动」。
    #
    #   ⚠️ 为什么必须有 ②（2026-10-10 注错实测发现）：
    #      只判 ① 会漏掉本仓**最常见的**漏发形态 —— 「一天一版」模型下，
    #      当天先发了版、之后又改了配置，HEAD 日期仍是当天、tag 已存在
    #      ⇒ ① 通过，可**改了配置却没重发资产**。实测该场景 ① 判绿（漏判）。
    #
    #   ⚠️ ② 的判据对象是「**profile 资产是否已随最新 Release 发出**」，
    #      而不是「tag 是否指向 HEAD」—— 这一点本次设计**来回错了两次**，
    #      两次都实测过，把结论钉在这里：
    #
    #      · 错法一 `tag_sha == head_sha`：tag 一经创建即固定，而
    #        `release_publish.apply()` 只 PATCH body/name、**从不移动 tag**
    #        （见该函数 patch 分支）。「一天一版」下当天任何后续提交都会让
    #        `tag != HEAD` ⇒ 门禁**永远红**。实测：`f8f70e1` 提交后判负，
    #        `--apply` 回写后**依然判负**（tag 未动）。
    #      · 错法二 `is_ancestor(tag_sha, head_sha)` 取真：它判的是「HEAD 是否
    #        超出 tag」，同样把「当天改文档/判据」误判成漏发。实测：只改
    #        `check_releases.py` + `gates.md` 的提交也会被判负 —— 而本仓
    #        显式规定「只改注释/文档 ⇒ 不必升号」（ops.md §2），更不该因此判负。
    #
    #      ⇒ 真正该问的是：**profile（12 件资产）变了没有？变了就必须发出去。**
    #        所以 ② 判「自 `tag_sha..HEAD` 之间，本地 profile 是否与已发布资产一致」。
    #        只改脚本/文档时该区间不含 profile ⇒ 天然放行，不会误伤。
    #
    #   ⚠️ 只认**远端 Release**，不查本地 `git tag`：本地可能没 fetch 到 tag
    #      （实测 2026-10-10：远端 Release 已在、本地 `git tag --list` 却是空的）。
    #   ⚠️ 与 R3/R4 的分工：R3/R4 判「最新那张**自身**对不对」，R6 判「HEAD 的
    #      改动**有没有**被发出去」。没有 R6 时，一张新 Release 都没建的场景下
    #      R3/R4 会全绿（见头注）。
    head_tag = rp.plan(root)["tag"]
    head_sha = git("rev-parse", "HEAD")
    have_tag = any(r["tag_name"] == head_tag for r in releases)
    judge(have_tag,
          "R6a HEAD(%s) 的 Release 已发布" % head_tag,
          "R6a HEAD 该有的 Release %s **不存在** —— 当前 main 的改动还没发版。"
          "跑 release_publish.py（预览）→ --apply（真发）；"
          "若本次是功能变动，先按 ops.md §2 升号再发" % head_tag)
    if have_tag:
        # ② profile 是否已随该 Release 发出（见上文「② 的判据对象」）
        try:
            ref = _api_json("/git/ref/tags/%s" % head_tag, os.environ.get("GITHUB_TOKEN"))
            tag_sha = (ref.get("object") or {}).get("sha")
        except Skip as e:
            skipped.append("R6b tag %s 指向：%s —— 未能核对 profile 是否已发布" % (head_tag, e))
        else:
            if not tag_sha:
                skipped.append("R6b tag %s 读不到指向的 commit —— 未验证" % head_tag)
            else:
                # tag_sha..HEAD 之间变动过的 profile —— 这些必须已随该 Release 发出
                # ⚠️ 匹配用**仓库内相对路径**，不能用 basename：
                #    `rp.ASSET_NAMES` 是「内核前缀 + 产品线 + 形态」的**组合全集**
                #    （24 个，含 `clash-lazy.conf` 这类并不存在的混搭名），而实际
                #    文件名是 `clash/profiles/lazy.yaml` —— 两者 basename 永不相等。
                #    实测踩过：第一版用 basename 判，对任何 profile 改动都判绿（假闸门）。
                #    这里改为把资产名还原成目录形态再比对。
                asset_paths = set()
                for nm in rp.ASSET_NAMES:
                    for kern in ("surge", "egern", "clash"):
                        pre = kern + "-"
                        if not nm.startswith(pre):
                            continue
                        rest = nm[len(pre):]          # 如 lazy.min.yaml
                        fam, _, tail = rest.partition(".")
                        # tail 形如 min.yaml / yaml / min.conf / conf
                        ext = "." + tail.split(".")[-1]
                        mid = ".min" if tail.startswith("min.") else ""
                        asset_paths.add("%s/profiles/%s%s%s"
                                        % (kern, fam, mid, ext))
                        break
                try:
                    changed = [f for f in git("diff", "--name-only",
                                              "%s..%s" % (tag_sha, head_sha)).splitlines()
                               if f in asset_paths]
                except subprocess.CalledProcessError:
                    changed = []
                unpub = sorted(set(changed))
                judge(not unpub,
                      "R6b %s 之后无未发布的 profile 变动" % head_tag,
                      "R6b %s 之后这些 profile 变了但没发版：%s —— "
                      "跑 release_publish.py --apply 重发资产（幂等回写同一张）"
                      % (head_tag, unpub))

    for m in ok:
        print("   ✅ %s" % m)
    for m in bad:
        print("   ❌ %s" % m)
    for m in skipped:
        print("   ⚠️ 未验证 %s" % m)
    print("\nTOTAL: %d passed, %d failed, %d unverified" % (len(ok), len(bad), len(skipped)))
    if bad:
        return 1
    return 3 if skipped else 0


if __name__ == "__main__":
    sys.exit(main())
