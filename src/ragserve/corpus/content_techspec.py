"""Synthetic corpus content - technical specifications family.

Fully synthetic. Specifications deliberately state numbers (latency budgets, limits, versions,
ports) because those are the facts a QA service is most often asked for and the easiest to
verify as correct or wrong.
"""
from __future__ import annotations

from typing import Dict, List, Tuple

TECHSPEC: Dict[str, Dict[str, Tuple[str, List[Tuple[str, str]]]]] = {
    "ingestion_api": {
        "en": ("Ingestion API Contract", [
            ("Endpoints",
             "Batches are accepted at POST /v1/documents with a maximum of 200 documents per "
             "batch and a 10 MB payload limit."),
            ("Response codes",
             "A batch returns 202 when queued, 422 when schema validation fails, and 429 when "
             "the per-tenant rate limit is exceeded."),
            ("Idempotency",
             "Every request carries an Idempotency-Key header; retries within 24 hours return "
             "the original result instead of duplicating work."),
        ]),
        "zh": ("接入接口规范", [
            ("端点",
             "批次通过 POST /v1/documents 接收，每批最多 200 篇文档，负载上限 10 MB。"),
            ("响应码",
             "批次入队返回 202，模式校验失败返回 422，超出租户速率限制返回 429。"),
            ("幂等性",
             "每个请求携带 Idempotency-Key 头；24 小时内的重试返回原结果而不重复处理。"),
        ]),
    },
    "query_service": {
        "en": ("Query Service Specification", [
            ("Latency budget",
             "The query path targets a p95 of 800 ms, of which retrieval receives 250 ms and "
             "generation receives 500 ms."),
            ("Request shape",
             "A request carries the question, an optional session identifier and an optional "
             "configuration override for retrieval mode and reranking."),
            ("Response shape",
             "A response carries the answer text, the ordered citation list and a trace block "
             "with confidence, coverage and the retrieved chunk identifiers."),
        ]),
        "zh": ("查询服务规范", [
            ("延迟预算",
             "查询路径目标 p95 为 800 毫秒，其中检索 250 毫秒、生成 500 毫秒。"),
            ("请求结构",
             "请求包含问题、可选的会话标识，以及可选的检索模式与重排配置覆盖。"),
            ("响应结构",
             "响应包含答案正文、有序引用列表，以及带置信度、覆盖率和检索块标识的追踪块。"),
        ]),
    },
    "embedding_pipeline": {
        "en": ("Embedding Pipeline Specification", [
            ("Vector shape",
             "Vectors are 512 dimensional and L2 normalised so that cosine similarity and dot "
             "product coincide."),
            ("Determinism",
             "Vectorisation is deterministic: the same text and seed always produce the same "
             "vector, which is what makes offline measurement reproducible."),
            ("Reindexing",
             "A full reindex of the corpus completes in under 60 seconds and is triggered by a "
             "change in the corpus version hash."),
        ]),
        "zh": ("向量化流水线规范", [
            ("向量维度",
             "向量为 512 维并做 L2 归一化，因此余弦相似度与点积等价。"),
            ("确定性",
             "向量化是确定性的：相同文本与种子始终产生相同向量，这也是离线测量可复现的前提。"),
            ("重建索引",
             "语料全量重建索引在 60 秒内完成，由语料版本哈希变化触发。"),
        ]),
    },
    "cache_layer": {
        "en": ("Cache Layer Specification", [
            ("Layers",
             "Two layers exist: an exact layer keyed by the normalised question and a semantic "
             "layer keyed by a locality-sensitive signature."),
            ("Expiry",
             "Exact entries expire after 300 seconds. Semantic entries expire after 900 seconds "
             "and additionally require answer-quality validation on write."),
            ("Invalidation",
             "Entries are scoped by corpus version, retrieval mode and model version, so any of "
             "those changing invalidates the entry without an explicit purge."),
        ]),
        "zh": ("缓存层规范", [
            ("层级",
             "缓存分两层：按归一化问题键入的精确层，以及按局部敏感签名键入的语义层。"),
            ("过期",
             "精确条目 300 秒后过期。语义条目 900 秒后过期，且写入时须通过答案质量校验。"),
            ("失效",
             "条目按语料版本、检索模式与模型版本作用域化，任一变化即自动失效，无需显式清理。"),
        ]),
    },
    "auth_service": {
        "en": ("Authentication Service Specification", [
            ("Tokens",
             "Access tokens are short lived at 15 minutes; refresh tokens rotate on every use "
             "and are valid for 30 days."),
            ("Scopes",
             "Scopes are checked per endpoint. Retrieval requires the query scope, and "
             "administrative configuration requires the admin scope."),
            ("Failure handling",
             "Five consecutive failures for one principal lock the principal for 15 minutes and "
             "emit a security event."),
        ]),
        "zh": ("认证服务规范", [
            ("令牌",
             "访问令牌有效期 15 分钟；刷新令牌每次使用后轮换，有效期 30 天。"),
            ("权限范围",
             "每个端点校验权限范围。检索需要查询范围，管理配置需要管理范围。"),
            ("失败处理",
             "同一主体连续失败 5 次将锁定 15 分钟，并发出安全事件。"),
        ]),
    },
    "event_bus": {
        "en": ("Event Bus Specification", [
            ("Topics",
             "The bus carries document lifecycle, query lifecycle and incident topics, each "
             "versioned and schema validated on publish."),
            ("Delivery",
             "Delivery is at least once with a maximum of 5 attempts using exponential backoff "
             "starting at 2 seconds."),
            ("Ordering",
             "Ordering is guaranteed within a partition key, which is the document identifier "
             "for lifecycle events and the session identifier for query events."),
        ]),
        "zh": ("事件总线规范", [
            ("主题",
             "总线承载文档生命周期、查询生命周期与事件主题，各主题均有版本并在发布时做模式校验。"),
            ("投递",
             "投递语义为至少一次，最多重试 5 次，采用从 2 秒开始的指数退避。"),
            ("顺序",
             "在同一分区键内保证顺序：生命周期事件用文档标识，查询事件用会话标识。"),
        ]),
    },
    "storage_engine": {
        "en": ("Storage Engine Specification", [
            ("Layout",
             "Chunks and documents are stored as append-only JSON lines keyed by corpus version, "
             "with a manifest describing counts and hashes."),
            ("Compaction",
             "Compaction runs when a corpus version exceeds 50 artefacts and rewrites the "
             "manifest atomically."),
            ("Durability",
             "Writes are flushed before acknowledgement, and every artefact carries a checksum "
             "verified on read."),
        ]),
        "zh": ("存储引擎规范", [
            ("结构",
             "分块与文档以按语料版本键控的仅追加 JSON Lines 存储，并由清单描述数量与哈希。"),
            ("压缩合并",
             "当某语料版本产物超过 50 个时执行压缩合并，并原子地重写清单。"),
            ("持久性",
             "写入在确认前落盘，每个产物都带校验和并在读取时校验。"),
        ]),
    },
    "observability_stack": {
        "en": ("Observability Stack Specification", [
            ("Signals",
             "The stack collects structured logs, request metrics and traces; every request "
             "carries a workflow identifier correlating the three."),
            ("Sampling",
             "Traces are sampled at 10 percent, while errors and refusals are always sampled "
             "regardless of rate."),
            ("Retention",
             "Metrics are retained for 15 months, traces for 30 days and raw logs for 90 days."),
        ]),
        "zh": ("可观测性栈规范", [
            ("信号",
             "该栈采集结构化日志、请求指标与链路追踪；每个请求带工作流标识关联三者。"),
            ("采样",
             "链路追踪按 10% 采样；错误与拒答无论速率一律采样。"),
            ("留存",
             "指标留存 15 个月，链路追踪留存 30 天，原始日志留存 90 天。"),
        ]),
    },
    "deployment_pipeline": {
        "en": ("Deployment Pipeline Specification", [
            ("Stages",
             "A change passes build, hermetic test, contract test and a canary stage before it "
             "reaches production traffic."),
            ("Canary",
             "The canary serves 5 percent of traffic for 30 minutes and rolls back automatically "
             "if the error rate exceeds 1 percent."),
            ("Rollback",
             "Rollback restores the previous artefact within 10 minutes and preserves the "
             "previous configuration."),
        ]),
        "zh": ("部署流水线规范", [
            ("阶段",
             "变更在到达生产流量前需经过构建、密闭测试、契约测试与灰度阶段。"),
            ("灰度",
             "灰度承接 5% 流量并持续 30 分钟；若错误率超过 1% 则自动回滚。"),
            ("回滚",
             "回滚在 10 分钟内恢复上一产物，并保留上一配置。"),
        ]),
    },
    "rate_limiting": {
        "en": ("Rate Limiting Specification", [
            ("Limits",
             "The default tenant limit is 60 requests per minute and 5000 requests per day, "
             "enforced per tenant rather than per address."),
            ("Headers",
             "Responses carry remaining quota and reset time; clients should back off on 429 "
             "using the retry-after value."),
            ("Bursts",
             "A burst allowance of 10 requests smooths short spikes without changing the "
             "sustained limit."),
        ]),
        "zh": ("速率限制规范", [
            ("限制",
             "默认租户限制为每分钟 60 次请求、每天 5000 次请求，按租户而非按地址执行。"),
            ("响应头",
             "响应携带剩余配额与重置时间；客户端在收到 429 时应依 retry-after 退避。"),
            ("突发",
             "10 次请求的突发额度用于平滑短时尖峰，不改变持续限制。"),
        ]),
    },
}


def techspec_documents() -> List[Tuple[str, str, str, List[Tuple[str, str]]]]:
    out: List[Tuple[str, str, str, List[Tuple[str, str]]]] = []
    for _topic, by_language in TECHSPEC.items():
        for language in ("en", "zh"):
            title, sections = by_language[language]
            out.append(("techspec", language, title, sections))
    return out
