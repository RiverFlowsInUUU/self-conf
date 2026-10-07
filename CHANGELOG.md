# 更新日志

本文件按 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/) 规范编写。

---

## 2026-10-07

### 新增

- 🧭 **三内核并列** —— `surge/`（Surge）、`egern/`（Egern）、`clash/`（mihomo）各占一个顶层目录，互不干扰。
  clash 侧另有 `clash/override/`，是本仓独有的**覆写脚本**形态（挂到任意订阅上，输出与静态 profile 逐位一致）。
- 🔗 **共享资产单源化**
  - `icons/` 三内核引用同一份（38 个）。
  - `rules/` 以 `.list` 为唯一真源，mihomo 用的 `.yaml` 由 `skill/scripts/clash/build_rules.py` 生成 —— 单一真源，不会漂移。
- 🛡️ **clash 侧补齐四个审计器**（此前为零，是最大的对标缺口）
  - `check_clash_dns.py`：DNS 防泄露审计，14 项判据（与 `check_surge_dns.py` / `check_egern_dns.py` 同职责）。
  - `audit_region_filters.py`：地区组判别力审计，7 条判据。
  - `audit_routing_coverage.py`：分流覆盖审计，含**联网档**（离线档为默认，CI 友好）。
  - `audit_ruleset_content.py`：规则集内容审计（behavior 与实际内容是否相符、裸 IP 条目）。
- ✅ **真机验证脚本** `skill/tests/clash/check_real_kernel.py`
  用真实 mihomo 二进制跑 `-t -f`；找不到二进制退 2（未验证，不是通过）。
  实测 mihomo Meta alpha-9f053c4：四份静态配置 + 脚本输出形态全部 `test is successful`。
- 📝 **clash 侧文档 11 篇**，规格对齐另两个内核的 8 篇。
- 📚 **共享层 8 篇全部扩到三内核**：`cross-kernel-diff.md`（三内核移植边界）、`ops.md`、`dns-basics.md`、
  `rulesets.md`、`hardening-checklist.md`、`no-resolve-pairing.md`、`boundaries.md`、`troubleshoot-faq.md`。

### 修复

- 🧱 `routing.yaml` 被**纵向堆叠 7 份**（3294 行）—— 重生成时用了追加模式。已修复并加自检。
- 📡 两份静态 profile 的 `proxy-providers` **整段丢失** —— 用户导入后无从填订阅。已改为从静态版继承。
- ⚙️ `Smart` **未接上三档** —— 声明了 `Low Mult./Auto/High Mult.` 但 `Smart.proxies` 仍是 `["DIRECT"]`，
  三档形同虚设（声明了却没连，比不声明更隐蔽）。
- ✈️ **机场城市名/三字码无组可归** —— 「东京 01」「NRT 03」「LAX 02」「硅谷 03」六地区组全不匹配：
  城市名只存在于 `Other Regions` 的排除块，而日本/美国组的正向 filter 只有国家简称。按姊妹仓写法补全。
- 🔗 远程规则集死链静默降级 —— Jinx 上游把 `*-white-guard.*` 改名 `*-direct.*`，懒人版一直挂着 404。
- 🛑 两版 `AD` 组口径不一致（分流版 `REJECT,DIRECT` / 懒人版单成员 `REJECT`）—— 已统一。
- 🔒 IPv6 未显式关闭（顶层 + `dns.ipv6` 两处都要 false）；`nameserver` 写主机名导致明文引导查询；
  `nameserver-policy` 用了无依据的逗号多值；`geoip-*` 缺 `no-resolve`。均已取得官方/源码依据后修正。
- 🔢 头注里的规模数字过期（`my_clash.js` 写 20 组/20 集/26 条，实际 22/25/27）。

### 变更

- 🧪 判据从 17 道扩到 **21 道**，CI 全绿。
- 📖 文档去除「实验性 / 原仓 / 两仓」等来源表述 —— 本仓是三内核并列的新仓库，不是 1+1=2。
- 🏷️ 仓库描述改为「Surge · Egern · mihomo 三内核配置模板 · 殊途同归 · 久用如一」。

### 已知取舍（不是缺陷）

- `Jinx-Ads` 等 `classical` 规则集只生效域名类规则（真机 warning 确认）。
- `tun.dns-hijack: any:53` 按官方语义只收 UDP:53（收 TCP 需另加 `tcp://any:53`）。
- 覆盖审计联网档对 `.mrs` 是退化为文本版判的，未逆向二进制正文。
- 地区组正则用 Python 近似（mihomo 用 Go regexp2，支持 `(?i)` 在任意位置）。
