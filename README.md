# sim2patent —— 仿真 agent → 专利 agent 的桥接 agent

把 **仿真 agent** 的产物(工程 CAE/CFD 数值结果,CSV/JSON)自动转换为
**专利 agent** 需要的结构化输入(技术交底书 + 创新点清单 + 数据依据),
并落盘成一份可交接的 JSON + Markdown 手稿。

```
仿真 agent 输出(CSV/JSON)
        │  parsers 解析成 SimulationResult
        ▼
数据摘要 build_data_digest(行数封顶,防超长)
        │  analyze 阶段:DeepSeek(或离线 mock)挖掘发明点
        ▼
InventionAnalysis 创新点清单(每条含数据证据/置信度/风险)
        │  disclose 阶段:生成结构化技术交底书
        ▼
TechnicalDisclosure + Markdown 渲染
        │  交接 PatentAgentPort(默认落盘 handoff JSON)
        ▼
技术交底书.md / 创新点清单.md / handoff_*.json  ← 专利 agent 取用
```

## 目录结构

```
sim2patent/
├── sim2patent/            # 主包
│   ├── parsers.py         # CSV/JSON -> SimulationResult(适配器)
│   ├── schema.py          # 数据模型(dataclass,可无损 JSON 化)
│   ├── stages.py          # analyze / disclose 两阶段 + JSON 契约校验
│   ├── prompts.py         # 两阶段中文提示词(硬约束:数值必须可溯源)
│   ├── llm.py             # DeepSeek(OpenAI 兼容)客户端,惰性导入 openai
│   ├── mock.py            # 离线确定性实现(无网络、无 key 可用)
│   ├── render.py          # 渲染 交底书.md / 创新点清单.md
│   ├── bridge.py          # 编排核心 Bridge
│   ├── patent_agent.py    # 专利 agent 交接端口(默认落盘)
│   ├── utils.py           # 数据摘要压缩
│   └── cli.py / __main__.py
├── examples/              # 示例输入(规范 JSON / 宽松 JSON / CSV)
├── tests/                 # pytest(全离线,不依赖网络)
└── output/                # 产物输出目录(自动创建,git 忽略)
```

## 安装

> 环境要求:Python ≥ 3.10(用了 `str | Path` 类型写法)。

```powershell
# 进入仓库目录
cd D:\Claude Code Project\AI\sim2patent

# 创建并激活虚拟环境
python -m venv .venv
.\.venv\Scripts\activate        # PowerShell
# Linux/macOS 用: source .venv/bin/activate

# 可编辑安装(自动带上开发依赖 pytest / ruff / build)
pip install -e ".[dev]"
```

安装完成后得到两个等价入口:

- `sim2patent ...`(console 脚本,来自 `pyproject.toml`)
- `python -m sim2patent ...`(未安装时也可用)

## 快速开始

```powershell
# 1) 设置密钥(真实 LLM);不设也可,会自动降级离线 mock
$env:DEEPSEEK_API_KEY = "sk-xxxxxxxx"

# 2) 运行
python -m sim2patent examples\sample_sim.json            # 全流程(LLM,缺 key 自动 mock)
python -m sim2patent run examples\sample_sim.csv --mock  # 强制离线,可无 key 试用
python -m sim2patent parse examples\sample_sim.json      # 只看解析结果
```

产物写在 `output/`:

| 文件 | 内容 |
| --- | --- |
| `handoff_<输入名>_<时间戳>.json` | 交接件:simulation + analysis + disclosure 全量结构化数据 |
| `交底书_<输入名>_<时间戳>.md` | 技术交底书草稿(给工程师/代理师审阅) |
| `创新点清单_<输入名>_<时间戳>.md` | 候选发明点清单(含数据证据与风险) |

> 注意:在 Windows PowerShell 里带中文文件名没问题;输出目录默认
> 是**当前工作目录**下的 `output/`,可用 `--out <目录>` 指定。

## 输入格式

### JSON(推荐:规范形态)

顶层键与 `schema.py` 对应:`title / objective / baseline / parameters / metrics / design_points / notes`。
`design_points` 中可用 `is_baseline: true` 标记对照方案。完整例子见
`examples/sample_sim.json`。宽松形态(任意记录数组 / 记录式 dict)也能解析,
列名含 `倾角/间距/入口/…` 自动判为参数,含 `温度/压降/应力/…` 判为指标。

### CSV

首行表头,每行一个设计点,例如:

```csv
设计点,入口风速,风道倾角,翅片间距,最高温度,温差,压降
P0,2.0,0,6,55.4,9.8,28
```

- 参数/指标列按列名特征词自动划分;划分不准时用
  `--param-cols 风道倾角,翅片间距` 显式指定参数列;
- 无 `is_baseline` 标记时,**首行视为对照方案**;
- 指标方向(越低越好/越高越好)由列名推断(温度/压降/应力→低好,效率/寿命→高好)。

## 设计要点与边界

- **数值可溯源**:两阶段提示词都硬性要求 LLM 只引用数据摘要中真实出现的数值,
  每一条发明点带 `supporting_evidence`,并区分"数据支持"与"待人工验证"(`concern`)。
- **离线可用**:不设 `DEEPSEEK_API_KEY` 或加 `--mock` 时走确定性 mock,
  全链路不联网,`tests/` 全部离线。
- **两层 JSON 契约校验**:LLM 输出解析失败自动重试一次,再失败给清晰报错。
- **行数保护**:输入设计点超过 60 行会被摘要截断并注明,避免超长上下文。
- **桥接止于交底书**:权利要求撰写属于**专利 agent**;本项目把交接协议定在
  `patent_agent.py`,后续实现 `PatentAgentPort` 并在 `make_patent_agent(kind=...)`
  注册即可接入真实专利 agent(如用 LLM 生成权利要求初稿),桥接侧零改动。
- **免责**:自动生成的是**草稿**,实施例数值与新颖性须经工程师/专利代理师核实,
  不构成任何专利法律意见。

## 测试与质量门禁

```powershell
python -m pytest tests -q       # 单元测试(全离线,不联网)
ruff check .                    # 静态检查
python -m build                 # 打包 sdist + wheel(需 pip install build)
```

CI(GitHub Actions)在每次 push/PR 上自动跑:Python 3.10/3.11/3.12 三套
`ruff + pytest + 端到端 mock smoke`,并执行 `python -m build` 校验产物,
见 `.github/workflows/ci.yml`。

## 开发 / 贡献

1. 报告问题、提功能请求 → GitHub Issues;
2. 提 PR:改代码 → 跑 `ruff check .` 与 `pytest` → 提交;
3. 主要扩展点:
   - 新输入格式:在 `sim2patent/parsers.py` 加一个解析分支;
   - 换/加模型:`LLMBackend` 只暴露 `chat_json`/`chat_text`;
   - 接入真实专利 agent:实现 `patent_agent.PatentAgentPort` 并在
     `make_patent_agent(kind=...)` 注册(例如用 LLM 生成权利要求初稿);
   - 版本与变更记录:改 `pyproject.toml` 与 `CHANGELOG.md`。

## 环境变量

| 变量 | 含义 | 默认 |
| --- | --- | --- |
| `DEEPSEEK_API_KEY` | DeepSeek API 密钥(缺省走 mock) | 无 |
| `DEEPSEEK_BASE_URL` | API 网关 | `https://api.deepseek.com` |
| `SIM2PATENT_MODEL` | 模型名 | `deepseek-chat` |
| `SIM2PATENT_TIMEOUT` | HTTP 超时(秒) | `120` |
