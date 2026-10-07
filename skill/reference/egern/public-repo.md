# 公开模板仓库（本项目的对外交付物 · Egern 侧）

> 本文是 [`SKILL.md`](../../SKILL.md) 的引用文件。 **何时读**：要更新模板 / 了解公开仓库结构时。

---

自用配置已脱敏发布为公开模板 + 本 skill：

**https://github.com/RiverFlowsInUUU/self-conf**（Egern 分支在 `egern/`，与 Surge / mihomo 同仓）

```
README.md                                   # 门面（人类看的唯一文档）：订阅地址 + 分组表 + 隐私对照 + AI 指路
LICENSE · .gitattributes · .gitignore
icons/                                      # 图标 PNG + icons.json / icons-full.json —— 两内核共用
rules/                                      # 本仓自托管的规则集（当前 1 份：Egern 用的 apple_system.list）
skill/                                      # ★ AI 驱动的唯一知识库
  SKILL.md                                  # 单一入口：底线与纪律 → §0 判内核 → 分支 A/B
  reference/shared/                         # 跨内核主题七篇（cross-kernel-diff · rulesets · ops · troubleshoot-faq 等）
  reference/{surge,egern}/                  # 单侧主题（profile-anatomy 逐键权威 · hardening-template · pitfalls · checker 等）
  scripts/{surge,egern}/ · tests/           # 审计脚本 + 五项共享检查
egern/profiles/lazy.yaml / lazy.min.yaml    # 懒人版 · 可选（4 组 / 10 条规则；隐藏订阅槽位 Airport）
egern/profiles/routing.yaml / .min.yaml     # 分流版 · 推荐（脱敏模板：2 条占位节点 + 1 个机场槽位，凭据与订阅均为占位符）
egern/profiles/config_old/                  # 历史归档（配置变动时按规则入档，只增不删）
.github/workflows/ci.yml                    # CI：六步检查（push / PR 自动）
```

> 原根级 `docs/`、两侧 `DetailsReadme/`、`CHANGELOG.md`、`skill/README.md` 已于 2026-09-27
> 全部并入 `skill/`（git 历史与备份 tag `pre-cleanup-20260927` 可查）。

> **可选版本只有两个** —— `routing`（分流版 · 推荐）与 `lazy`（懒人版），文件名不带版本号；
> 当前是第哪一版写在头注 `#! version=` 里；配置变动时变动前的旧配置归档进 `profiles/config_old/`
> （归档号 = 目录内最新号的下一位；2026-09-29 起三段制 X.Y.Z，满 10 进 1，完整版与 `.min` 成对），更早历史看 git。

**要更新模板时**：**直接在仓库里改 `profiles/*.yaml` 即可。** 这份模板早已完成脱敏
（2 条占位节点 + 1 个占位订阅，全都连不出去，无真实证书），改它不需要"从自用配置重新生成"。
改完按 [`SKILL.md`](../../SKILL.md) §3 的标准动线走（归档 → 改完整版 → `make_min.py` → 闸门 → 推送）。

> 📦 **历史做法（已不再使用）**：早期由维护者本地的 `outputs/` 脚本链生成 ——
> `_build_public_template.py`（带断言的行级替换 + 38 个敏感串零残留自检）、
> `_transform_template.py`、`_make_min.py`、`_fetch_icons.py`、
> `_publish_to_github.py`（Git Data API 单次提交；空仓库需先落初始化提交，
> 否则 `POST /git/blobs` 报 `409 Git Repository is empty`）。
> ⚠️ 这些脚本**不在本仓库**（避免暴露构建侧私人路径）。"不要手改仓库里的 yaml"这条老规矩**已作废**：
> 现在的版本就是在仓库里直接改出来的。若将来要恢复"从自用配置生成"的流程，方法论见 skill
> `github-publish-sanitized-repo`，需按它重建脚本。

📌 **验证 = CI（`.github/workflows/ci.yml`，push / PR 自动）+ 本地同组命令复现**
（命令清单见 [`SKILL.md`](../../SKILL.md) §3）；探针 / 量测类脚本（`probe_*` / `weigh_*` / `profile_ruleset`）不在验证链上，是手工工具。

**脱敏清单（这五类必须洗）**：节点 server/凭据/sni/reality 公钥 → 占位；
机场订阅 URL（含 token）→ 占位；`mitm.ca_p12` + `ca_passphrase`（个人 CA 私钥）→ **注释掉**；
机场组名/节点名 → `Airport-A` / `Node-1`；`dns.forward` 里的**节点域名** → `example-node.com`。

## README 的边界：只讲产品，不讲改动过程

README 是**产品介绍** —— 读者要知道「这东西是什么、怎么用」。以下三类**不属于**它：

- 🚫 **归类 / 设计自述** —— 「某组为什么不算开关」「**上面是分类顺序**」这类解释我们怎么想的话。
- 🚫 **与评审 / 工单的对话** —— 「原写 X 属误标，已按功能拆开」。
- 🚫 **内部判据与断言名** —— 「由某脚本某断言守着」。

判据与原理 → `skill/reference/`（对应主题文件）。改动历史看 git log。

> 改 README 的 **markdown 版式**前先问 GitHub 本人（`POST /markdown` 接口，推送前就能看出某写法
> 会不会被 sanitizer 剥掉）：见 [`../surge/public-repo.md`](../surge/public-repo.md) §5.1。

**自查**：README 里出现「为什么…」「不算」「误标」「判据」「原写」「上面是…顺序」，
八成就是改动记录漏出来了。

同一事实要用**使用者视角的性质**表述：`不被规则引用`（内部判据）→ `独立于规则链路`（读者能懂）。

实测反例（2026-09-22）：在 README 里补「我们为什么这样归类 / 上面是分类顺序」这类说明，
用户一句打回 —— 「readme 是产品介绍，不是自说自话的地方」。

## 首页不列规则集

规则集属**实现侧**：用了哪些 `.list`、从哪个仓库拉、顺序怎么排。使用者关心的是**分流结果**。

| | 首页（`README.md`） | `reference/shared/rulesets.md` |
|:--|:--|:--|
| 顺序表 | 「匹配什么 → 去向」（白名单 / 广告 / 按应用 / 国内…） | 逐条列出规则集名与参数 |
| 规则集清单 | ❌ 一个都不出现 | ✅ 文件名 · 去向 · 来源 URL |
| 来源仓库 | ❌ | ✅ 含图标、数据库、许可 |

**判据**：首页上这句话，对读者**用**这份配置有没有帮助？
「`OpenAI.list` → `ChatGPT`」没有意义 —— 使用者不能按规则集文件名分流；
「ChatGPT 走 `ChatGPT` 组，面板上可改道」才有意义。

实测（2026-09-22）：首页原挂着「📚 规则来源」段 + 「分流版的应用规则」表 + 「排序约束」，
用户连判两次 —— 先要求来源段下沉，随即补充：「不仅是规则集的来源，而且是有哪些规则集……
我认为都没必要放在首页的 README 里面。」

闸门：`verify_readme_tone.py`（维护者本地的装配闸门，不进公开仓）的「首页无规则集文件与来源仓库」一项。
⚠️ 只对**配置模板仓**生效 —— `jinx` 本身是规则集仓，README 讲规则集是它的产品，不适用这条。
