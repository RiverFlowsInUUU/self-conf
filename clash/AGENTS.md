# clash/ · mihomo 侧

**本目录是唯一有生成链的一侧。** 根 [`AGENTS.md`](../AGENTS.md) 的规则仍然适用；
这里只写 clash/ 特有的、agent 推不出来的东西。

---

## 两个生成链（**按这个顺序改**）

```
rules/*.list          ──build_rules.py──▶    rules/*.yaml
clash/override/*.js   ──build_profiles.py──▶  clash/profiles/*.yaml + *.min.yaml
```

| 你想改 | 改这个 | 然后跑 |
|:--|:--|:--|
| mihomo 的分组 / 规则 / DNS | `clash/override/my_clash.js`（分流版）或 `my_clash_lazy.js`（懒人版） | `python self-conf-skills/run/clash/build_profiles.py` |
| 自托管规则集的内容 | `rules/*.list` | `python self-conf-skills/run/clash/build_rules.py` |

⚠️ **直接改 `clash/profiles/*.yaml` 会在下次生成时被覆盖** —— 这是本侧最高频的错误。

**两形态必须逐位一致**：`my_clash.js` 生成的组/规则数，与 `clash/profiles/routing.yaml`
里的静态描述必须对得上。`check_script_sync.py` 判这条，
`check_header_numbers.py` 判「脚本头注里写的数字」是否与实际输出一致 ——
**改了组数/规则数，头注里的数字要一起改**。

---

## 本侧专属判据

```bash
python self-conf-skills/gates/clash/check_structure.py        # 结构完整性
python self-conf-skills/gates/clash/check_script_sync.py      # 脚本 ↔ 静态 profile 对拍
python self-conf-skills/gates/clash/check_version_header.py   # 头注版本（三内核同号）
python self-conf-skills/gates/clash/check_remote_urls.py      # 远程规则集可达（需联网，慢）
python self-conf-skills/gates/clash/check_ruleset_doc_sync.py # 配置 URL ↔ 文档表
python self-conf-skills/gates/clash/check_clash_dns.py clash/profiles/routing.yaml clash/profiles/lazy.yaml
```

（`verify_all.py` 会跑其中大部分；单独跑这几个是**改完只想快速自查**时用。）

---

## 一个已知的刻意差异

`Smart` 组的**倍率三档**（Low Mult. / Auto / High Mult.）**只存在于静态模板**，
脚本侧做不到 —— 因为覆写脚本在**订阅加载时执行一次**，看不到 provider 里的节点名。

⇒ `check_script_sync.py` 把这条列为**已知差异**，打印提醒但**不判负**。
**不要去"修"它**，也不要把脚本改成"对齐"。
