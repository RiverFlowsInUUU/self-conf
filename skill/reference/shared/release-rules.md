# 发版规矩

> 本仓的发版模型：一个更新日 = 一个 Release，tag = `vYYYY-MM-DD`。

⚠️ 本文是**规矩**，不是历史。历史请看 [`CHANGELOG.md`](CHANGELOG.md)。

## 1 · 版本号放哪

版本号写在 profile 的**头注第一行**，格式 `#! version=<产品线>_v<X.Y.Z>`：

```
#! version=routing_v4.0.5
```

| 内核 | 产品线 | 头注 |
|:--|:--|:--|
| Surge | 分流版 / 懒人版 | `#! version=routing_vX.Y.Z` / `#! version=lazy_vX.Y.Z` |
| Egern | 分流版 / 懒人版 | 同上（与 Surge 同号，强制对齐） |
| mihomo | 分流版 / 懒人版 | `#! version=routing_vX.Y.Z` / `#! version=lazy_vX.Y.Z` |

- Surge 与 Egern 同一产品线**必须同号**（跨内核对拍的前提，由 `check_min_pair.py` 的 X 判据守着）。
- mihomo 是**独立版本线**（配置由脚本生成，不是另两个内核的变体），从 `v1.0` 起。
- `.min` 版必须带**同一行**头注（对拍判据要求逐字节一致）。

## 2 · 什么时候升号

| 改动类型 | 升号 | 归档 | 进 Release |
|:--|:--:|:--:|:--:|
| 配置键变动（功能变化） | ✅ | ✅ | ✅ |
| 只改注释 / 文案 / 排版（配置键零变动，`.min` 逐字节不变） | ❌ | ❌ | ✅（并入当天那张 Release 的同一版本号条目）

规矩（2026-10-07 定）：

- **一天一版**：一天内改几次都只升一次号，当天后续改动沿用同号，不再归档、不再升号。
- 于是「版本号诞生日」与「内容诞生日」可以分离 —— 版本号是**功能**的刻度。
- Release 归组以**版本号首现日**为准，所以注释改动不会把旧版本号拖进新一天那张 Release。

## 3 · Release 怎么发

- **tag**：`vYYYY-MM-DD`（该日版本的诞生日期），指向 main。
- **资产**：当日各产品线最终版本的文件（完整版 + `.min`），固定名**带内核前缀**
  （`surge-lazy.conf` / `egern-routing.min.yaml` / `clash-lazy.min.yaml` 这样 ——
  Assets 面板自解释，不依赖「.conf=Surge / .yaml=Egern / clash-*=mihomo」的圈内约定）。
- **资产一律不带版本号** —— 这是铁律；版本号仅存在于正文条目与 profile 头注。
- **单边内核日如实注明**（如某日只有 mihomo 有内容），不硬凑。

### 标题与正文模板

标题 = 分类 emoji + 日期 + 当日主题。正文层级（**H1 更新日志**标题永远置顶）：

```markdown
🛡️ 2026-10-07 · 三内核并列与 DNS 防泄露统一      ← Release 标题

# 分流版 v4.0.5 / 懒人版 v2.0.5 更新日志

> 本次两版同步，变更一致。

## 共同变更

### 1. 关闭 IPv6
- Surge：`ipv6 = false`
- Egern：`ipv6: false`
- mihomo：顶层 `ipv6` + `dns.ipv6` 两处都关
- 影响：不再返回 AAAA 记录，双栈站点自动回落 IPv4；三内核行为对齐。

## 适用版本

- 分流版 v4.0.5
- 懒人版 v2.0.5
```

## 4 · 谁在守这些规矩

| 规矩 | 判据 |
|:--|:--|
| 头注版本格式合法、跨内核同号、`.min` 一致 | `skill/tests/check_min_pair.py`（V1 / V2 / X 判据） |
| 一天一版 | `skill/tests/check_min_pair.py`（V7，需完整 git 历史） |
| 现役版本与归档序列一致 | `skill/tests/check_min_pair.py`（V3–V6） |
| 徽章承诺的组数 / 规则数与实际一致 | `skill/tests/check_badges.py` |

⚠️ `check_releases.py`（远端 Release 断言 R1–R5）在本仓**暂不适用** ——
本仓尚发布过 Release。等首次发布后启用，判据如下：

- R1 tag 匹配 `^v\d{4}-\d{2}-\d{2}$` 且无重复
- R2 资产名属于固定名集合且不含版本号样式
- R3 标题 = emoji + 日期 + 主题
- R4 覆盖归档版本 + 现役版本，各自按诞生日期归组
- R5 Latest 必须是含现行版本的那张

## 5 · 发布流程（push 之后）

1. 确认当天门禁全绿：`python skill/tests/verify_all.py`
2. 补齐当日主题与条目
3. 发布 Release

⚠️ 改 mihomo 的版本号要改**脚本**（`clash/override/*.js` 不直接写版本头 ——
版本头由 `build_profiles.py` 保留并写入；`.min` 由生成器同步）。直接改 profile 会在重新生成时被覆盖。

## 6 · 已知取舍

- mihomo 侧不参与 Surge / Egern 的「跨内核同号」判据（独立版本线）。
- 归档文件（config_old）里的 URL 指向本仓，是为了自包含 —— 代价是归档不再忠实于
  发布当时的绝对地址。刻意如此（本仓是唯一真源）。
