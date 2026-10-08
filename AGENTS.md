# self-conf · Agent 指南

**给任何 AI 编码助手看的操作手册。** 人类请看 [`README.md`](./README.md)；
`SECURITY.md` 是公开仓的安全纪律。

本仓是 Surge / Egern / mihomo（Clash Meta）**三内核代理配置模板**。
配置本身是给人读的（注释写满「为什么」）；本文件是给 AI 的操作规程。

> 📌 **换任何 AI 都能用**：本文件是**唯一真源**。各工具的约定文件
> （`CLAUDE.md` · `GEMINI.md` · `.cursorrules` · `.github/copilot-instructions.md`）
> 是**薄指针 + 关键红线**，内容以本文件为准 —— 不做第二份副本，避免漂移。

---

## 0 · 四条底线

1. **改配置 = 改两份**。每份 profile 有 `.conf`/`.yaml` 与 `.min` 两份形态，**只差注释、
   内容必须逐字相同**。改完整版后跑 `make_min.py --apply` 同步（漂移由 `check_min_pair.py` 兜底）。
2. **clash 的 profile 是生成物，改 JS 不改 YAML**。`clash/profiles/*.yaml` 由
   `clash/override/my_clash*.js` 生成 ⇒ **改配置要改那份 JS**，然后
   `python skill/scripts/clash/build_profiles.py` 重生成（`--check` 在门禁里，过期即判负）。
   ⚠️ 直接改 YAML 会在下次生成时被覆盖。
   （Surge / Egern 的 profile **不是**生成物 —— 那两侧直接改 `.conf` / `.yaml`。）
3. **`rules/*.yaml` 是生成物，不手改**。真源是 `rules/*.list`，跑
   `python skill/scripts/clash/build_rules.py` 重生成。
4. **改完必须跑门禁**：`python skill/tests/verify_all.py` —— 唯一入口，与 CI 同源。
   **"我改对了"不算做完，门禁绿了才算。**

---

## 1 · 怎么用这些文档（**先看这里，不要整篇读**）

8 篇文档每篇 45~135 KB。**整篇读是浪费** —— 它们都带完整标题层级，
用 `grep` 定位到节，通常只需读 2~5 KB。

```bash
# ① 定位：先 grep 关键词拿行号与节标题
grep -n "include-all" skill/reference/profiles/clash.md
# ② 只读那一节：从命中行往上找最近的标题，往下读到下一个同级标题
```

| 你要做的事 | 读哪份 | 改哪个文件 | 常见 grep 关键词 |
|:--|:--|:--|:--|
| 改 Surge 配置的某个键 | `skill/reference/profiles/surge.md` | `surge/profiles/*.conf` | 键名（`hijack-dns` / `ipv6` / `proxy-test-url`） |
| 改 Egern 配置 | `skill/reference/profiles/egern.md` | `egern/profiles/*.yaml` | 键名（`forward` / `policy_groups` / `proxy_nameservers`） |
| 改 mihomo 配置 | `skill/reference/profiles/clash.md` | ⚠️ **`clash/override/my_clash*.js`**（不是 yaml，见底线 2） | 键名（`include-all` / `fake-ip-filter` / `nameserver-policy`） |
| 动 DNS / 防泄露逻辑 | `skill/reference/dns.md` | 三处对应文件 | `泄露` / `引导` / `no-resolve` / `明文` |
| 加 / 换 / 删规则集 | `skill/reference/rulesets.md` | `rules/*.list` + 三侧 profile | 规则集名（`AI.list` / `Jinja` / `mrs`） |
| 排查拦截失效、分流异常 | `skill/reference/pitfalls.md` | — | 现象词（`没有拦截` / `走直连` / `解析`） |
| 日常操作 / 发版 / 加固清单 | `skill/reference/ops.md` | — | `升号` / `Release` / `加固清单` |
| 改门禁脚本 / 改判据 | `skill/reference/gates.md` | `skill/tests/` · `skill/scripts/` | `判据` / `退出码` / `新增闸门` |

**每条配置键的权威解释，是它自己在 profile 里的注释**（写满了理由）。
文档是「跨键的机制与取舍」，不是注释的复述。改键之前先读那个键的注释。

---

## 2 · 目录结构

```
AGENTS.md          AI 入口（唯一真源，仓库根）
CLAUDE.md · GEMINI.md · .cursorrules · .github/copilot-instructions.md
                   薄指针 → AGENTS.md（兼容各 AI 工具的约定文件名）
surge/profiles/    lazy.conf · lazy.min.conf · routing.conf · routing.min.conf
egern/profiles/    同名 .yaml
clash/profiles/    同名 .yaml（静态交付形态，**由 override/*.js 生成**）
clash/override/    my_clash.js · my_clash_lazy.js（覆写脚本形态，挂订阅上用）
rules/             AI.list · apple_system.list · emby.list（唯一真源）
icons/             策略组图标，三内核共用
skill/
  reference/       8 篇：profiles/{surge,egern,clash}.md · dns.md · rulesets.md
                   · pitfalls.md · ops.md · gates.md
  scripts/<kern>/  审计 / 生成脚本
  tests/           门禁 + verify_all.py（唯一入口）
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
| **改了闸门却「改了没红」** | 注错**没落在判据的扫描面上** | **先怀疑注错，再怀疑判据**（见 `gates.md` 注错三铁律） |

**最重要的一条：本地全绿 ≠ 线上能跑。**

---

## 6 · 门禁

```bash
python skill/tests/verify_all.py          # 全跑，出汇总表
python skill/tests/verify_all.py -v       # 带详细输出
python skill/tests/verify_all.py --index  # 只列清单（现抓，勿手抄）
```

退出码：**0 = 全过 · 1 = 判负 · 2 = 环境不达标（先修环境，别读判据）· 3 = 未验证**。

⚠️ **3 不是绿**（汇总表显示 ⚠️ 且不计入 passed）。
分界线只有一条：**没读到远端真值 = 3；读到了但不过 = 1。**

判据要改？先读 `skill/reference/gates.md` 的「新增闸门自查清单」——
**一道从不判红的闸门比没有更糟**，它给虚假的安全感。

---

## 7 · 红线

- ❌ 不手工编辑 `rules/*.yaml`（生成物，改真源 `.list`）
- ❌ 不手工编辑 `clash/profiles/*.yaml`（生成物，改 `override/my_clash*.js`）
- ❌ 不让 `.min` 与完整版漂移（改一份必须同步另一份）
- ❌ 不为让门禁变绿而改判据 —— 改判据需要先说明「原判据错在哪」
- ❌ 不把「文档里写的数字」当权威 —— 组数/条数一律现抓（`verify_all --index` / 脚本输出）
- ⚠️ 结构性调整先补判据，不靠"再跑一遍"
