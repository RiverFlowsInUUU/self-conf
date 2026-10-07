<div align="center">

<img src="https://raw.githubusercontent.com/RiverFlowsInUUU/self-conf/main/icons/Surge.png" height="56" alt="Surge">&nbsp;&nbsp;<img src="https://raw.githubusercontent.com/RiverFlowsInUUU/self-conf/main/icons/Egern.png" height="56" alt="Egern">&nbsp;&nbsp;<img src="https://raw.githubusercontent.com/RiverFlowsInUUU/self-conf/main/icons/Proxy.png" height="56" alt="mihomo">

# self-conf

三内核配置模板 · 殊途同归 · 久用如一

[![Surge](https://img.shields.io/badge/Surge-iOS%20%7C%20macOS-1f6feb?style=flat-square)](#-取用)
[![Egern](https://img.shields.io/badge/Egern-iOS%20%7C%20macOS-0969da?style=flat-square)](#-取用)
[![mihomo](https://img.shields.io/badge/mihomo-Clash%20Meta-8250df?style=flat-square)](#-取用)
[![Kernels](https://img.shields.io/badge/Kernels-3-dc3545?style=flat-square)](#-内核并列)
[![DNS](https://img.shields.io/badge/DNS-Zero%20Leak-2ea043?style=flat-square)](#-共享与分歧)
[![License](https://img.shields.io/badge/License-MIT-dfb317?style=flat-square)](LICENSE)

</div>

> ⚗️ **实验性整合项目** —— 把 `Self-Configuration`（Surge / Egern）与 `Clash`（mihomo）
> 两个仓合并到一处，验证「三内核共用一份资产」是否真的成立。
> **两个原仓保持不变**，本仓随便折腾；折腾不成也不影响它们。

> 🤖 **AI agent 请从这里开始** → [`skill/SKILL.md`](skill/SKILL.md)

## 📥 取用

| <div align="center">内核</div> | 🪶 懒人版 · 至简 | 🧭 分流版 · 可控 |
|:--|:--|:--|
| **Surge** | [`surge/profiles/lazy.min.conf`](surge/profiles/lazy.min.conf) | [`surge/profiles/routing.min.conf`](surge/profiles/routing.min.conf) |
| **Egern** | [`egern/profiles/lazy.min.yaml`](egern/profiles/lazy.min.yaml) | [`egern/profiles/routing.min.yaml`](egern/profiles/routing.min.yaml) |
| **mihomo**<br><sub>静态</sub> | [`clash/profiles/lazy.min.yaml`](clash/profiles/lazy.min.yaml) | [`clash/profiles/routing.min.yaml`](clash/profiles/routing.min.yaml) |
| **mihomo**<br><sub>覆写脚本</sub> | [`clash/override/my_clash_lazy.js`](clash/override/my_clash_lazy.js) | [`clash/override/my_clash.js`](clash/override/my_clash.js) |

mihomo 多一种形态：覆写脚本可挂到任意订阅上，输出与静态文件逐位一致。

## 🧭 内核并列

三个内核各占一个顶层目录，互不干扰 —— 这是整合能成立的前提。

```
self-conf/
  surge/      Surge 配置（.conf）
  egern/      Egern 配置（.yaml）
  clash/      mihomo 配置 + 覆写脚本
  icons/      共享图标（三内核同源）
  rules/      共享规则集（.list 为真源）
  skill/      手册 + 脚本 + 门禁（按内核分目录）
```

## 🔗 共享与分歧

### 共享（合并的直接收益）

| 资产 | 说明 |
|:-----|:-----|
| `icons/` | 38 个图标，三内核引用同一份。整合时 34 个同名文件**内容完全一致**，零冲突 |
| `rules/` | `AI.list` / `apple_system.list` / `emby.list` 为**唯一真源**；<br>mihomo 用的 `.yaml` 由 `build_rules.py` 生成 |

`rules/` 是最典型的收益：整合前两个仓各存一份内容相同、格式不同的规则集
（emby 4 / apple_system 18 / AI 272 条，逐条相同），改一处忘一处就漂移。
现在单一真源，物理上不可能漂移。

### 分歧（内核机制决定，不是失误）

| 项 | Surge / Egern | mihomo |
|:--|:--|:--|
| 地区组 | `smart` + filter | `url-test` + filter |
| 订阅源 | `Airport` external 组 | proxy-provider |
| 倍率分档 | `policy-priority` 权重 | 模板靠 `filter` 分三档；脚本做不到 |
| 规则集格式 | `.list` | `.mrs` / `.yaml` |
| IPv6 | 显式关闭 | 显式关闭（一致） |

## 🌐 隐私至上 · 无 DNS 泄露

三个内核共同的底线：

- **解析器全加密** —— DoH / DoT，无一条明文递归
- **明文入口收口** —— `hijack-dns` / `dns-hijack` 接管 `:53`
- **代理域名不给真答案** —— fake-ip，真实解析在落地侧
- **IPv6 显式关闭** —— 杜绝真实 IPv6 绕过 TUN
- **广告拦截前移到 DNS 层** —— 两个必要条件缺一即失效

## 🧪 门禁

| 范围 | 位置 |
|:-----|:-----|
| 跨内核 | `skill/tests/*.py`（含 `verify_all.py` 总入口） |
| mihomo 专属 | `skill/tests/clash/*.py` |

同名文件按目录分开（如 `check_structure.py` 在两个目录下各一份，判据不同），
互不覆盖。

## 📖 按需查阅

操作手册与审计判据在 [`skill/SKILL.md`](skill/SKILL.md)。

---

<div align="center">

🐈 让 DNS 无处可漏 · MIT License

</div>
