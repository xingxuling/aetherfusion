"""Capability signatures and TaoWind canonical mappings."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CapabilitySignature:
    capability_id: str
    display_name: str
    canonical_layer: str
    role: str
    default_strategy: str
    path_terms: tuple[str, ...]
    content_terms: tuple[str, ...]
    dependency_terms: tuple[str, ...] = ()
    rationale: str = ""


CAPABILITY_SIGNATURES: tuple[CapabilitySignature, ...] = (
    CapabilitySignature(
        "android-device-control",
        "Android Device Control",
        "L8-physical-observation-action",
        "shared-organ",
        "WRAP",
        ("android", "adb", "device", "uiautomator", "accessibility", "scrcpy"),
        ("adb", "uiautomator", "accessibilityservice", "android device", "scrcpy"),
        ("adb", "uiautomator2"),
        "External device-control runtimes should normally stay independently updatable behind an adapter/provider boundary.",
    ),
    CapabilitySignature(
        "agent-orchestration",
        "Agent Orchestration",
        "L1-intelligence-meta-control",
        "shared-organ",
        "FEDERATE",
        ("agent", "tools", "mcp", "planner", "orchestr"),
        ("agent", "tool call", "function call", "mcp", "orchestrat", "planner"),
        ("openai-agents", "mcp"),
        "Agent frameworks tend to own execution semantics, so federation/adaptation is safer than copying their control core.",
    ),
    CapabilitySignature(
        "tokenization-representation",
        "Tokenization and Representation",
        "L5-language-ir",
        "shared-organ",
        "ADAPT",
        ("token", "tokenizer", "encoding", "bpe"),
        ("tokenizer", "tokenization", "byte pair", "bpe", "encoding"),
        ("tiktoken", "tokenizers"),
        "Small representation libraries are often portable, but should remain below the canonical semantic owner.",
    ),
    CapabilitySignature(
        "speech-perception",
        "Speech Perception",
        "L8-physical-observation-action",
        "shared-organ",
        "WRAP",
        ("audio", "speech", "whisper", "transcrib"),
        ("speech", "transcrib", "audio", "whisper", "mel spectrogram"),
        ("whisper", "soundfile", "librosa"),
        "Model-heavy perception stacks are better exposed through provider boundaries than copied into a canonical core.",
    ),
    CapabilitySignature(
        "evaluation-benchmarking",
        "Evaluation and Benchmarking",
        "evidence-cross-cut",
        "formal-evidence-mirror",
        "ADAPT",
        ("eval", "benchmark", "metric", "score", "grader"),
        ("evaluation", "benchmark", "metric", "scorer", "grader", "assert"),
        ("pytest-benchmark",),
        "Evaluation logic should feed the Evidence Ledger without becoming the product or runtime authority.",
    ),
    CapabilitySignature(
        "procedural-generation",
        "Procedural Generation",
        "L7-simulation-open-world-lab",
        "shared-organ",
        "ADAPT",
        ("procgen", "generator", "environment", "world", "seed"),
        ("procedural", "generate", "environment", "world seed", "random seed"),
        (),
        "Generation primitives can be adapted into WorldSeed/GameBrain-style labs while keeping provenance and tests.",
    ),
    CapabilitySignature(
        "sparse-model-runtime",
        "Sparse Model Runtime",
        "L1-intelligence-meta-control",
        "shared-organ",
        "ABSORB",
        ("moe", "expert", "paging", "offload", "cache", "quant"),
        ("mixture of experts", "expert routing", "paging", "offload", "prefetch", "quantization", "kv cache"),
        (),
        "Runtime mechanisms such as expert paging and prefetch are usually more valuable as absorbed mechanisms than as a copied product surface.",
    ),
    CapabilitySignature(
        "browser-automation",
        "Browser Automation",
        "L8-physical-observation-action",
        "shared-organ",
        "WRAP",
        ("browser", "playwright", "selenium", "cdp", "chrom"),
        ("playwright", "selenium", "chrome devtools", "browser automation", "cdp"),
        ("playwright", "selenium"),
        "Browser controllers are external execution bodies and fit provider/adapter boundaries.",
    ),
)


CANONICAL_LAYER_LABELS = {
    "L0-subject-intent": "主体 / 意图",
    "L1-intelligence-meta-control": "智能 / 元控制",
    "L2-shared-semantic-kernel": "共享语义核",
    "L3-memory-knowledge-metabolism": "记忆 / 知识代谢",
    "L4-forecast-future-state": "预测 / 未来状态",
    "L5-language-ir": "语言 / 中间表示",
    "L6-reality-causal-runtime": "现实 / 因果运行时",
    "L7-simulation-open-world-lab": "模拟 / 开放世界实验场",
    "L8-physical-observation-action": "物理观察 / 行动",
    "L9-spatial-human-interface": "空间 / 人机接口",
    "evidence-cross-cut": "证据横切层",
}

FUSION_STRATEGIES = (
    "REUSE",
    "WRAP",
    "ADAPT",
    "TRANSPLANT",
    "ABSORB",
    "FEDERATE",
    "REPLACE",
    "IGNORE",
    "REVIEW",
)
