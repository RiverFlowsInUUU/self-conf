# self-conf 维护手册

三内核（Surge / Egern / mihomo）配置模板。

原仓 `Self-Configuration` 与 `Clash` 保持不变；本仓用于验证
「三内核共用一份资产」是否真的成立。折腾不成也不影响它们。

---

## 1 · 布局：目录并列，不重命名

```
surge/  egern/  clash/      各内核一个顶层目录
icons/  rules/              共享资产
skill/tests/*.py            跨内核门禁（Surge / Egern 用）
skill/tests/clash/*.py      mihomo 专属门禁
```

**为什么并列而不是混在一起**：两仓的同名文件太多了
（`check_structure.py` / `check_min_pair.py` / `check_secrets.py`），
判据完全不同，混放会互相覆盖。按内核分目录 → **零重命名、零冲突**，
原脚本可以一字不改地搬过来跑。

实测：`skill/tests/check_structure.py`（Surge/Egern 版）搬到新仓后
**零改动直接通过**。

## 2 · 共享资产：单一真源

### rules/

`AI.list` / `apple_system.list` / `emby.list` 是**唯一真源**（`.list`，Surge 原生）。
mihomo 用的 `.yaml` 由脚本生成：

```bash
python skill/scripts/clash/build_rules.py           # 生成
python skill/scripts/clash/build_rules.py --check   # CI 用：过期即判负
```

改内容只改 `.list`，重跑脚本。物理上不可能漂移。

> 整合前两仓各存一份（emby 4 / apple_system 18 / AI 272 条，逐条相同），
> 双份维护 —— 这是合并最直接的收益。

### icons/

38 个图标，三内核引用同一份。整合时 34 个同名文件**内容字节完全一致**，零冲突。

## 3 · 分歧：内核机制决定，不要去"对齐"

| 项 | Surge / Egern | mihomo |
|:--|:--|:--|
| 地区组 | `smart` + filter | `url-test` + filter |
| 订阅源 | `Airport` external 组 | proxy-provider |
| 倍率分档 | `policy-priority` 权重 | 模板靠 `filter` 三档；**脚本做不到** |
| 规则集格式 | `.list` | `.mrs` / `.yaml` |

⚠️ 倍率分档这条最容易误判为漂移：
mihomo 模板能用 `filter` 在运行时分档，脚本在订阅加载时执行一次、
看不到 provider 节点名，故脚本侧是单组 fallback。
`check_script_sync.py` 把它列为**已知差异**，打印提醒但不判负。

## 4 · 已消弭的冲突（整合时实际遇到）

| 冲突 | 处理 |
|:-----|:-----|
| `check_structure.py` 等 3 个同名文件 | 按内核分目录 |
| Surge/Egern 的路径相对仓库根，搬到子目录会失效 | 保留原位（不进子目录） |
| mihomo 的 `198.18.0.1`（fake-ip 段）被 Surge 侧 secrets 扫描判为真实 IP | 给 `DOC_NETS` 加 `198.18.`（RFC 6815 保留段） |

第 3 条值得记：那是 mihomo 的**合法保留段**，但 Surge / Egern 侧不认识。
不加白名单就会被误判 —— 整合必须处理这类"各内核的常识不同"。

## 5 · 改配置的顺序

```bash
# Surge / Egern 侧
python skill/tests/verify_all.py

# mihomo 侧
python skill/tests/clash/check_structure.py
python skill/tests/clash/check_min_pair.py
python skill/tests/clash/check_script_sync.py
python skill/scripts/clash/build_rules.py --check   # 规则集生成物是否过期

# 慢，按需
python skill/tests/clash/check_remote_urls.py
```

## 6 · 门禁清册

**跨内核**（`skill/tests/`）
`verify_all.py`（总入口）· `check_structure` · `check_min_pair` ·
`check_secrets` · `check_badges` · `check_links` · `check_portability` ·
`check_region_filters` · `check_releases` · `make_min` · `sync_docs`

**mihomo 专属**（`skill/tests/clash/`）
`check_structure` · `check_min_pair` · `check_script_sync` ·
`check_remote_urls` · `check_secrets`

## 7 · 踩过的坑（CI 暴露，本地全绿也没用）

| 现象 | 根因 | 处理 |
|:-----|:-----|:-----|
| Linux CI 上 clash 门禁报「缺文件」，本地全过 | `_default_root()` 基于 `__file__` 向上推算，在 Actions 的调用方式下算错目录 | 改为 CWD 优先 + 逐级向上探测，找到同时含 `profiles/` 与 `override/` 的目录 |
| V7「一天一版」判负：一天升了 21 个版本 | 复制文件时 mtime 丢失，历史归档全变成复制当天 | `cp -p` 保留 mtime；另加 `SKIP_V7` 开关应对"本就不继承 git 历史" |
| `198.18.0.1` 被判为真实 IP | 那是 mihomo 的 fake-ip 段（RFC 6815），Surge/Egern 侧不认识 | 加入 `DOC_NETS` 白名单 |
| CRLF 判负 | Clash 侧 3 个文件是 CRLF | 转 LF + 搬入 `.gitattributes` |

第一条最值得记：**本地全绿 ≠ 线上能跑**。路径探测这类环境相关的东西，
一定要让 CI 跑一遍才算数。

## 8 · 红线

- ❌ 不改 `Self-Configuration` 与 `Clash` 两个原仓
- ❌ 不手工编辑 `rules/*.yaml`（生成物，改真源 `.list`）
- ⚠️ 结构性调整需先补判据，不靠"再跑一遍"
