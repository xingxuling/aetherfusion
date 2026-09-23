# AetherFusion Capability Fusion v2 Alpha

## North Star / 北极星

Turn external software projects into **auditable capability organs**, rather than
blindly copying repositories into a monolith.

中文：把外部软件项目消化成**可审计、可回滚、可持续同步的能力器官**，而不是把整个仓库无脑复制进一个超级仓库。

## First executable slice / 第一版可执行切片

The v2 alpha adds a local, read-only capability planner:

```text
source project
→ license gate
→ capability extraction
→ TaoWind canonical-layer mapping
→ target gap / overlap comparison
→ fusion strategy selection
→ JSON / Markdown evidence plan
```

中文对应：

```text
源项目
→ 许可证闸门
→ 能力提取
→ TaoWind 规范能力层映射
→ 目标缺口 / 重叠比对
→ 融合策略选择
→ JSON / Markdown 证据计划
```

## Strategies / 融合策略

- `REUSE`：直接复用。
- `WRAP`：封装，通过 Adapter / Provider 接入。
- `ADAPT`：适配，在保留原项目语义边界的前提下重接接口。
- `TRANSPLANT`：器官移植，只迁入边界清楚的小型模块。
- `ABSORB`：机制吸收，提取算法/调度/结构机制后原生重实现。
- `FEDERATE`：联邦融合，两边保持独立，通过协议协作。
- `REPLACE`：替换旧器官。
- `IGNORE`：明确忽略。
- `REVIEW`：证据不足，进入人工审查。

## Recognized capability families / 当前识别能力族

The first catalog recognizes:

- Android device control / Android 设备控制
- Agent orchestration / 智能体编排
- Tokenization and representation / 词元化与表示
- Speech perception / 语音感知
- Evaluation and benchmarking / 评测与基准
- Procedural generation / 程序化生成
- Sparse model runtime / 稀疏模型运行时
- Browser automation / 浏览器自动化

The catalog is intentionally small and evidence-driven. New signatures should be
added only when they map to a clear canonical owner and have tests.

中文：目录故意保持小而明确；只有当新能力能归位到明确的规范所有者并拥有测试证据时，才扩展签名。

## Safety / 安全边界

This alpha is planning-only:

- no automatic source copying;
- no dependency installation;
- no target config rewriting;
- no overwrite;
- no network clone/update;
- license review can block direct transplantation;
- every decision keeps evidence and a next-action chain.

中文：当前 alpha 只做规划，不自动复制源码、不安装依赖、不修改目标配置、不覆盖文件，也不主动联网拉取仓库。许可证存在不确定性时，会阻止高耦合移植。

## CLI / 命令行

```bash
aetherfusion-capability \
  --source ./external-project \
  --target ./taowind-project \
  --project-url https://github.com/example/project \
  --out ./reports/capability-fusion.md \
  --json ./reports/capability-fusion.json
```

中文：`--source` 是待吸收项目，`--target` 是 TaoWind 目标项目；输出同时包含人类可读计划和机器可读计划。

Use `--strict-license` when automated pipelines should fail closed on unknown or review-required licensing.

中文：自动流水线若要求许可证不明确就直接失败，可增加 `--strict-license`。

## Planned next slice / 下一切片

The next executable slice should add:

1. registry-backed canonical ownership checks / 注册表驱动的规范所有权检查；
2. adapter skeleton generation / Adapter 骨架生成；
3. upstream-sync manifests / 上游同步清单；
4. RNCS branch/sandbox handoff / RNCS 分支或沙箱交接；
5. Evidence Ledger receipts / 证据账本回执；
6. capability archaeology ingestion / 资产考古机结果接入；
7. optional GitHub source acquisition behind explicit authorization / 经明确授权的 GitHub 源项目获取。

That turns v2 from a capability planner into a governed external-capability digestion pipeline.

中文：完成这些后，AetherFusion v2 就会从“能力级规划器”变成真正受治理的外部能力消化流水线。
