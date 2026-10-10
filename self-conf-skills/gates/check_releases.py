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
   R6b 该 tag 那张 Release 的资产与**本地 profile 逐件一致**（改了没重发即判负）

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
import hashlib
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


def asset_relpath(name):
    """资产固定名 → 仓库内相对路径。`surge-lazy.min.conf` → `surge/profiles/lazy.min.conf`。

    ⚠️ 必须做这层还原：资产名是「内核前缀 + 产品线 + 形态」，而实际文件在
        `<kern>/profiles/<fam><.min><ext>` —— 两者 basename 永不相等。
        （历史教训见 gates.md §10.2.1：第一版用 basename 判，对任何 profile
        改动都判绿，是个假闸门。）
    """
    for kern in ("surge", "egern", "clash"):
        pre = kern + "-"
        if not name.startswith(pre):
            continue
        rest = name[len(pre):]                    # 如 lazy.min.yaml
        fam, _, tail = rest.partition(".")
        ext = "." + tail.split(".")[-1]           # .yaml / .conf
        mid = ".min" if tail.startswith("min.") else ""
        return "%s/profiles/%s%s%s" % (kern, fam, mid, ext)
    return None


def local_sha256(path):
    with open(path, "rb") as fh:
        return "sha256:" + hashlib.sha256(fh.read()).hexdigest()


def mismatched_assets(rel, root, assets):
    """远端资产 ↔ 本地 profile 的逐件比对。

    返回 (unpub, unverified)：
      unpub      —— 本地已改但远端资产还是旧的（**真漏发**，判负）
      unverified —— 无法比对（本地文件缺失 / 远端没给 digest），未验证，不判负

    为什么优先用 digest：GitHub 在 assets 上返回 `digest`（`sha256:...`），
    可直接与本地哈希比，**零下载**。无 digest 时退回「大小 + 下载全文比对」，
    两者都拿不到则记 unverified —— 不能默默放过（那正是本判据上一版栽的地方）。
    """
    unpub, unverified = [], []
    for name, rpath in sorted(rel.items()):
        a = assets.get(name)
        if a is None:
            unpub.append("%s（该 Release 没有这件资产）" % name)
            continue
        lp = os.path.join(root, rpath)
        if not os.path.isfile(lp):
            unverified.append("%s（本地缺 %s）" % (name, rpath))
            continue
        digest = (a.get("digest") or "").strip().lower()
        if digest.startswith("sha256:"):
            if digest != local_sha256(lp):
                unpub.append(name)
            continue
        try:
            want = open(lp, "rb").read()
        except OSError as e:
            unverified.append("%s（读不到本地文件：%s）" % (name, e))
            continue
        url = a.get("browser_download_url")
        if not url:
            unverified.append("%s（远端未给下载地址）" % name)
            continue
        if a.get("size") != len(want):
            unpub.append(name)
            continue
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "self-conf-release"})
            with urllib.request.urlopen(req) as r:
                got = r.read()
        except Exception as e:                        # noqa: BLE001
            unverified.append("%s（下载失败：%s）" % (name, e))
            continue
        if got != want:
            unpub.append(name)
    return unpub, unverified


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
    #   ⚠️ ② 的判据对象是「**profile 资产是否与已发布的一致**」，
    #      不是「tag 是否指向 HEAD」—— 这一点设计时**来回错了三次**，
    #      三次都实测过，把结论钉在这里：
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
    #      · 错法三 `git diff tag_sha..HEAD` 找变动过的 profile（2026-10-10
    #        实测撞上）：**与错法一同病**。tag 不动 ⇒ 当天改过 profile 并重发过，
    #        该 diff 恒非空 ⇒ 永远红，且提示的补救（再跑 --apply）治不了它。
    #        更糟的是浅克隆下 `git diff` 抛 Invalid revision range，被
    #        `except CalledProcessError` 吞成空列表 ⇒ **静默判绿**（假阴性）。
    #        实测：同一提交本地绿、CI（fetch-depth: 0）红。
    #
    #      ⇒ 真正该问的是：**本地 profile 与已发布资产一致吗？**
    #        直接比资产内容（digest 优先，零下载）：既不因 tag 不动而假红，
    #        也不依赖本地有完整 git 历史（浅克隆同样能判）。
    #        只改脚本/文档时 profile 内容没变 ⇒ 天然放行，不会误伤。
    #
    #   ⚠️ 只认**远端 Release**，不查本地 `git tag`：本地可能没 fetch 到 tag
    #      （实测 2026-10-10：远端 Release 已在、本地 `git tag --list` 却是空的）。
    #   ⚠️ 与 R3/R4 的分工：R3/R4 判「最新那张**自身**对不对」，R6 判「HEAD 的
    #      改动**有没有**被发出去」。没有 R6 时，一张新 Release 都没建的场景下
    #      R3/R4 会全绿（见头注）。
    head_tag = rp.plan(root)["tag"]
    head_sha = git("rev-parse", "HEAD")
    target_release = next((r for r in releases if r["tag_name"] == head_tag), None)
    have_tag = target_release is not None
    judge(have_tag,
          "R6a HEAD(%s) 的 Release 已发布" % head_tag,
          "R6a HEAD 该有的 Release %s **不存在** —— 当前 main 的改动还没发版。"
          "跑 release_publish.py（预览）→ --apply（真发）；"
          "若本次是功能变动，先按 ops.md §2 升号再发" % head_tag)
    if have_tag:
        # ② 该 Release 的资产与**本地 profile 逐件一致**（见上文「② 的判据对象」）
        #
        # ⚠️ 2026-10-10 重写（原实现有两个实测缺陷，见 gates.md §10.2.1）：
        #
        #   缺陷一 · 当天重发后**永远判负**（假阳性）
        #     原实现用 `git diff <tag_sha>..HEAD` 找变动过的 profile。但 tag 固定在
        #     「当天首次发布」的提交上，而 `release_publish.apply()` **从不移动 tag**
        #     （该函数 PATCH 分支只回写 body/name + 重传资产）。「一天一版」模型下，
        #     只要当天改过 profile 并重发过，`tag_sha..HEAD` 就恒非空 ⇒ **永远红**，
        #     且提示的补救办法（再跑 --apply）**治不了它**（实测：重发后依旧判负）。
        #     这与作者记为「错法一」的 `tag_sha == head_sha` 是**同一个病**，
        #     只是触发了另一条路径 —— 当时以为避开了，其实没有。
        #
        #   缺陷二 · 浅克隆下**静默判绿**（假阴性，更危险）
        #     本地是浅克隆时 tag 指向的 commit 对象不存在，`git diff` 抛
        #     `Invalid revision range`，而原实现 `except CalledProcessError: changed = []`
        #     把异常吞成「无变动」⇒ 判绿。实测：同一提交在本地绿、在 CI（fetch-depth: 0）红。
        #
        #   ⇒ 正解是**回到文档早已写明的判据对象**（gates.md §10.2.1 末段）：
        #     「**profile 是否已发出** —— 本地 profile 与已发布资产一致吗？」
        #     直接比资产内容，不猜 git 历史：既不会因 tag 不移动而假红，
        #     也不依赖本地是否有完整历史（浅克隆同样能判）。
        rel = {}
        for nm in want_assets:
            rp_ = asset_relpath(nm)
            if rp_:
                rel[nm] = rp_
        rel_assets = {a["name"]: a for a in target_release.get("assets", [])}
        unpub, unverified = mismatched_assets(rel, root, rel_assets)
        judge(not unpub,
              "R6b %s 的 %d 件资产与本地 profile 逐件一致" % (head_tag, len(rel)),
              "R6b %s 的资产与本地 profile 不一致（本地已改但没重发）：%s —— "
              "跑 release_publish.py --apply 重发资产（幂等回写同一张，tag 不动）"
              % (head_tag, ", ".join(unpub)))
        if unverified:
            skipped.append("R6b 部分资产未能比对：%s" % ", ".join(unverified))

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
