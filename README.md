# agent-evidence-vault

`agent-evidence-vault` 是一个零运行时依赖的 Python 3.9+ 开源项目，用来把 Codex、Claude Code、Cursor 等 AI coding agent 的一次交付离线打包成可审计 evidence vault。它扫描交付目录，读取命令、测试、CI、风险、验收、review notes 等证据，生成 manifest、SHA256 完整性哈希、Markdown/JSON/JUnit 报告，并提供 CI gate 退出码，帮助团队回答：

- 这次 agent 改动验证了什么？
- 缺少哪些关键证据？
- 是否存在阻塞风险？
- manifest 中记录的文件在后续是否被篡改？
- PR/CI 能不能合并或放行？

## 适用场景

- AI agent 完成代码改动后，维护者希望获得离线、可归档、可审计的交付证据包。
- 平台团队希望为 AI 辅助开发建立轻量 CI gate。
- 安全、合规或工程效能团队希望在 PR 中保留测试、命令、风险和验收依据。
- 多 agent 协作时，需要统一 Codex、Claude Code、Cursor 等工具的交付证据格式。

## 安装

```bash
python -m pip install -e .
```

项目只使用 Python 标准库；没有外部运行时依赖。

## 快速开始

```bash
python -m agent_evidence_vault collect \
  --root examples/basic \
  --evidence examples/basic/evidence \
  --out vault \
  --format all \
  --minimum-score 60

python -m agent_evidence_vault check \
  --manifest vault/manifest.json \
  --root examples/basic
```

安装后也可以使用脚本名：

```bash
aev collect --root . --evidence evidence --out vault
aev score --manifest vault/manifest.json
```

## CLI

### collect

扫描目录、解析证据并输出报告。

```bash
aev collect --root . --evidence evidence --out vault --format all
```

常用参数：

- `--root`：agent 交付目录，默认当前目录。
- `--evidence`：证据输入目录，默认 `<root>/evidence`。
- `--out`：输出目录，默认 `vault`。
- `--config`：JSON 配置文件。
- `--format`：可重复传入，支持 `json`、`markdown`、`junit`、`all`。
- `--minimum-score`：覆盖配置中的最低分。
- `--quiet`：减少 stdout 输出。

退出码：

- `0`：gate 通过。
- `1`：证据检查或最低分 gate 未通过。
- `2`：输入、配置或解析错误。

### check

读取 manifest 并重新计算文件 SHA256，检查完整性。

```bash
aev check --manifest vault/manifest.json --root .
```

退出码：

- `0`：所有文件存在且哈希匹配。
- `2`：存在缺失文件或哈希不匹配。

### score

输出 manifest 的分数和失败检查。

```bash
aev score --manifest vault/manifest.json --json
```

### validate-config

校验配置文件。

```bash
aev validate-config --config aev.config.json
```

## Python API

```python
from agent_evidence_vault import collect_vault, verify_manifest

result = collect_vault(
    root=".",
    evidence_dir="evidence",
    out_dir="vault",
    formats=("json", "markdown", "junit"),
)

assert result.manifest.score >= 70

verify = verify_manifest("vault/manifest.json", root=".")
assert verify.gate_passed
```

## 输入格式

证据目录支持 JSON、JSONL 和简单 `key: value` 文本。默认识别这些文件名：

- `commands.jsonl`、`commands.json`、`commands.txt`
- `tests.jsonl`、`tests.json`、`tests.txt`
- `ci.jsonl`、`ci.json`、`ci.txt`
- `risks.jsonl`、`risks.json`、`risks.txt`
- `acceptance.jsonl`、`acceptance.json`、`acceptance.txt`
- `review_notes.jsonl`、`review_notes.json`、`review_notes.txt`

JSONL 示例：

```jsonl
{"name":"unit tests","command":"python -m unittest","exit_code":0,"status":"passed"}
{"name":"type check","command":"python -m py_compile src/app.py","exit_code":0}
```

JSON 示例：

```json
{
  "items": [
    {"name": "test_api", "status": "passed", "framework": "unittest"}
  ]
}
```

TXT 示例：

```text
criterion: 用户可以生成 manifest
status: passed
note: 已通过端到端 CLI 验证。
```

## 证据模型

manifest 中的核心对象：

- `files`：交付目录内文件的相对路径、大小、类型、证据分类和 SHA256。
- `evidence`：命令、测试、CI、风险、验收、review notes 等结构化证据。
- `checks`：缺失证据、失败测试、阻塞风险、最低分等 gate 检查。
- `summary`：证据数量、分类统计、失败数量、开放风险数量。
- `score`：0 到 100 的风险评分。

风险项推荐字段：

```json
{"name":"No browser screenshot","severity":"medium","status":"open","mitigation":"Manual review required."}
```

支持的风险等级：`low`、`medium`、`high`、`critical`。

## 完整性校验

`collect` 会对扫描到的每个文件计算 SHA256，并写入 `manifest.json`。后续可以用 `check` 重新计算：

```bash
aev check --manifest vault/manifest.json --root .
```

如果文件被修改、删除或替换，完整性检查会失败并返回非零退出码。

## CI / PR 集成

GitHub Actions 示例：

```yaml
name: Evidence Vault
on: [pull_request]
jobs:
  evidence:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: python -m pip install -e .
      - run: aev collect --root . --evidence evidence --out vault --format all
      - run: aev check --manifest vault/manifest.json --root .
```

JUnit 输出 `vault/junit.xml` 可以被 CI 测试报告系统读取；Markdown 输出 `vault/report.md` 可贴到 PR 评论或 artifact。

## 配置

配置文件是 JSON：

```json
{
  "required_evidence": ["commands", "tests", "acceptance"],
  "fail_on_open_risks": ["critical", "high"],
  "minimum_score": 75,
  "include": ["**/*"],
  "exclude": [".git/**", "__pycache__/**", "vault/**"],
  "max_file_bytes": 10485760
}
```

默认 gate 要求存在 `commands`、`tests`、`acceptance`，没有失败命令/测试/CI/验收证据，没有配置中指定等级的开放风险，并且分数达到最低值。

## 风险评分

基础分为 100。扣分规则：

- 开放风险：`low` 3，`medium` 8，`high` 18，`critical` 35。
- 失败的命令、测试、CI 或验收证据：每项 10。
- 失败检查：按严重程度扣分。
- 没有任何证据：额外扣 30。

分数用于辅助 gate，不替代人工 review。

## 限制

- 只做离线文件扫描和证据汇总，不调用外部服务。
- 不验证 CI URL 的真实性，也不访问私有系统。
- 不解析任意 YAML；配置使用 JSON，证据可用 JSON/JSONL/TXT。
- 大文件默认跳过，避免把二进制产物塞进 manifest。
- SHA256 能证明文件内容一致，不能证明证据语义真实。

## 开发指南

```bash
python -m pip install -e .
python -m unittest discover -s tests
python -m agent_evidence_vault collect --root examples/basic --evidence examples/basic/evidence --out vault --format all --minimum-score 60
```

代码结构：

- `src/agent_evidence_vault/scanner.py`：目录扫描、文件分类、SHA256。
- `src/agent_evidence_vault/parsers.py`：JSON/JSONL/TXT 证据读取。
- `src/agent_evidence_vault/checks.py`：缺失证据、失败项、开放风险和最低分检查。
- `src/agent_evidence_vault/scoring.py`：风险评分。
- `src/agent_evidence_vault/reports.py`：Markdown/JSON/JUnit 报告。
- `src/agent_evidence_vault/api.py`：可复用 Python API。
- `src/agent_evidence_vault/cli.py`：CLI 入口。

## English

`agent-evidence-vault` is a dependency-free Python 3.9+ developer tool for packaging one AI coding-agent delivery into an offline, auditable evidence vault. It is designed for teams using Codex, Claude Code, Cursor, and similar agents.

It answers practical review questions:

- What did the agent actually change and verify?
- Which command, test, CI, screenshot, log, risk, acceptance, or review-note evidence is present?
- Which evidence is missing?
- Are there blocking open risks?
- Has any file changed since the manifest was created?
- Should CI allow this delivery to merge?

### Installation

```bash
python -m pip install -e .
```

No external runtime dependencies are required.

### CLI

```bash
aev collect --root . --evidence evidence --out vault --format all
aev check --manifest vault/manifest.json --root .
aev score --manifest vault/manifest.json --json
aev validate-config --config aev.config.json
```

Exit codes:

- `0`: gate passed.
- `1`: collection or score gate failed.
- `2`: parse/config/input error, or integrity verification failed.

### Evidence Inputs

Place evidence files in an evidence directory:

- `commands.jsonl/json/txt`
- `tests.jsonl/json/txt`
- `ci.jsonl/json/txt`
- `risks.jsonl/json/txt`
- `acceptance.jsonl/json/txt`
- `review_notes.jsonl/json/txt`

JSONL example:

```jsonl
{"name":"unit tests","command":"python -m unittest","exit_code":0,"status":"passed"}
```

Text example:

```text
criterion: User can generate a manifest
status: passed
note: Verified through the end-to-end CLI flow.
```

### Evidence Model

The manifest contains:

- `files`: relative path, size, kind, evidence category, and SHA256 for scanned files.
- `evidence`: structured command/test/CI/risk/acceptance/review-note items.
- `checks`: missing evidence checks, failed run checks, open risk checks, and minimum score checks.
- `summary`: category/status counts and risk totals.
- `score`: a 0-100 risk score.

### Integrity Verification

`collect` writes SHA256 hashes into `manifest.json`. `check` recomputes them:

```bash
aev check --manifest vault/manifest.json --root .
```

The command fails if any file is missing or changed.

### CI / PR Integration

The repository includes `.github/workflows/ci.yml`. A minimal PR gate is:

```yaml
- run: python -m pip install -e .
- run: aev collect --root . --evidence evidence --out vault --format all
- run: aev check --manifest vault/manifest.json --root .
```

Use `vault/junit.xml` as a CI test report and `vault/report.md` as a PR artifact or comment source.

### Limitations

The tool is intentionally offline. It does not call CI providers, validate external URLs, verify private tokens, or prove that a human process was followed. SHA256 validates file content integrity, not the semantic truth of the evidence.

