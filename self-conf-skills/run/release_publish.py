# -*- coding: utf-8 -*-
"""Release 发布器：当前版本 → 一张 GitHub Release（tag = vYYYY-MM-DD）

设计（2026-10-08 改革，取代旧的"时间线重建"模型）
────────────────────────────────────────────────
旧模型试图从 git 历史**重建**全部历史 Release（考古版本号首现日、比对归档快照、
维护 200 行 PUBLIC_NOTES / DAY_THEMES 手写表）。它带来三类长期负担：
  · 归档目录 `config_old/`（132 文件 / 2.3 MB）只为考古而存在
  · 手写历史表要与代码同步，于是又长出 CHANGELOG 漂移门禁、两套 CHANGELOG
  · 版本日期口径本身成了一个需要专门文档 + 已论定裁定去守的东西

新模型只做一件事：**把当前版本发出去**。
  · tag = vYYYY-MM-DD（发布日；同一天重复发布即幂等回写同一张）
  · 资产 = 三内核 × 两产品线 × 完整版/.min = 12 件，固定名不带版本号
  · 说明 = **从上次发版以来的 commit 自动汇总**（见 collect_notes）
    —— 不再有手写历史表，因此不可能与代码漂移

用法（仓库根目录）:
    python self-conf-skills/run/release_publish.py                # 计划模式：打印将要发布的内容，一个字不发
    python self-conf-skills/run/release_publish.py --apply        # 真发（需 GITHUB_TOKEN）

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


def release_body(p):
    lines = ["# %s" % " / ".join("%s %s" % (FAM_CN[f], p["versions"][f]) for f in FAMS)]
    lines.append("")
    if p["since"]:
        lines.append("> 自上一版（`%s`）以来的变更。" % p["since"])
    else:
        lines.append("> 首个版本。")
    lines.append("")
    if not p["notes"]:
        lines.append("（本次没有面向用户的变更条目。）")
    for subject in p["notes"]:
        lines.append("- %s" % subject)
    lines.append("")
    lines.append("## 取用")
    lines.append("")
    for fam in FAMS:
        for kern in KERNS:
            ext = KERN_EXT[kern]
            for suffix in ("", ".min"):
                name = "%s-%s%s%s" % (kern, fam, suffix, ext)
                if name in p["assets"]:
                    lines.append("- [`%s`](https://github.com/%s/releases/download/%s/%s)"
                                 % (name, REPO, p["tag"], name))
    return "\n".join(lines)


def release_title(p):
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


def apply(p, token):
    body, title = release_body(p), release_title(p)
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
    ap.add_argument("--token", default=os.environ.get("GITHUB_TOKEN"))
    args = ap.parse_args()

    p = plan(repo_root())
    print("tag      %s" % p["tag"])
    print("版本     %s" % " · ".join("%s %s" % (FAM_CN[f], p["versions"][f]) for f in FAMS))
    print("自       %s" % (p["since"] or "（首个版本）"))
    print("资产     %d 件" % len(p["assets"]))
    print("\n──── 说明预览 ────")
    print(release_body(p))

    if not args.apply:
        print("\n（计划模式：一个字都没发。加 --apply 才发布）")
        return 0
    if not args.token:
        print("❌ --apply 需要 GITHUB_TOKEN")
        return 2
    return apply(p, args.token)


if __name__ == "__main__":
    sys.exit(main())
