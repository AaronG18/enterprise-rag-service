"""Synthetic corpus content - architecture documents family.

Fully synthetic. These documents describe the system the repository itself implements, so they
also double as the design rationale a reviewer would look for (ADR-style statements with
trade-offs rather than assertions).
"""
from __future__ import annotations

from typing import Dict, List, Tuple

ARCHITECTURE: Dict[str, Dict[str, Tuple[str, List[Tuple[str, str]]]]] = {
    "multitenant": {
        "en": ("Multi-Tenant Design", [
            ("Isolation model",
             "Each tenant has its own corpus version and configuration; indexes are built per "
             "tenant at service start and are not shared."),
            ("Resource fairness",
             "Requests are admitted per tenant against a quota, so one tenant cannot exhaust "
             "the instance under load."),
            ("Trade-off",
             "Per-tenant indexes cost memory proportional to tenant count, which is accepted "
             "because tenant count is small and isolation is a compliance requirement."),
        ]),
        "zh": ("多租户设计", [
            ("隔离模型",
             "每个租户拥有独立的语料版本与配置；索引在服务启动时按租户构建且不共享。"),
            ("资源公平",
             "请求按租户配额准入，因此单个租户无法在负载下耗尽实例资源。"),
            ("权衡",
             "按租户建索引的内存开销随租户数增长，这一代价可接受，因为租户规模小且隔离是合规要求。"),
        ]),
    },
    "retrieval_pipeline": {
        "en": ("Retrieval Pipeline Architecture", [
            ("Stages",
             "Retrieval runs a vector stage and a lexical stage in parallel, fuses them with "
             "reciprocal rank fusion, then optionally reranks the fused candidates."),
            ("Why fusion over scoring",
             "Cosine similarity and BM25 scores are not comparable in scale, so a weighted sum "
             "would need recalibration every time either stage changed."),
            ("Configuration surface",
             "Retrieval mode and reranking are configuration, not code: swapping either must "
             "not require editing the pipeline."),
        ]),
        "zh": ("检索流水线架构", [
            ("阶段",
             "检索并行执行向量阶段与词法阶段，用倒数排名融合合并，随后可选地对融合候选重排。"),
            ("为何用融合而非加权",
             "余弦相似度与 BM25 分数量纲不可比，加权求和会在任一路变化时都需要重新标定。"),
            ("配置面",
             "检索模式与重排属于配置而非代码：切换二者都不应改动流水线代码。"),
        ]),
    },
    "scaling": {
        "en": ("Scaling Strategy", [
            ("Vertical first",
             "A single instance serves the measured load; horizontal scaling is deferred until "
             "the per-instance concurrency ceiling is reached."),
            ("Index growth",
             "The in-memory index is sized for corpora up to roughly 100 thousand chunks; beyond "
             "that an approximate neighbour index is required."),
            ("Statelessness",
             "The service keeps no durable state, so instances can be added or removed without "
             "session migration."),
        ]),
        "zh": ("扩容策略", [
            ("先纵向",
             "单实例可承载已测量的负载；在达到单实例并发上限前不引入横向扩容。"),
            ("索引增长",
             "内存索引按约 10 万块规模设计；超过该规模需改用近似最近邻索引。"),
            ("无状态",
             "服务不保存持久状态，因此可增减实例而无需迁移会话。"),
        ]),
    },
    "failure_modes": {
        "en": ("Failure Modes and Degradation", [
            ("Generator unavailable",
             "If the model provider is unreachable, the request fails with a provider error and "
             "the refusal path is not used, because inventing an answer is worse than failing."),
            ("Index unavailable",
             "If retrieval returns nothing, the service refuses with a low-confidence reason "
             "rather than answering from memory."),
            ("Cache inconsistency",
             "A cache entry that fails validation on read is treated as a miss and the entry is "
             "evicted."),
        ]),
        "zh": ("失效模式与降级", [
            ("生成器不可用",
             "若模型提供方不可达，请求以提供方错误失败且不走拒答路径，因为编造答案比失败更糟。"),
            ("索引不可用",
             "若检索无结果，服务以低置信度理由拒答，而非凭记忆作答。"),
            ("缓存不一致",
             "读取时校验失败的缓存条目视为未命中，并将该条目逐出。"),
        ]),
    },
    "data_flow": {
        "en": ("Data Flow Overview", [
            ("Ingestion",
             "Documents are validated, split into chunks with overlap, embedded, and written to "
             "the versioned corpus store."),
            ("Query",
             "A question is resolved against session history, retrieved against the index, and "
             "answered with citations drawn from retrieved chunks only."),
            ("Telemetry",
             "Each stage emits a structured event carrying the workflow identifier, so one "
             "request can be reconstructed from logs alone."),
        ]),
        "zh": ("数据流概览", [
            ("接入",
             "文档经校验、带重叠切分为块、向量化，并写入带版本的语料存储。"),
            ("查询",
             "问题先结合会话历史消解，再在索引上检索，并仅从检索到的块中给出引用作答。"),
            ("遥测",
             "每个阶段发出携带工作流标识的结构化事件，因此仅凭日志即可重建单次请求。"),
        ]),
    },
    "deployment_topology": {
        "en": ("Deployment Topology", [
            ("Components",
             "The service, the log shipper and the metrics collector run together; the model "
             "provider is reached over loopback in development and over the network in "
             "production."),
            ("Environments",
             "Development runs a single instance on loopback; production runs at least two "
             "instances behind a load balancer."),
            ("Configuration",
             "All environment differences are expressed in configuration files, so the same "
             "artefact is promoted between environments."),
        ]),
        "zh": ("部署拓扑", [
            ("组件",
             "服务、日志投递器与指标采集器共同运行；模型提供方在开发环境经回环访问，生产环境经网络访问。"),
            ("环境",
             "开发环境为回环单实例；生产环境在负载均衡后至少两个实例。"),
            ("配置",
             "所有环境差异都以配置文件表达，因此同一产物可在环境间晋级。"),
        ]),
    },
    "security_architecture": {
        "en": ("Security Architecture", [
            ("Data boundaries",
             "Queries and retrieved content leave the host only towards a configured model "
             "endpoint, and a loopback-only guard is enforced in the default path."),
            ("Secrets",
             "Credentials are read from the environment at call time, never written to logs, "
             "and never persisted by the service."),
            ("Output controls",
             "Answers are redacted before being returned, and the same redaction is applied to "
             "the log record so logs cannot leak what the answer hid."),
        ]),
        "zh": ("安全架构", [
            ("数据边界",
             "提问与检索内容仅发往已配置的模型端点；默认路径强制回环地址校验。"),
            ("凭据",
             "凭据在调用时从环境读取，绝不写入日志，也绝不持久化。"),
            ("输出控制",
             "答案在返回前脱敏，日志记录同样脱敏，以避免日志泄露答案中已隐藏的信息。"),
        ]),
    },
    "cost_model": {
        "en": ("Cost Model", [
            ("Drivers",
             "Cost is driven by input tokens, output tokens and the number of model calls per "
             "answer, not by request count alone."),
            ("Levers",
             "Caching, retrieval depth and model tier are the three levers; retrieval depth has "
             "the largest effect because context dominates the prompt."),
            ("Reporting",
             "Cost is reported per thousand calls from measured token totals, and no monetary "
             "value is printed when a price is not configured."),
        ]),
        "zh": ("成本模型", [
            ("驱动因素",
             "成本由输入 token、输出 token 以及每次答案的模型调用次数驱动，而非仅由请求数决定。"),
            ("调节手段",
             "缓存、检索深度与模型档位是三个调节手段；检索深度影响最大，因为上下文主导提示。"),
            ("报告",
             "成本按每千次调用基于实测 token 总量报告；未配置价格时不输出金额。"),
        ]),
    },
    "migration_plan": {
        "en": ("Migration Plan", [
            ("Phases",
             "Migration runs in three phases: shadow evaluation, partial traffic with rollback, "
             "then full cutover."),
            ("Shadow evaluation",
             "The new configuration answers the same labelled set offline; promotion requires "
             "that no target metric regresses by more than 2 percent."),
            ("Rollback criteria",
             "Rollback is triggered by any refusal-rate increase above 5 percentage points or "
             "any p95 increase above 20 percent."),
        ]),
        "zh": ("迁移计划", [
            ("阶段",
             "迁移分三阶段：影子评估、带回滚的部分流量、然后全量切换。"),
            ("影子评估",
             "新配置离线回答同一标注集；晋级要求任何目标指标回退不超过 2%。"),
            ("回滚条件",
             "拒答率上升超过 5 个百分点，或 p95 上升超过 20%，即触发回滚。"),
        ]),
    },
    "decision_log": {
        "en": ("Architecture Decision Log", [
            ("Deterministic provider by default",
             "The default generator is deterministic so that every measurement is reproducible "
             "without credentials; real generation is a separate, separately tagged lane."),
            ("Hashing vectors",
             "Vectors come from a hash of tokens rather than a model, which removes a "
             "dependency and a download, at the cost of semantic quality."),
            ("In-memory index",
             "The index lives in memory because the corpus is small; this is revisited when the "
             "chunk count grows by two orders of magnitude."),
        ]),
        "zh": ("架构决策记录", [
            ("默认使用确定性生成器",
             "默认生成器是确定性的，因此所有测量无需凭据即可复现；真实生成为独立且单独打标的通道。"),
            ("哈希向量",
             "向量由词元哈希得到而非模型，消除了依赖与下载，代价是语义质量下降。"),
            ("内存索引",
             "索引驻留内存，因为语料规模很小；当块数增长两个数量级时需重新评估。"),
        ]),
    },
}


def architecture_documents() -> List[Tuple[str, str, str, List[Tuple[str, str]]]]:
    out: List[Tuple[str, str, str, List[Tuple[str, str]]]] = []
    for _topic, by_language in ARCHITECTURE.items():
        for language in ("en", "zh"):
            title, sections = by_language[language]
            out.append(("architecture", language, title, sections))
    return out
