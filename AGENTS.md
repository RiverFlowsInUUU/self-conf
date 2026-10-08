# self-conf · Agent 指南

Surge / Egern / mihomo（Clash Meta）**三内核代理配置模板**。
人类请看 [`README.md`](./README.md)；公开仓安全纪律见 [`SECURITY.md`](./SECURITY.md)。

> 本文件是各 AI 工具入口的**唯一真源**。`CLAUDE.md` · `GEMINI.md` · `.cursorrules` ·
> `.github/copilot-instructions.md` 是薄指针，内容以本文件为准。
> ⚠️ `clash/` 有独立的生成链，**在那里工作时先读 [`clash/AGENTS.md`](./clash/AGENTS.md)**（就近生效）。

---

## 命令

```bash
python tools/gates/verify_all.py          # 门禁唯一入口（与 CI 同源）。绿了才算改完
python tools/gates/verify_all.py -v       # 带详细输出
python tools/gates/verify_all.py --index  # 列闸门清单（现抓，勿手抄）

python tools/run/make_min.py --apply              # 改完完整版后同步 .min
python tools/run/clash/build_profiles.py          # 改完 my_clash*.js 后重生成 mihomo profile
python tools/run/clash/build_rules.py             # 改完 rules/*.list 后重生成 .yaml
python tools/run/repo_state.py                    # 一屏现状：版本 / Release / CI
```

退出码：**0 = 全过 · 1 = 判负 · 2 = 环境不达标（先修环境，别读判据）· 3 = 未验证**。
⚠️ **3 不是绿**（显示 ⚠️，不计入 passed）。**没读到远端真值 = 3；读到了但不过 = 1。**

---

## 边界

**✅ 总是**
- 改完跑 `verify_all.py` —— **"我改对了"不算做完，门禁绿了才算**
- 改完整版后同步 `.min`（两份只差注释，内容必须逐字相同）
- 每条配置键的权威解释是**它自己在 profile 里的注释**（写满了理由）；改键前先读它

**⚠️ 先问**
- 改判据 / 加闸门（先说明「原判据错在哪」，再读 `tools/reference/gates.md` 的自查清单）
- 结构性调整（先补判据，不靠"再跑一遍"）

**🚫 从不**
- 手工编辑生成物：`rules/*.yaml`（改 `rules/*.list`）、
  `clash/profiles/*.yaml`（改 `clash/override/my_clash*.js`）、`*.min.*`（跑 `make_min.py --apply`）
- 为了「让门禁变绿」而改判据
- 把文档里写的数字当权威（组数/条数一律现抓）
- **把三内核「对齐」** —— 机制不同，看起来的不一致常是刻意的

---

## 改动去哪（**推不出来的部分**）

| 改什么 | 改哪个文件 | ⚠️ 易错 |
|:--|:--|:--|
| Surge 配置 | `surge/profiles/*.conf` | **不是**生成物，直接改 |
| Egern 配置 | `egern/profiles/*.yaml` | **不是**生成物，直接改 |
| mihomo 配置 | `clash/override/my_clash*.js` | ⚠️ **是**生成物 ⇒ 改 JS 再 build |
| 规则集内容 | `rules/*.list` | ⚠️ `.yaml` 是生成的 |

**三内核机制差异**（看起来不一致 ≠ 漂移）：地区组 Surge/Egern 用 `smart`、mihomo 用
`url-test`；订阅源前者是 external 组、后者是 `proxy-provider`；倍率分档 mihomo 的
**脚本做不到**（生成期看不到节点名）。`check_script_sync.py` 把这类列为**已知差异**，
打印提醒但不判负 —— **不要去"修"它**。

---

## 文档怎么读（**不要整篇读**）

`tools/reference/` 8 篇，每篇 45~135 KB。**整篇读是浪费** —— 它们都有完整标题层级，
用 `grep` 定位到节，通常只需读 2~5 KB：

```bash
grep -n "include-all" tools/reference/profiles/clash.md   # 拿行号与节标题，只读那一节
```

---

## 一件事：本地全绿 ≠ 线上能跑

改动涉及**路径 / 编码 / 联网**时，**等 CI 结果**，别只看本地 —— 这三类历史上都栽过
（Linux 上路径探测算错目录；中文 Windows 管道 GBK 崩成退出码 1，而 1 恰是判负码）。

同理：闸门「跑了没红」时，**先怀疑自己的注错没落在判据的扫描面上**，再怀疑判据失灵。
