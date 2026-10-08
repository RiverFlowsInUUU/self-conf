---
name: self-conf
description: Surge / Egern / mihomo（Clash Meta）三内核代理配置模板的维护与改动。改 profile、调分流规则、加规则集、防 DNS 泄露、排查拦截失效或分流异常、发版、跑门禁时使用。只要用户提到 self-conf、Surge 配置、Egern 配置、mihomo / Clash 配置、分流版 / 懒人版、规则集、DNS 泄露、审计脚本、闸门，或让你改这个仓库里的配置，就用这个技能——即使用户没明说仓库名。它给出「先读哪份、改完跑哪道门禁、什么算做完」。
---

# self-conf 维护

三内核（Surge / Egern / mihomo）配置模板仓。**配置本身是给人读的**（注释写满了「为什么」）；
本技能是给 AI 的操作规程。

---

## 0 · 三条底线

1. **改配置 = 改两份**。每份 profile 都有 `.conf`/`.yaml` 与 `.min` 两份形态，
   **只差注释、内容必须逐字相同**。改完整版必须同步 `.min`（或跑 `make_min.py`）。
   漂移由 `check_min_pair.py` 兜底。
2. **`rules/*.yaml` 是生成物，不手改**。真源是 `rules/*.list`，跑
   `python skill/scripts/clash/build_rules.py` 重生成。
3. **改完必须跑门禁**。`python skill/tests/verify_all.py` —— 它是唯一入口，
   与 CI 同源。**"我改对了"不算做完，门禁绿了才算。**

---

## 1 · 我要做什么 → 读哪份 → 跑哪道门禁

| 你要做的事 | 先读 | 改完跑 |
|:--|:--|:--|
| 改 Surge 配置的某个键 | `reference/profiles/surge.md` + 该键在 `surge/profiles/*.conf` 里的注释 | `verify_all.py` |
| 改 Egern 配置 | `reference/profiles/egern.md` + `egern/profiles/*.yaml` 注释 | `verify_all.py` |
| 改 mihomo 配置 / 覆写脚本 | `reference/profiles/clash.md` | `verify_all.py` + `build_profiles.py --check` |
| 动 DNS / 防泄露逻辑 | `reference/dns.md` | `verify_all.py`（含 3 道 DNS 审计） |
| 加 / 换 / 删规则集 | `reference/rulesets.md` | `verify_all.py` |
| 排查拦截失效、分流异常 | `reference/pitfalls.md` | 按该篇定位 |
| 日常操作、发版、加固清单 | `reference/ops.md` | `verify_all.py` |
| 改门禁脚本、改判据 | `reference/gates.md` | `verify_all.py` + 该篇「新增闸门自查清单」 |

**reference/ 只有 8 篇**，全部在 `skill/reference/` 下：

```
profiles/{surge,egern,clash}.md   逐键语义 + 加固模板（改配置前查这里）
dns.md                            DNS 泄露原理 + 三内核落地语法
rulesets.md                       规则集选型、权重、跨内核差异
pitfalls.md                       事故复盘（排查时查这里）
ops.md                            日常操作 / 加固清单 / 发版规矩
gates.md                          门禁判据与纪律（改判据前必读）
```

---

## 2 · 目录结构

```
surge/profiles/    lazy.conf · lazy.min.conf · routing.conf · routing.min.conf
egern/profiles/    同名 .yaml
clash/profiles/    同名 .yaml（静态交付形态）
clash/override/    my_clash.js · my_clash_lazy.js（覆写脚本形态，挂订阅上用）
rules/             AI.list · apple_system.list · emby.list（唯一真源）
icons/             策略组图标，三内核共用
skill/
  SKILL.md         本文件（AI 入口）
  reference/       8 篇技术文档
  scripts/         审计 / 生成脚本（<kernel>/ 分子目录）
  tests/           门禁脚本 + verify_all.py（唯一入口）
```

**三内核并列、不混放**：同名判据脚本判据完全不同，按内核分目录 ⇒ 零改名、零冲突。

---

## 3 · 三内核的分歧（**不要去"对齐"**）

| 项 | Surge / Egern | mihomo |
|:--|:--|:--|
| 地区组 | `smart` + filter | `url-test` + filter |
| 订阅源 | `Airport` external 组 | `proxy-provider` |
| 倍率分档 | `policy-priority` 权重 | 模板靠 `filter` 分档；**脚本做不到**（生成期看不到节点名） |
| 规则集格式 | `.list` | `.mrs` / `.yaml` |
| `.min` 生成 | `make_min.py` | 无生成器，靠对拍兜底 |

⚠️ 倍率分档最容易被误判成漂移。`check_script_sync.py` 把它列为**已知差异**，
打印提醒但不判负。

---

## 4 · 共享资产：单一真源

`rules/*.list` 是唯一真源（Surge 原生格式），mihomo 用的 `.yaml` 由脚本生成：

```bash
python skill/scripts/clash/build_rules.py           # 生成
python skill/scripts/clash/build_rules.py --check   # 过期即判负（CI 用）
```

改内容只改 `.list`，重跑脚本 —— **物理上不可能漂移**。

---

## 5 · 已知陷阱（CI 暴露过、本地全绿也没用的）

| 现象 | 根因 | 处置 |
|:--|:--|:--|
| Linux CI 报「缺文件」，本地全过 | `_default_root()` 靠 `__file__` 推算，Actions 下算错 | 已改 CWD 优先 + 逐级向上探测 |
| `198.18.0.1` 被判真实 IP | 那是 mihomo 的 fake-ip 段（RFC 6815），Surge/Egern 侧不认 | 已加 `DOC_NETS` 白名单 |
| CRLF 判负 | Clash 侧曾混入 CRLF | 已转 LF + `.gitattributes` 钉 `eol=lf` |
| 子进程输出 UnicodeDecodeError | 中文 Windows 管道默认 GBK，而内容是 UTF-8 | 一律显式 `encoding='utf-8'` |
| 联网探测偶发超时 → CI 红 | 冷连接 / 丢包，不是端点失效 | 已加重试（`RETRIES=3`） |

**最重要的一条：本地全绿 ≠ 线上能跑。** 路径探测、编码、网络这类环境相关的东西，
必须让 CI 跑一遍才算数。

---

## 6 · 门禁（唯一入口 `verify_all.py`）

```bash
python skill/tests/verify_all.py          # 全跑，出汇总表
python skill/tests/verify_all.py -v       # 带详细输出
python skill/tests/verify_all.py --index  # 只列清单（现抓，勿手抄）
```

退出码：**0 = 全过 · 1 = 判负 · 2 = 环境不达标（先修环境，别读判据）· 3 = 未验证**。

⚠️ **3 不是绿**。汇总表里显示 ⚠️ 且不计入 passed。
分界线只有一条：**没读到远端真值 = 3；读到了但不过 = 1。**

判据要改？先读 `reference/gates.md` 的「新增闸门自查清单」——
**一道从不判红的闸门比没有更糟**，它给虚假的安全感。

---

## 7 · 红线

- ❌ 不手工编辑 `rules/*.yaml`（生成物，改真源 `.list`）
- ❌ 不让 `.min` 与完整版漂移（改一份必须同步另一份）
- ❌ 不为让门禁变绿而改判据 —— 改判据需要先说明「原判据错在哪」
- ⚠️ 结构性调整先补判据，不靠"再跑一遍"
