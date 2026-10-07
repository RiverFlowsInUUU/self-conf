<div align="center">

<img src="https://raw.githubusercontent.com/RiverFlowsInUUU/self-conf/main/icons/Surge.png" height="56" alt="Surge">&nbsp;&nbsp;<img src="https://raw.githubusercontent.com/RiverFlowsInUUU/self-conf/main/icons/Egern.png" height="56" alt="Egern">&nbsp;&nbsp;<img src="https://raw.githubusercontent.com/RiverFlowsInUUU/self-conf/main/icons/Proxy.png" height="56" alt="mihomo">

# 三内核配置模板

殊途同归 · 久用如一

[![Surge](https://img.shields.io/badge/Surge-iOS%20%7C%20macOS-1f6feb?style=flat-square)](#-取用)
[![Egern](https://img.shields.io/badge/Egern-iOS%20%7C%20macOS-0969da?style=flat-square)](#-取用)
[![mihomo](https://img.shields.io/badge/mihomo-Clash%20Meta-8250df?style=flat-square)](#-取用)
[![Groups](https://img.shields.io/badge/Groups-23%20%7C%2023%20%7C%2025-8250df?style=flat-square)](#-井然有序)
[![Rules](https://img.shields.io/badge/Rules-26%20%7C%2026%20%7C%2027-dc3545?style=flat-square)](#-井然有序)
[![DNS](https://img.shields.io/badge/DNS-Zero%20Leak-2ea043?style=flat-square)](#-隐私至上--无-dns-泄露)
[![License](https://img.shields.io/badge/License-MIT-dfb317?style=flat-square)](LICENSE)
[![CI](https://github.com/RiverFlowsInUUU/self-conf/actions/workflows/ci.yml/badge.svg)](https://github.com/RiverFlowsInUUU/self-conf/actions/workflows/ci.yml)

</div>

> 🤖 **AI agent 请从这里开始** → [`skill/SKILL.md`](skill/SKILL.md)：动手前的顺序，和三内核各自的判据。

## 📥 取用

| <div align="center">内核</div> | 🪶 懒人版 · 至简 · 省心 | 🧭 分流版 · 可控 · 随心 |
|:--|:--|:--|
| <img src="https://raw.githubusercontent.com/RiverFlowsInUUU/self-conf/main/icons/Surge-Icon.png" height="20" alt=""> **Surge** | [`lazy.min.conf`](surge/profiles/lazy.min.conf) | [`routing.min.conf`](surge/profiles/routing.min.conf) |
| <img src="https://raw.githubusercontent.com/RiverFlowsInUUU/self-conf/main/icons/Egern-Icon.png" height="20" alt=""> **Egern** | [`lazy.min.yaml`](egern/profiles/lazy.min.yaml) | [`routing.min.yaml`](egern/profiles/routing.min.yaml) |
| **mihomo**<br><sub>静态</sub> | [`lazy.min.yaml`](clash/profiles/lazy.min.yaml) | [`routing.min.yaml`](clash/profiles/routing.min.yaml) |
| **mihomo**<br><sub>覆写脚本</sub> | [`my_clash_lazy.js`](clash/override/my_clash_lazy.js) | [`my_clash.js`](clash/override/my_clash.js) |

mihomo 多一种形态：覆写脚本可挂到任意订阅上，输出与静态文件逐位一致。

---

## 🧭 井然有序

🗂️ 各司其职，各安其序，无隙可乘。

| <div align="center">组</div> | 🪶 懒人版 | 🧭 分流版 |
|:---|:---:|:---:|
| 🚀 `Proxy` | ✅ | ✅ |
| ⚡ `Smart` | - | ✅ |
| 🤖 `ChatGPT` · `Gemini` · `Claude` · `AI` | 仅 `AI` | ✅ |
| ▶️ `YouTube` · 🎬 `Emby` · 🔎 `Google`<br>✈️ `Telegram` · 🐦 `Twitter` · 🪟 `Microsoft`<br>🎶 `YouTube Music` · 🎵 `Spotify` | - | ✅ |
| 🍎 `Apple Update` | - | ✅ |
| 🛑 `AD` | ✅ | ✅ |
| 🇭🇰 `Hong Kong` · 🇨🇳 `Taiwan` · 🇯🇵 `Japan`<br>🇸🇬 `Singapore` · 🇺🇸 `United States`<br>🇦🇶 `Other Regions` | - | ✅ |

分流版：**Surge / Egern 23 组 · 26 条规则**，**mihomo 25 组 · 27 条规则**（差异在 mihomo 另有 `Smart` 的三档子组，见下）。

---

## 🔗 共享与分歧

三个内核各占一个顶层目录，互不干扰：

```
surge/    egern/    clash/       各内核配置（clash 另有 override/ 覆写脚本）
icons/    rules/                 共享资产
skill/                           手册 · 判据 · 文档
```

**共享的是内容，不是文件** —— `icons/` 三内核引用同一份（38 个）；
`rules/` 以 `.list` 为唯一真源，mihomo 用的 `.yaml` 由 `build_rules.py` 生成。

**分歧由内核机制决定**，不是失误：

| | Surge | Egern | mihomo |
|:--|:--|:--|:--|
| 订阅源载体 | `Airport` external 组 | `Airport` external 组 | `proxy-providers`（provider） |
| 地区组择优 | `smart` + filter | `smart` + filter | `url-test` + filter |
| 倍率机制 | `policy-priority` 权重 | `priorities` | 无权重键，用 `fallback` + `filter` 分档 |
| 规则集格式 | `.list` / `.txt` | `.list` / `.txt` | `.mrs`（+ 少量 `.yaml`） |
| `no-resolve` 落点 | 规则行尾 | 仅 `geoip`/`ip_cidr`/`asn` 类 | `RULE-SET` 行尾 |
| 独有机制 | `pre-matching` / `extended-matching` | `flatten: true` | `tun` 段 / 覆写脚本 |

哪些能互相照搬、哪些照搬就是错的，见
[`cross-kernel-diff.md`](skill/reference/shared/cross-kernel-diff.md)。

mihomo 有一个独有设计：`Smart` 是 fallback，按**倍率**分三档回落
（`Low Mult.` → `Auto` → `High Mult.`）。

---

## 🌐 隐私至上 · 无 DNS 泄露

| | <div align="center"><img src="https://raw.githubusercontent.com/RiverFlowsInUUU/self-conf/main/icons/Surge-Icon.png" height="22" alt=""> Surge</div> | <div align="center"><img src="https://raw.githubusercontent.com/RiverFlowsInUUU/self-conf/main/icons/Egern-Icon.png" height="22" alt=""> Egern</div> | <div align="center"><img src="https://raw.githubusercontent.com/RiverFlowsInUUU/self-conf/main/icons/Proxy.png" height="22" alt=""> mihomo</div> |
|:--|:--|:--|:--|
| 🚫 旁路设备 | `hijack-dns` 接管明文 `:53`（六个知名解析器） | `hijack_dns` 接管明文 `:53`（全量） | `tun.dns-hijack: any:53` + `strict-route`（锁死绕行） |
| 🔐 加密通道 | 主解析走 DoH，主机名端点经裸 IP 受控引导 | 主解析走 DoH/DoT，四条端点全是 IP 字面量 | 主解析走 DoH，端点一律写 **IP 字面量**（`1.1.1.1` / `8.8.8.8`） |
| 🛡️ 明文回退 | `dns-server` 全裸 IP，绝不写 `system` | `forward` 兜底只指加密组，绝不落明文 | `default-nameserver` 裸 IP（仅引导）+ `proxy-server-nameserver` 专用通道 |
| 🧭 规则克制 | IP 类规则一律 `no-resolve`；零 IP 的规则集不写 | IP 类规则一律 `no_resolve`；该键对 `rule_set` 不生效 | IP 类规则一律 `no-resolve`；纯域名规则集不写 |
| ✂️ 远端解析 | 代理域名交节点解析，本地不留答案 | 代理域名交节点解析（`proxy_nameservers` 专用通道） | `enhanced-mode: fake-ip` 只回假 IP，真实解析在落地侧 |
| 🔎 IPv6 | `ipv6 = false` | `ipv6: false` | 顶层 `ipv6` + `dns.ipv6` **两处**都要 false |
| 🛑 广告拦截 | `pre-matching REJECT` | `forward` → `reject` | DNS 层双条件（`rcode://success` + `fake-ip-filter` 成对） |
| 📦 数据库依赖 | 依赖内置系统集 | 引用共享 `.list` | **零 dat 依赖**，用 `.mrs` 远程集 |
| 📋 自检读数 | 5 个审计脚本 · 19 断言 | 10 个审计脚本 · 24 断言 | `check_clash_dns` 14 项 + `check_structure` 8 项 |

三内核共通的底线：**解析器全加密 · 明文入口收口 · 代理域名不给真答案 ·
IPv6 显式关闭 · 广告拦截前移**。每一条都有判据守着（21 道门禁 + CI）。

---

## 📖 按需查阅

操作手册、逐键语义与审计判据都在 [`skill/SKILL.md`](skill/SKILL.md)。

---

<div align="center">

🐈 让 DNS 无处可漏 · MIT License

</div>
