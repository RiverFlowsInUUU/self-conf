<div align="center">

<img src="https://raw.githubusercontent.com/RiverFlowsInUUU/self-conf/main/icons/Surge.png" height="56" alt="Surge">&nbsp;&nbsp;&nbsp;&nbsp;<img src="https://raw.githubusercontent.com/RiverFlowsInUUU/self-conf/main/icons/Brand-Cross.png" height="56" alt="">&nbsp;&nbsp;&nbsp;<img src="https://raw.githubusercontent.com/RiverFlowsInUUU/self-conf/main/icons/Egern.png" height="56" alt="Egern">&nbsp;&nbsp;&nbsp;&nbsp;<img src="https://raw.githubusercontent.com/RiverFlowsInUUU/self-conf/main/icons/Brand-Cross.png" height="56" alt="">&nbsp;&nbsp;&nbsp;<img src="https://raw.githubusercontent.com/RiverFlowsInUUU/self-conf/main/icons/mihomo.png" height="56" alt="mihomo">

# Surge · Egern · mihomo 配置模板

殊途同归 · 久用如一

[![Surge](https://img.shields.io/badge/Surge-iOS%20%7C%20macOS-1f6feb?style=flat-square)](#-三全其美--皆合心意)
[![Egern](https://img.shields.io/badge/Egern-iOS%20%7C%20macOS-0969da?style=flat-square)](#-三全其美--皆合心意)
[![mihomo](https://img.shields.io/badge/mihomo-Clash%20Meta-8250df?style=flat-square)](#-三全其美--皆合心意)
[![Groups](https://img.shields.io/badge/Groups-23%20%7C%2023%20%7C%2025-8250df?style=flat-square)](#-井然有序)
[![Rules](https://img.shields.io/badge/Rules-26%20%7C%2026%20%7C%2027-dc3545?style=flat-square)](#-井然有序)
[![DNS](https://img.shields.io/badge/DNS-Zero%20Leak-2ea043?style=flat-square)](#-隐私至上--无-dns-泄露)
[![License](https://img.shields.io/badge/License-MIT-dfb317?style=flat-square)](LICENSE)
[![CI](https://github.com/RiverFlowsInUUU/self-conf/actions/workflows/ci.yml/badge.svg)](https://github.com/RiverFlowsInUUU/self-conf/actions/workflows/ci.yml)

</div>

> 🤖 **AI agent 请从这里开始** → [`AGENTS.md`](AGENTS.md)：动手前的顺序，和三内核各自的判据。

一套配置，覆盖 Surge、Egern、mihomo（Clash Meta）三款内核。
它们语法不同、机制不同，但在这里**组结构一致、规则次序一致、防泄露底线一致** ——
你换客户端不用重新学一遍。

## 📥 三全其美 · 皆合心意

| <div align="center">内核</div> | 🪶 懒人版 · 至简 · 省心 | 🧭 分流版 · 可控 · 随心 |
|:--|:--|:--|
| <img src="https://raw.githubusercontent.com/RiverFlowsInUUU/self-conf/main/icons/Surge-Icon.png" height="20" alt=""> **Surge** | [`surge-lazy.min.conf`](https://raw.githubusercontent.com/RiverFlowsInUUU/self-conf/main/surge/profiles/lazy.min.conf) | [`surge-routing.min.conf`](https://raw.githubusercontent.com/RiverFlowsInUUU/self-conf/main/surge/profiles/routing.min.conf) |
| <img src="https://raw.githubusercontent.com/RiverFlowsInUUU/self-conf/main/icons/Egern-Icon.png" height="20" alt=""> **Egern** | [`egern-lazy.min.yaml`](https://raw.githubusercontent.com/RiverFlowsInUUU/self-conf/main/egern/profiles/lazy.min.yaml) | [`egern-routing.min.yaml`](https://raw.githubusercontent.com/RiverFlowsInUUU/self-conf/main/egern/profiles/routing.min.yaml) |
| <img src="https://raw.githubusercontent.com/RiverFlowsInUUU/self-conf/main/icons/mihomo-Icon.png" height="20" alt=""> **mihomo** | [`clash-lazy.min.yaml`](https://raw.githubusercontent.com/RiverFlowsInUUU/self-conf/main/clash/profiles/lazy.min.yaml) | [`clash-routing.min.yaml`](https://raw.githubusercontent.com/RiverFlowsInUUU/self-conf/main/clash/profiles/routing.min.yaml) |
| <img src="https://raw.githubusercontent.com/RiverFlowsInUUU/self-conf/main/icons/mihomo-Icon.png" height="20" alt=""> **mihomo**<br><sub>覆写脚本</sub> | [`my_clash_lazy.js`](https://raw.githubusercontent.com/RiverFlowsInUUU/self-conf/main/clash/override/my_clash_lazy.js) | [`my_clash.js`](https://raw.githubusercontent.com/RiverFlowsInUUU/self-conf/main/clash/override/my_clash.js) |

- **懒人版**：一个总出口，只做防泄露 + 广告拦截 + AI 分流。想省心就用它。
- **分流版**：按应用 + 按地区细分，每个应用可单独指定走哪个地区。想可控就用它。
- **mihomo 覆写脚本**：不用下载配置 —— 把它挂到你自己的订阅上，订阅会被改造成同样的结构。

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

分流版：**Surge / Egern 23 组 · 26 条规则**，**mihomo 25 组 · 27 条规则**。

## 🌐 隐私至上 · 无 DNS 泄露

| | <div align="center"><img src="https://raw.githubusercontent.com/RiverFlowsInUUU/self-conf/main/icons/Surge-Icon.png" height="22" alt=""> Surge</div> | <div align="center"><img src="https://raw.githubusercontent.com/RiverFlowsInUUU/self-conf/main/icons/Egern-Icon.png" height="22" alt=""> Egern</div> | <div align="center"><img src="https://raw.githubusercontent.com/RiverFlowsInUUU/self-conf/main/icons/mihomo-Icon.png" height="22" alt=""> mihomo</div> |
|:--|:--|:--|:--|
| 🚫 旁路设备 | 列举收口 | 全量收口 | 交客户端 TUN |
| 🔐 加密通道 | DoH · 端点裸 IP | DoH / DoT · 端点全 IP | DoH · 端点全 IP |
| 🛡️ 明文回退 | 全裸 IP · 无 `system` | 只指加密组 | 引导与代理分道 |
| 🧭 规则克制 | 按需 `no-resolve` | 按需 `no_resolve` | 按需 `no-resolve` |
| ✂️ 远端解析 | 交节点解析 | 交节点解析 | `fake-ip` · 落地解析 |
| 🔎 IPv6 | 关闭 | 关闭 | 两处关闭 |
| 🛑 广告拦截 | 匹配前拦 | 转拒绝 | 解析层拦 |
| 📦 数据库依赖 | 内置 | 共享清单 | 零 dat 依赖 |

三内核机制不同、写法不同，但**底线一致**。逐键对照与推导见 [`dns.md`](self-conf-skills/references/dns.md)。

每一条都有判据守着 —— 全套闸门 + CI，不是文档里的一句话。

## 📖 按需查阅

操作手册、逐键语义、审计判据与发版规矩都在 [`AGENTS.md`](AGENTS.md)。

---

<div align="center">

🐈 让 DNS 无处可漏 · MIT License

</div>
