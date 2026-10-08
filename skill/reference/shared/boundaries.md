# 边界手册 · 例外与已论定

> **用途**：回答「**这处算不算例外 / 这个为什么不做**」——防止下一轮审查把**已论定的裁定**当成**新发现的缺陷**重报（实例：`probe` 系列被外审两轮误报为「不走四态协议」的例外，实为四态协议的规范用户）。
> **纪律**：本页**只放仓里没有家的内容**；有原件的只写一行指针，**不复述论证**（复述 = 制造第二份要同步的副本）。
> **每条必须带「重议条件」**：只写「不要再报」而无条件 = 禁止质疑，比没有清单更危险。
> **体量上限 40 行** —— 超了说明它在复制正文，那它自己就变成了新的漂移面。

## 1 · 例外清单（不适用，不是缺陷）

| 对象 | 为什么是例外 | 重议条件 |
|:-----|:-------------|:---------|
| `skill/scripts/release_publish.py`（含其 `/releases/latest` 读取） | 发布器，**刻意不套四态退出码** —— 读不到远端只影响「要不要多 PATCH 一次」，不是「未能验证」；`/releases/latest` 那条同理（依据：`apply()` 内的就近注释） | 引入需要 SKIP 语义的新发布流程 |
| 非 GitHub 的请求点：`egern/probe_dns_endpoints.py`、`egern/probe_doh.py`、`egern/_egern_common.py`、`surge/audit_ruleset_content.py` | 不走 `check_releases._api_json` 那套 **GitHub 请求异常分类**（各自处理自身网络失败）。⚠️ 这与**四态协议无关** —— `probe_dns_endpoints.py` 恰是四态协议的**规范用户**（缺参 → 2、有失效 → 1、`sys.exit(main())`） | 出现第二个消费 GitHub API 的脚本（须共用 `_api_json`） |
| Shadowrocket / sing-box 等其它内核 | 本仓覆盖 Surge + Egern + **mihomo（clash）** 三内核；其余内核不在范围内（`no-resolve`、`dns-server`、`fake-ip-filter` 在三内核语义已各不相同，见 [`cross-kernel-diff.md`](cross-kernel-diff.md)）：新增内核分支 |

## 2 · 已论定清单（裁定 ｜ 依据指针 ｜ 重议条件）

| 裁定 | 依据指针 | 重议条件 |
|:-----|:---------|:---------|
| 不做 `env_check.py` / `requirements.txt`（「错误信息即体检」） | 本页（仓内无其它原件） | 出现第一起「环境不达标但报错不足以定位」的事故 |
| 不做 GitHub API 合并拉取 / 结果缓存 | 本页 | releases 闸门耗时或限流成为真实瓶颈 |
| 不把各闸门「结论行」统一成机器可读一行式 | 本页 | 出现需要机器解析结论行的下游消费者 |
| SKIP 独立占码 3 ／ **2 的准入** = 本地前置检查（禁止把远端 HTTP 码翻译成 2）／ 404 语义分档 | [`troubleshoot-faq.md`](troubleshoot-faq.md) §8.2 | 改动退出码协议本身时（同步 §8.2） |
| 不做 E（AST 闸门 `check_exit_codes`） | `skill/SKILL.md` §3 其他共享纪律 | 见该处「推翻挂账的触发条件」 |
| 不做闸门清单的机器对账（`ci.yml` ↔ `verify_all.py`） | `skill/tests/verify_all.py` 头注 | 见该处「推翻挂账的触发条件」 |
| P5 `MyHome` 是**误报关闭**（照官方示例留的占位网络名），非缺陷 | [`ops.md`](ops.md) ／ [`cross-kernel-diff.md`](cross-kernel-diff.md) | 官方示例改名、或该段被实际启用时 |
| ~~clash 侧没有分流覆盖审计脚本~~ ⇒ **已于 2026-10-07 补出** `skill/scripts/clash/audit_routing_coverage.py`（闸门 #9） —— 意味着「规则是否真的接住了该接的域名」在 mihomo 侧**仍需人工/实测兜底**（闸门 #9 只校验策略字段，不验证真实域名命中） | [`hardening-checklist.md`](hardening-checklist.md) mihomo 章「验收标准」第 6 条；[`no-resolve-pairing.md`](no-resolve-pairing.md) mihomo 侧章（写明静态门禁只证明「不触发解析」，不能代替分流覆盖验证） | 补出 `skill/scripts/clash/audit_routing_coverage.py`（已于 2026-10-07 补出，离线档） 时 |
| **浅克隆下 `check_releases` 的成片红是噪声，不是缺陷**（缺完整历史 → R3/R4 假红：`81/28` → 完整克隆 `113/0`） | [`ops.md`](ops.md) §6.8「跑判据前先确认前置条件」 | `check_releases` 不再依赖 `--find-object` 反查诞生日期时 |
| Egern 审计**跨 profile 输出折叠**（约省 3 KB）不做 | `skill/reference/egern/checker.md`（记 22 离线 / 24 联网） | 该处不再引用这组条数时 |
| 历史 release notes（`release_publish.PUBLIC_NOTES`）保留**发布当时**的条数，不回改 | 该值记录发布时点的事实（v3.9 条目即此例）；自 v2.0.1／v4.0.1 起新条目已改为「当前版本信息统一只保留在文件头注」 | 需修订历史记录本身（发布勘误） |
| **「一天一版」只从 2026-10-04 起算** —— 此前的多版本日是历史，不回改、不追溯（09-24 分流版一天 8 个版本、09-26/27/28 各 3 个、09-29 各 2 个） | [`check_min_pair.py`](../../tests/check_min_pair.py) 的 `CADENCE_FROM` 就近注释 | 需要回溯修订历史版本号时（须连同 `config_old/` 与 Release 资产一起动） |
| 不建「版本日期口径」专用闸门：`number_birth` 用 `-G`（整行锚定）而非 `-S`（子串），由就近注释守 | [`release_publish.py`](../../scripts/release_publish.py) 的 `number_birth` 就近注释（含实测：互换后闸门仍全绿） | 出现「版本被算进错误日期的 Release」的实际事故时（即现役号开始互为前缀、-G 与 -S 分叉） |
| `GitHub` 不再单设分流组，`GitHub.list` 直指 `Proxy`（2026-10-05）—— 覆盖审计的 `github.com` 期望随之从 `{"GITHUB"}` 改为 `{"PROXY"}`，**即主动放弃「该文档有专属组」这条防线** | [`profile-anatomy.md`](../surge/profile-anatomy.md) §13.1 ／ [`rulesets.md`](rulesets.md) §4 | 需要「面板上单独调 GitHub 出口」时（重新建组，并把覆盖审计期望改回 `GITHUB`） |
| 不建「同日日志堆叠」专用闸门（2026-10-05）—— 实测相似度判据不可行：跨产品线**正确**的共同变更相似度达 0.46~1.00，与「该合并却没合并」的 0.49 无法用阈值区分；同版本内该合并的条目相似度仅 0.04~0.18，任何阈值都会全漏。⇒ 改由纪律守（[`ops.md`](ops.md) §6.9 第三条硬要求 + SKILL.md 动线⑦） | `ops.md` §6.9 第三条硬要求（含实测数据） | 出现「读者按性质数不清当天改了几件事」的实际投诉时（届时考虑人工复核清单或结构化条目字段） |
| `icons/icons-full.json`（大集成图标订阅）**引入对上游仓的外部引用**，与「本仓自包含」纪律（[`troubleshoot-faq.md`](troubleshoot-faq.md)）相冲 —— 用户明确要求两个 JSON：一个纯本仓、一个大集成 | [`rulesets.md`](rulesets.md) §5 素材表 | 上游 `jnlaoshu/MySelf` 或 `Koolson/Qure` 删仓 / 转私有导致引用失效时（届时删该 JSON 或改回自托管） |

## 3 · 不是缺陷的边界

- **审计通过 ≠ 配置可用**：脚本只覆盖**静态可判定**的部分；拦截效果、误杀、节点可用性必须实测（[`../../SKILL.md`](../../SKILL.md) §3）。
- 文档里的条数是**写作时点的约数**，随上游规则集漂移 —— 要精确值现跑脚本（同 §3「任何条数一律现抓」）。**本仓自托管集（`rules/AI.list`）的条数真源 = 该文件头部档案的自动合计行**（由生成器算出，勿手抄）。
