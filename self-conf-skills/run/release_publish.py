# -*- coding: utf-8 -*-
"""Release 发布器：当前版本 → 一张 GitHub Release（tag = vYYYY-MM-DD）

设计（2026-10-08 改革，取代旧的"时间线重建"模型）
────────────────────────────────────────────────
旧模型试图从 git 历史**重建**全部历史 Release（考古版本号首现日、比对归档快照、
维护 200 行 PUBLIC_NOTES / DAY_THEMES 手写表）。它带来三类长期负担：
  · 归档目录 `config_old/`（132 文件 / 2.3 MB，**已删除**）只为考古而存在
  · 手写历史表要与代码同步，于是又长出 CHANGELOG 漂移门禁、两套 CHANGELOG
  · 版本日期口径本身成了一个需要专门文档 + 已论定裁定去守的东西

新模型只做一件事：**把当前版本发出去**。
  · tag = vYYYY-MM-DD（发布日；同一天重复发布即幂等回写同一张）
  · 资产 = 三内核 × 两产品线 × 完整版/.min = 12 件，固定名不带版本号
  · 说明 = **人工撰写的 `releases/<tag>.md`**（面向用户的更新日志）
    ⚠️ 曾经从 commit subject 自动汇总 —— 2026-10-10 实测证明那是**内部语言**，
       不是给用户看的更新日志。现已**取消降级路径**：缺说明文件即拒绝发布。

用法（仓库根目录）:
    python self-conf-skills/run/release_publish.py --init     # 生成说明草稿（结构齐备）
    python self-conf-skills/run/release_publish.py            # 计划模式：预览，一个字不发
    python self-conf-skills/run/release_publish.py --apply    # 真发（需说明文件 + GITHUB_TOKEN）

退出码：0 = 成功/已预览 · 1 = 说明缺失或不合格（**拒绝发布**）· 2 = 缺 token

可选环境变量：
    GITHUB_REPO   目标仓库 owner/repo（默认 RiverFlowsInUUU/self-conf）
    GITHUB_TOKEN  --apply 必需
"""
import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import time
import urllib.request

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

REPO = os.environ.get("GITHUB_REPO", "RiverFlowsInUUU/self-conf")
API = "https://api.github.com/repos/%s" % REPO
UPLOAD = "https://uploads.github.com/repos/%s/releases" % REPO

# 三内核 × 两产品线 —— 全脚本只认这两个元组，不再散写硬编码
KERNS = ("surge", "egern", "clash")
FAMS = ("lazy", "routing")
KERN_EXT = {"surge": ".conf", "egern": ".yaml", "clash": ".yaml"}
FAM_CN = {"lazy": "懒人版", "routing": "分流版"}
KERN_LABEL = {"surge": "Surge", "egern": "Egern", "clash": "mihomo"}
# 资产固定名全集（check_releases 的白名单从这派生 —— 单一真源）
ASSET_NAMES = {"%s-%s%s" % (kern, fam, ext)
               for kern in KERNS for fam in FAMS
               for ext in (".conf", ".min.conf", ".yaml", ".min.yaml")}

TAG_RE = re.compile(r"^v(\d{4}-\d{2}-\d{2})$")


# ──────────────────────────── 本地状态 ────────────────────────────

def git(*a):
    # ⚠️ 必须显式 encoding='utf-8'：中文 Windows 上 subprocess 默认按 GBK 解码 stdout，
    #    而 commit message 是 UTF-8 ⇒ UnicodeDecodeError。本仓历史上踩过同类坑
    #    （子进程输出一律按 UTF-8 读，见 check_min_pair 的编码垫片）。
    return subprocess.check_output(["git", *a], encoding="utf-8",
                                   errors="replace",
                                   stderr=subprocess.DEVNULL).strip()


def repo_root():
    return git("rev-parse", "--show-toplevel")


def current_versions(root):
    """{fam: 'vX.Y.Z'} —— 从头注 `#! version=<fam>_vX.Y.Z` 读，三内核必须同号。"""
    out = {}
    for fam in FAMS:
        seen = {}
        for kern in KERNS:
            p = os.path.join(root, kern, "profiles", "%s%s" % (fam, KERN_EXT[kern]))
            try:
                with open(p, encoding="utf-8") as fh:
                    head = fh.read(400)
            except OSError:
                raise SystemExit("❌ 读不到 %s" % p)
            m = re.search(r"^#!\s+version=%s_(v\S+)" % fam, head, re.M)
            if not m:
                raise SystemExit("❌ %s 首行缺 `#! version=%s_vX.Y.Z` 头注" % (p, fam))
            seen[kern] = m.group(1)
        if len(set(seen.values())) != 1:
            raise SystemExit("❌ %s 三内核版本号不一致：%s" % (fam, seen))
        out[fam] = seen[KERNS[0]]
    return out


def last_release_tag():
    """最近一个 tag（形如 vYYYY-MM-DD）。没有则返回 None。"""
    try:
        tags = [t for t in git("tag", "--sort=-creatordate").splitlines() if TAG_RE.match(t)]
    except subprocess.CalledProcessError:
        return None
    return tags[0] if tags else None


# commit subject 里这些前缀/词不构成"给用户的变更"，不进 Release 说明
_NOISE = re.compile(r"^(chore|ci|style|test|refactor)(\(|:|：)|^Merge |^Revert ")


def collect_notes(since_tag):
    """从 `since_tag..HEAD` 的 commit **subject** 汇总发布说明 —— 取代旧的手写 PUBLIC_NOTES 表。

    为什么改成这样：旧表 200 行、要与代码同步、于是长出 CHANGELOG 漂移门禁。
    从 commit 派生则**不可能漂移** —— 它就是 commit 本身。

    ⚠️ 刻意**只取 subject**，不取 commit 正文的 `- ` 行：
       本仓 commit 正文是写给人看的详细记录（含 markdown 片段与回溯说明），
       抽成要点会变成一堆半句。subject 是唯一被约定为“一句话概括”的字段。
       要写进 Release 的内容，写进 subject 即可 —— 这也让 commit 更守纪律。
    过滤：去掉 chore/ci/style/test/refactor 与 merge/revert；剥掉 `fix:` 这类前缀。
    """
    rng = "%s..HEAD" % since_tag if since_tag else "HEAD"
    try:
        raw = git("log", rng, "--format=%s", "--no-merges")
    except subprocess.CalledProcessError:
        return []
    items = []
    for subject in raw.splitlines():
        subject = subject.strip()
        if not subject or _NOISE.match(subject):
            continue
        # 剥 `fix(scope):` / `feat：` 这类前缀
        subject = re.sub(r"^[a-z]+(\([^)]*\))?\s*[:：]\s*", "", subject)
        if subject:
            items.append(subject)
    return items


# ──────────────────────────── 计划 ────────────────────────────

def plan(root):
    """当前版本 → 一张 Release 计划。"""
    vers = current_versions(root)
    since = last_release_tag()
    notes = collect_notes(since)
    today = git("log", "-1", "--format=%as")
    assets = {}
    for fam in FAMS:
        for kern in KERNS:
            ext = KERN_EXT[kern]
            for suffix in ("", ".min"):
                p = os.path.join(root, kern, "profiles",
                                 "%s%s%s" % (fam, suffix, ext))
                if os.path.exists(p):
                    assets["%s-%s%s%s" % (kern, fam, suffix, ext)] = p
    return {"tag": "v" + today, "date": today, "versions": vers,
            "notes": notes, "since": since, "assets": assets}


def notes_file_path(root, tag):
    """面向用户的发布说明文件：`releases/<tag>.md`。"""
    return os.path.join(root, "releases", "%s.md" % tag)


# ── 说明文件的格式判据（机械部分：是非，不是好坏）─────────────────────────
# ⚠️ 只判「结构在不在」，**不判文采** —— 好坏是价值判断，写成判据会退化成
#    关键词黑名单式的假精确。结构缺失则是明确的错，可以硬判。
#    2026-10-10 事故：发布器原先从 commit subject 汇总正文，产出的全是
#    「Release 断言新增 R6」这类内部语言，与往日用户向更新日志形态不符。
REQUIRED_H2 = "## 适用版本"
# 变更分列段：至少要有其一（两版都有变更时用「共同变更」，单边时用对应产品线）
CHANGE_H2 = ("## 共同变更", "## 懒人版变更", "## 分流版变更")


def notes_problems(text, versions):
    """返回说明文件的问题清单；空列表 = 合格。

    ⚠️ 判据要写**具体**，不能写 `if "## " not in text` 这种粗判 ——
       实测漏判过：正文只要含 `## 适用版本` 就满足了「有 ##」，
       「缺变更分列段」的情况整类溜过（复核脚本抓到的第 8 个用例）。
       所以这里逐个检查**具体的段名**。
    """
    bad = []
    lines = text.splitlines()
    h1 = [l for l in lines if l.startswith("# ")]
    if not h1:
        bad.append("缺一级标题（应为 `# <产品线> vX[ → vY] 更新日志`）")
    elif "更新日志" not in h1[0]:
        bad.append("一级标题缺「更新日志」字样：%s" % h1[0])
    if REQUIRED_H2 not in text:
        bad.append("缺 `%s` 段" % REQUIRED_H2)
    if not any(h in text for h in CHANGE_H2):
        bad.append("缺变更分列段(需其一：%s)" % " / ".join(CHANGE_H2))
    for v in sorted(versions):
        if v not in text:
            bad.append("正文未出现当前版本号 %s" % v)
    if "由 commit 自动汇总" in text:
        bad.append("正文含自动汇总的降级标记 —— 那是内部语言，不应发布")
    # title 行的占位符必须是**填过的**（草稿里是 `← …` 的提示语）
    mt = re.search(r"<!--\s*title:\s*(.*?)\s*-->", text)
    if mt and ("←" in mt.group(1) or not mt.group(1).strip()):
        bad.append("`<!-- title: -->` 还是草稿占位符 —— 请填成当日主题")
    return bad


def notes_draft(root, p):
    """生成说明文件草稿：结构齐备 + 版本号已填，只留「人话」待补。

    目的：让「写说明」从负担变成填空 —— 这是「硬拦」能被接受的前提。
    """
    fam_lines = []
    for fam in FAMS:
        fam_lines.append("## %s变更" % FAM_CN[fam])
        fam_lines.append("")
        # ⚠️ p["versions"][fam] 已含 `v` 前缀（如 `v1.0.1`），不要再拼一个 v
        fam_lines.append("- **%s** ← 用一句话说明用户会看到什么不同"
                         "（不是改了什么代码）" % p["versions"][fam])
        fam_lines.append("")
    return "\n".join([
        "<!-- title: ← 当日主题（一句话，会显示在 Release 标题里，可带 emoji） -->",
        "",
        "# %s 更新日志" % " → ".join(
            "%s %s" % (FAM_CN[f], p["versions"][f]) for f in FAMS),
        "",
        "> ← 一句话说清本次范围（例如：本次仅懒人版有变更，分流版无变化）。",
        "",
    ] + fam_lines + [
        REQUIRED_H2,
        "",
    ] + ["- %s %s" % (FAM_CN[f], p["versions"][f]) for f in FAMS] + [
        "",
        "<!-- 写法见 self-conf-skills/references/ops.md 的〈标题与正文模板〉：",
        "     讲用户会遇到什么；避免判据编号 / 脚本名 / 函数名 / commit 这类内部词汇。",
        "     写完删掉本注释。 -->",
        "",
    ])


def _human_notes(root, tag):
    """读人工维护的发布说明；没有则返回 None。

    ⚠️ 为什么要这个（2026-10-10 事故）：
        原先说明**只**从 commit subject 自动汇总 ⇒ 发出来的 Release 是
        「Release 断言新增 R6」「路径统一 as_posix()」这类**内部工程语言**，
        与往日 Release 的形态（`# …更新日志` 标题、`## 懒人版变更 / ## 分流版变更`
        /`## 适用版本` 分列、面向用户描述行为影响）**完全不符**。
        ⇒ 说明必须有**人工把关的入口**；自动汇总降级为「提醒」，不再直接当正文。
    """
    p = notes_file_path(root, tag)
    if os.path.isfile(p):
        with open(p, encoding="utf-8") as fh:
            return fh.read().strip()
    return None


def release_body(p, human=None):
    """正文 = 说明文件（**唯一来源**）。

    ⚠️ 刻意**不提供**「自动汇总」的降级正文（2026-10-10 第二次修正）：
        曾经的降级路径是漏洞本身 —— 它让「没写说明」也能发出去，
        且发出来的正是内部语言。现在缺说明文件由 main() 直接拒绝发布，
        本函数只负责在说明**存在**时把它取出来。
    """
    if human:
        return human
    raise SystemExit("❌ 无发布说明 —— 不应走到这里（main 应先拦下）。")


def release_title(p, human=None):
    """Release 标题。

    ⚠️ 为什么标题也要从**说明文件**派生（2026-10-10 第二次事故）：
        原先标题由本函数按 `日期 · 版本号` 拼死，而 `apply()` 每次都会 PATCH
        `name` ⇒ **手工在 GitHub 上改过的标题会被下一次 --apply 覆盖回模板**。
        实测：把标题手改成「📱 2026-10-10 · 修复 Google Play 无法更新与下载」后，
        跑一次 `--apply` 就被打回 `2026-10-10 · 懒人版 v1.0.1 / 分流版 v1.0.0`。
        ⇒ 任何「手工改远端」的做法都是靠人话；正确做法是**让标题也有仓库内的真源**。
        约定：说明文件里写一行 HTML 注释 `<!-- title: … -->`，
        有则用它（去掉 `title:` 前缀），没有则退回 `日期 · 版本号`。
    """
    if human:
        m = re.search(r"<!--\s*title:\s*(.+?)\s*-->", human)
        if m:
            return "%s · %s" % (p["tag"][1:], m.group(1))
    return "%s · %s" % (p["tag"][1:], " / ".join(
        "%s %s" % (FAM_CN[f], p["versions"][f]) for f in FAMS))


# ──────────────────────────── GitHub API ────────────────────────────

def api_req(url, token, method="GET", data=None, ctype="application/json", raw=None):
    body = raw if raw is not None else (
        json.dumps(data, ensure_ascii=False).encode() if data is not None else None)
    req = urllib.request.Request(url, data=body, method=method)
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("User-Agent", "self-conf-release")
    if token:
        req.add_header("Authorization", "Bearer %s" % token)
    if body is not None:
        req.add_header("Content-Type", ctype)
    return urllib.request.urlopen(req)


def existing_releases(token):
    out, page = [], 1
    while True:
        with api_req("%s/releases?per_page=100&page=%d" % (API, page), token) as r:
            batch = json.load(r)
        out += batch
        if len(batch) < 100:
            return out
        page += 1


def _asset_stale(asset, path):
    """Release 上同名资产与本地不一致？优先用 digest（零下载），否则大小 + 全量比对。"""
    with open(path, "rb") as fh:
        local = fh.read()
    digest = asset.get("digest") or ""
    if digest.startswith("sha256:"):
        return digest != "sha256:" + hashlib.sha256(local).hexdigest()
    if asset.get("size") != len(local):
        return True
    try:
        req = urllib.request.Request(asset["browser_download_url"],
                                     headers={"User-Agent": "self-conf-release"})
        return urllib.request.urlopen(req).read() != local
    except Exception:                                       # noqa: BLE001
        return False                                        # 下载失败 ⇒ 宁可不误删


def apply(p, token, human=None):
    body = release_body(p, human if human is not None
                        else _human_notes(repo_root(), p["tag"]))
    title = release_title(p, body)
    ex = {r["tag_name"]: r for r in existing_releases(token)}
    rel = ex.get(p["tag"])
    if rel:
        patch = {}
        if (rel.get("body") or "") != body:
            patch["body"] = body
        if (rel.get("name") or "") != title:
            patch["name"] = title
        if patch:
            api_req("%s/releases/%s" % (API, rel["id"]), token, "PATCH", patch)
            print("回写 %s" % p["tag"])
        else:
            print("已存在且一致：%s" % p["tag"])
    else:
        with api_req(API + "/releases", token, "POST",
                     {"tag_name": p["tag"], "target_commitish": "main",
                      "name": title, "body": body, "make_latest": "true"}) as r:
            rel = json.load(r)
        print("创建 %s" % p["tag"])
        time.sleep(2)                                       # 拉开 created_at，稳定列表排序

    have = {a["name"]: a for a in rel.get("assets", [])}
    deleted = set()
    for a in rel.get("assets", []):
        if a["name"] not in p["assets"] or _asset_stale(a, p["assets"][a["name"]]):
            api_req("%s/releases/assets/%s" % (API, a["id"]), token, "DELETE")
            deleted.add(a["name"])
            print("  删除陈旧资产 %s" % a["name"])
    for name, path in sorted(p["assets"].items()):
        if name in have and name not in deleted:
            continue
        with open(path, "rb") as fh:
            raw = fh.read()
        api_req("%s/%s/assets?name=%s" % (UPLOAD, rel["id"], name), token, "POST",
                raw=raw, ctype="application/octet-stream")
        print("  上传 %s" % name)
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="真发（默认只出计划）")
    ap.add_argument("--init", action="store_true",
                    help="生成 releases/<tag>.md 草稿骨架（结构齐备，只待补人话）")
    ap.add_argument("--token", default=os.environ.get("GITHUB_TOKEN"))
    args = ap.parse_args()

    root = repo_root()
    p = plan(root)
    npath = notes_file_path(root, p["tag"])
    rel = os.path.relpath(npath, root)

    # ── --init：生成草稿（不发布）────────────────────────────────────────
    if args.init:
        if os.path.exists(npath):
            print("已存在，未覆盖：%s" % rel)
            return 0
        os.makedirs(os.path.dirname(npath), exist_ok=True)
        with open(npath, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(notes_draft(root, p))
        print("已生成草稿：%s" % rel)
        print("→ 打开它，把每条的「一句话」补成用户能看懂的话（结构已就绪）。")
        return 0

    human = _human_notes(root, p["tag"])
    print("tag      %s" % p["tag"])
    print("版本     %s" % " · ".join("%s %s" % (FAM_CN[f], p["versions"][f]) for f in FAMS))
    print("自       %s" % (p["since"] or "（首个版本）"))
    print("资产     %d 件" % len(p["assets"]))
    print("说明     %s" % ("%s（已撰写）" % rel if human else "❌ 未撰写：%s" % rel))

    if not args.apply:
        if human:
            print("\n──── 说明预览 ────")
            print(human)
        else:
            print("\n⚠️ 还没有 %s —— 生成草稿："
                  "python self-conf-skills/run/release_publish.py --init" % rel)
        print("\n（计划模式：一个字都没发。加 --apply 才发布）")
        return 0

    # ── --apply：说明缺失或结构不合格 ⇒ **拒绝发布** ──────────────────────
    #    这是 2026-10-10 事故的根本修法：不是「加判据去猜人话」，
    #    而是**让「没有面向用户的说明」这种 Release 根本发不出去**。
    #    原先的「降级为 commit 汇总 + 警告」是漏洞本身 —— 它让偷懒仍能通过。
    if not human:
        print("\n❌ 拒绝发布：缺少 %s" % rel)
        print("   先跑：python self-conf-skills/run/release_publish.py --init")
        print("   然后把草稿里的「一句话」补成用户能看懂的话（写法见 ops.md 标题与正文模板）。")
        return 1
    probs = notes_problems(human, set(p["versions"].values()))
    if probs:
        print("\n❌ 拒绝发布：%s 格式不合格" % rel)
        for b in probs:
            print("   · %s" % b)
        print("   格式要求见 self-conf-skills/references/ops.md 的〈标题与正文模板〉。")
        return 1
    if not args.token:
        print("❌ --apply 需要 GITHUB_TOKEN")
        return 2
    print("\n──── 说明预览 ────")
    print(human)
    return apply(p, args.token, human)


if __name__ == "__main__":
    sys.exit(main())
