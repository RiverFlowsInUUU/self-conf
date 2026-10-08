#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Agent Skill 规范合规 —— 保证本目录是一个**标准 Skill**。

依据：agentskills.io 规范（Anthropic 2025-12-18 发布为开放标准，30+ 工具支持：
Claude Code / Cursor / Codex CLI / Gemini CLI / GitHub Copilot / Amp / Windsurf …）

规范硬性要求：
  ① 目录里有 `SKILL.md`，含 YAML frontmatter（`---` 包围）
  ② frontmatter 必须有 `name` 与 `description`
  ③ `name`：1-64 字符，**仅小写字母/数字/连字符**，不以连字符开头/结尾，
     无连续连字符，且**必须与父目录名一致**
  ④ `description`：1-1024 字符，非空
  ⑤ （推荐）主 SKILL.md < 500 行 —— 超了说明该把细节拆进 references/

规范说明 `scripts/` `references/` `assets/` 是**推荐**而非强制
（"may contain any files and directories beyond the required SKILL.md"）
⇒ 本仓用 `gates/` `run/` `lib/` `references/`，是合法的自定义结构。

退出码：0 = 合规 · 1 = 违规 · 2 = 环境不达标
"""
import io
import os
import re
import sys

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL_DIR = os.path.dirname(HERE)          # <root>/self-conf-skills
ROOT = os.path.dirname(SKILL_DIR)
SKILL_MD = os.path.join(SKILL_DIR, "SKILL.md")

NAME_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
MAX_SKILL_LINES = 500


def parse_frontmatter(text):
    """返回 dict（只做本判据需要的浅解析，不引第三方 yaml）。"""
    if not text.startswith("---"):
        return None
    end = text.find("\n---", 3)
    if end < 0:
        return None
    fm = text[3:end]
    out = {}
    for ln in fm.splitlines():
        m = re.match(r"^([A-Za-z_-]+):\s*(.*)$", ln)
        if m:
            out[m.group(1)] = m.group(2).strip()
    return out


def main():
    if not os.path.isfile(os.path.join(ROOT, "surge", "profiles", "routing.conf")):
        print("❌ 不在仓库根 —— 环境不达标")
        return 2

    bad = []
    if not os.path.isfile(SKILL_MD):
        print("❌ 缺 %s —— 不是合法的 Agent Skill" % os.path.relpath(SKILL_MD, ROOT))
        return 1

    txt = io.open(SKILL_MD, encoding="utf-8").read()
    fm = parse_frontmatter(txt)
    if fm is None:
        bad.append("SKILL.md 缺 YAML frontmatter（必须以 `---` 包围）")
    else:
        name = fm.get("name", "")
        desc = fm.get("description", "")
        if not name:
            bad.append("frontmatter 缺必填字段 `name`")
        else:
            if not NAME_RE.match(name):
                bad.append("`name: %s` 不合规 —— 只能小写字母/数字/连字符，"
                           "不能以连字符开头结尾，不能有连续连字符" % name)
            if len(name) > 64:
                bad.append("`name` 超过 64 字符")
            if name != os.path.basename(SKILL_DIR):
                bad.append("`name: %s` 与父目录名 `%s` 不一致 —— 规范要求必须匹配"
                           % (name, os.path.basename(SKILL_DIR)))
        if not desc:
            bad.append("frontmatter 缺必填字段 `description`")
        elif len(desc) > 1024:
            bad.append("`description` 有 %d 字符 > 1024 上限" % len(desc))
        elif len(desc) < 40:
            bad.append("`description` 只有 %d 字符 —— 太短，agent 无法据此判断"
                       "何时该用本技能" % len(desc))

    n_lines = len(txt.splitlines())
    if n_lines > MAX_SKILL_LINES:
        bad.append("SKILL.md 有 %d 行 > %d 行 —— 规范建议把细节拆进 references/"
                   % (n_lines, MAX_SKILL_LINES))

    # 结构：references/ 与 gates/ 应存在（本仓约定，也是渐进披露的载体）
    for d in ("references", "gates", "run"):
        if not os.path.isdir(os.path.join(SKILL_DIR, d)):
            bad.append("缺 %s/ —— 渐进披露的载体缺失" % d)

    print("Agent Skill 规范合规（%s）" % os.path.basename(SKILL_DIR))
    print("-" * 78)
    if bad:
        for b in bad:
            print("  NG %s" % b)
        print("-" * 78)
        print("不合规 %d 处 —— 见 https://agentskills.io/specification" % len(bad))
        return 1
    d = fm.get("description", "")
    print("  OK name=%s（匹配目录名）· description %d 字符"
          % (fm.get("name"), len(d)))
    print("  OK SKILL.md %d 行 · references/ gates/ run/ 齐备" % n_lines)
    print("  OK 符合 agentskills.io 开放标准（30+ 工具可加载）")
    print("-" * 78)
    return 0


if __name__ == "__main__":
    sys.exit(main())
