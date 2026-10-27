"""Synthetic corpus content.

Fully synthetic, no third-party or internal material (RULES R6). Content is literal rather
than randomly assembled word soup: retrieval quality later depends on passages that read
like real policy, specification and design text, with concrete figures to retrieve.

Shape: 4 families x 2 languages x 3 documents, each with 3 sections.
"""
from __future__ import annotations

from typing import Dict, List, Tuple

# family -> language -> list of (title, [(heading, body), ...])
CONTENT: Dict[str, Dict[str, List[Tuple[str, List[Tuple[str, str]]]]]] = {
    "handbook": {
        "en": [
            ("Annual Leave Policy", [
                ("Entitlement",
                 "Full-time employees accrue 15 working days of paid annual leave per calendar year. "
                 "Part-time employees accrue leave pro rata based on contracted hours."),
                ("Carry-over",
                 "Up to 5 unused days may be carried into the next calendar year. "
                 "Carried-over days expire on 31 March and are not paid out on departure."),
                ("Request process",
                 "Leave of more than 3 consecutive days requires line-manager approval at least 10 working days in advance. "
                 "Requests are submitted through the people portal, which records the approval decision."),
            ]),
            ("Remote Work Policy", [
                ("Eligibility",
                 "Employees may work remotely up to 3 days per week after completing a 90-day onboarding period. "
                 "Roles requiring physical access to production hardware are excluded."),
                ("Equipment and allowance",
                 "The company provides a laptop and a one-off home-office allowance of 250 units. "
                 "Replacement cycles follow the standard 3-year hardware refresh."),
                ("Expectations",
                 "Remote workers must be reachable during core hours of 10:00 to 16:00 local time. "
                 "Teams must keep a written record of which days each member works on site."),
            ]),
            ("Expense Reimbursement Policy", [
                ("Limits",
                 "Travel and subsistence claims must be submitted within 30 days of the expense date. "
                 "Claims above 500 units require a second approver."),
                ("Receipts",
                 "Itemised receipts are required for every claim line. "
                 "Missing receipts may be replaced by a signed declaration once per quarter."),
                ("Payment timing",
                 "Approved claims are paid in the payroll run of the following month, normally on the 25th."),
            ]),
            ("Performance Review Cycle", [
                ("Cadence",
                 "Formal reviews take place twice a year, in June and December. "
                 "Managers run a shorter check-in every 4 weeks between cycles."),
                ("Rating scale",
                 "Reviews use a 4-point scale: below expectations, meets expectations, exceeds expectations, outstanding. "
                 "A written rationale is required for the top and bottom rating."),
                ("Outcomes",
                 "Ratings inform the annual salary review and the promotion shortlist. "
                 "Employees may append a written response within 10 working days."),
            ]),
        ],
        "zh": [
            ("年假政策", [
                ("额度",
                 "全职员工每个日历年享有 15 个工作日带薪年假。兼职员工按合同约定工时按比例累计。"),
                ("结转",
                 "最多可将 5 天未使用假期结转至下一日历年。结转假期于次年 3 月 31 日失效，离职时不予折现。"),
                ("申请流程",
                 "连续休假超过 3 天需提前 10 个工作日取得直属主管批准。申请通过人事系统提交，系统记录审批结果。"),
            ]),
            ("远程办公政策", [
                ("适用条件",
                 "员工在完成 90 天入职期后，每周最多可远程办公 3 天。需要现场接触生产硬件的岗位不适用。"),
                ("设备与补贴",
                 "公司提供笔记本电脑，并发放一次性家庭办公补贴 250 元。设备更换遵循 3 年标准更新周期。"),
                ("工作要求",
                 "远程办公人员须在当地时间 10:00 至 16:00 的核心时段保持可联系状态。团队须书面记录每位成员现场办公的日期。"),
            ]),
            ("费用报销政策", [
                ("限额",
                 "差旅与食宿费用须在费用发生之日起 30 天内提交。超过 500 元的申请需第二审批人复核。"),
                ("凭证",
                 "每一条报销明细均需提供明细凭证。缺失凭证每季度可用一次签署声明替代。"),
                ("付款时间",
                 "已批准的报销在次月工资发放日支付，通常为每月 25 日。"),
            ]),
            ("绩效评估周期", [
                ("周期",
                 "正式评估每年两次，分别在 6 月和 12 月。两次评估之间，主管每 4 周进行一次简短沟通。"),
                ("评级标准",
                 "评估采用四级：低于预期、符合预期、超出预期、卓越。最高与最低评级均须附书面理由。"),
                ("结果应用",
                 "评级结果用于年度薪酬调整与晋升候选名单。员工可在 10 个工作日内附书面意见。"),
            ]),
        ],
    },
    "compliance": {
        "en": [
            ("Data Retention Standard", [
                ("Retention windows",
                 "Operational logs are retained for 90 days; audit records are retained for 7 years. "
                 "Personal data is deleted within 30 days of a verified erasure request."),
                ("Exceptions",
                 "Retention may be extended only by a documented legal hold issued by the compliance office. "
                 "Extended retention expires when the hold is lifted."),
                ("Enforcement",
                 "Retention is verified quarterly by an automated job that reports deviations to the compliance office."),
            ]),
            ("Access Review Procedure", [
                ("Cadence",
                 "Privileged access is reviewed every 90 days; standard access is reviewed every 180 days."),
                ("Review actions",
                 "Reviewers must approve, downgrade or revoke each grant. "
                 "Grants not actioned within 14 days are automatically revoked."),
                ("Evidence",
                 "Each review cycle produces an artefact listing every decision, retained for 7 years."),
            ]),
            ("Incident Reporting Duty", [
                ("Thresholds",
                 "Any suspected personal-data breach must be reported within 24 hours of detection. "
                 "Confirmed breaches are escalated to the regulator within 72 hours."),
                ("Content of report",
                 "The report must state the data categories, affected record count, root cause and containment actions."),
                ("Post-incident",
                 "A written post-incident review is due within 10 working days and is tracked to closure."),
            ]),
            ("Third-Party Vendor Assessment", [
                ("Screening",
                 "Vendors handling personal data must pass a security questionnaire before contract signature. "
                 "High-risk vendors additionally require an on-site audit."),
                ("Contractual controls",
                 "Contracts must include confidentiality terms, a breach notification clause of 24 hours and a right to audit."),
                ("Re-assessment",
                 "Assessments are repeated every 12 months, or immediately after a vendor security incident."),
            ]),
        ],
        "zh": [
            ("数据保留规范", [
                ("保留期限",
                 "运行日志保留 90 天，审计记录保留 7 年。经核实的删除请求须在 30 天内完成个人数据删除。"),
                ("例外情形",
                 "仅当合规办公室出具书面法律保留通知时方可延长保留期限。保留期在通知解除时终止。"),
                ("执行与检查",
                 "每季度由自动化任务核查保留情况，并向合规办公室报告偏差。"),
            ]),
            ("访问权限复核流程", [
                ("周期",
                 "特权权限每 90 天复核一次，普通权限每 180 天复核一次。"),
                ("复核动作",
                 "复核人须对每项授权作出保留、降级或撤销的决定。14 天内未处理的授权将被自动撤销。"),
                ("证据留存",
                 "每轮复核生成记录全部决定的工件，并保留 7 年。"),
            ]),
            ("事件上报义务", [
                ("阈值",
                 "任何疑似个人数据泄露须在发现后 24 小时内上报。确认泄露须在 72 小时内向监管机构升级报告。"),
                ("报告内容",
                 "报告须说明数据类别、受影响记录数、根本原因和遏制措施。"),
                ("事后复盘",
                 "须在 10 个工作日内提交书面事后复盘，并跟踪至关闭。"),
            ]),
            ("第三方供应商评估", [
                ("准入筛查",
                 "处理个人数据的供应商须在签约前通过安全问卷。高风险供应商还需额外接受现场审计。"),
                ("合同控制",
                 "合同必须包含保密条款、24 小时泄露通知条款以及审计权。"),
                ("复评",
                 "评估每 12 个月重复一次；供应商发生安全事件时应立即复评。"),
            ]),
        ],
    },
    "techspec": {
        "en": [
            ("Query Service Level Objectives", [
                ("Latency",
                 "The read path targets a p95 of 800 milliseconds and a p99 of 2 seconds at 50 requests per second. "
                 "Requests exceeding 5 seconds are counted as availability failures."),
                ("Availability",
                 "The service targets 99.9 percent monthly availability measured at the load balancer. "
                 "Planned maintenance windows of up to 4 hours per month are excluded."),
                ("Error budget",
                 "Exceeding the monthly error budget freezes feature releases until the burn rate returns below 1."),
            ]),
            ("Storage Engine Specification", [
                ("Data model",
                 "Rows are partitioned by tenant and ordered by an ingest timestamp. "
                 "Each partition is compacted in the background every 15 minutes."),
                ("Capacity",
                 "A single node holds up to 4 terabytes of compressed data with a 3-replica replication factor."),
                ("Consistency",
                 "Reads are served from the primary replica by default; follower reads lag by at most 2 seconds."),
            ]),
            ("Ingestion API Contract", [
                ("Endpoints",
                 "Batches are accepted at POST /v1/ingest with a maximum payload of 8 megabytes and 1000 records."),
                ("Idempotency",
                 "Every record must carry a client-supplied record id; duplicates within 24 hours are discarded."),
                ("Backpressure",
                 "The API returns 429 with a Retry-After header when the queue depth exceeds 10000 records."),
            ]),
            ("Authentication Token Contract", [
                ("Token format",
                 "Access tokens are signed JWTs carrying a subject, an expiry and a scope list. "
                 "Refresh tokens are opaque strings stored server side."),
                ("Expiry and rotation",
                 "Access tokens expire after 30 minutes; refresh tokens after 14 days and are rotated on every use."),
                ("Failure modes",
                 "An expired token yields 401; a valid token without the required scope yields 403."),
            ]),
        ],
        "zh": [
            ("查询服务等级目标", [
                ("延迟",
                 "读路径在每秒 50 个请求的压力下，p95 目标为 800 毫秒，p99 目标为 2 秒。超过 5 秒的请求计入可用性失败。"),
                ("可用性",
                 "服务以负载均衡器处测量，月度可用性目标为 99.9%。每月不超过 4 小时的计划维护窗口不计入。"),
                ("错误预算",
                 "超出月度错误预算将冻结功能发布，直至消耗速率回到 1 以下。"),
            ]),
            ("存储引擎规格", [
                ("数据模型",
                 "数据行按租户分区，并按摄取时间戳排序。每个分区后台每 15 分钟执行一次合并。"),
                ("容量",
                 "单节点最多承载 4 TB 压缩数据，副本因子为 3。"),
                ("一致性",
                 "默认从主副本读取；从副本读取的延迟最多为 2 秒。"),
            ]),
            ("摄取接口约定", [
                ("接口",
                 "批量数据通过 POST /v1/ingest 提交，单请求最大 8 MB、最多 1000 条记录。"),
                ("幂等",
                 "每条记录必须携带客户端提供的记录标识；24 小时内的重复记录将被丢弃。"),
                ("背压",
                 "当队列深度超过 10000 条记录时，接口返回 429 并附带 Retry-After 头。"),
            ]),
            ("认证令牌约定", [
                ("令牌格式",
                 "访问令牌为签名 JWT，包含主体、过期时间与权限范围列表。刷新令牌为服务端存储的不透明字符串。"),
                ("过期与轮换",
                 "访问令牌 30 分钟后过期；刷新令牌 14 天后过期，且每次使用后轮换。"),
                ("失败语义",
                 "令牌过期返回 401；令牌有效但缺少所需权限返回 403。"),
            ]),
        ],
    },
    "architecture": {
        "en": [
            ("Ingestion Pipeline Design", [
                ("Stages",
                 "The pipeline has four stages: extract, normalise, enrich and publish. "
                 "Each stage is idempotent and may be replayed independently."),
                ("Watermarks",
                 "A per-source watermark advances only after a stage succeeds, so a failure never skips data."),
                ("Failure handling",
                 "Failed batches are retried 3 times with exponential backoff, then routed to a dead-letter store."),
            ]),
            ("Service Topology", [
                ("Components",
                 "The read path consists of an API gateway, a query planner and a storage cluster. "
                 "The write path shares the storage cluster but runs in a separate process pool."),
                ("Isolation",
                 "Read and write paths use separate connection pools so an ingest burst cannot exhaust read capacity."),
                ("Deployment",
                 "Components are deployed as independent containers and roll out one replica at a time."),
            ]),
            ("Cache and Freshness Design", [
                ("Layers",
                 "Two cache layers are used: an exact-match cache with a 300 second TTL, and a semantic cache with a 60 second TTL."),
                ("Invalidation",
                 "Cache entries are invalidated on document version change and on explicit purge calls."),
                ("Observed trade-off",
                 "The semantic cache raises hit rate but can return stale answers; the 60 second TTL bounds staleness."),
            ]),
            ("Observability Architecture", [
                ("Signals",
                 "Three signal types are emitted: structured logs, per-request metrics and distributed traces."),
                ("Correlation",
                 "Every request carries a workflow id that is propagated to all downstream calls and echoed in responses."),
                ("Cost control",
                 "Traces are sampled at 10 percent, while errors are sampled at 100 percent to keep diagnosis possible."),
            ]),
        ],
        "zh": [
            ("摄取流水线设计", [
                ("阶段",
                 "流水线包含四个阶段：抽取、规范化、富化与发布。每个阶段幂等，可独立重放。"),
                ("水位线",
                 "每个数据源的水位线仅在阶段成功之后推进，因此失败不会跳过数据。"),
                ("失败处理",
                 "失败批次以指数退避重试 3 次，随后进入死信存储。"),
            ]),
            ("服务拓扑", [
                ("组件",
                 "读路径由 API 网关、查询规划器和存储集群组成。写路径共用存储集群，但运行在独立进程池。"),
                ("隔离",
                 "读写路径使用独立连接池，避免摄取峰值耗尽读能力。"),
                ("部署",
                 "各组件以独立容器部署，每次滚动更新一个副本。"),
            ]),
            ("缓存与新鲜度设计", [
                ("层级",
                 "使用两层缓存：精确匹配缓存 TTL 为 300 秒，语义缓存 TTL 为 60 秒。"),
                ("失效",
                 "文档版本变更或显式清理调用时，缓存条目失效。"),
                ("权衡",
                 "语义缓存提高命中率，但可能返回过期答案；60 秒 TTL 用于约束过期程度。"),
            ]),
            ("可观测性架构", [
                ("信号类型",
                 "系统输出三类信号：结构化日志、按请求统计的指标和分布式追踪。"),
                ("关联",
                 "每个请求携带工作流标识，该标识会传递到所有下游调用，并在响应中回传。"),
                ("成本控制",
                 "追踪按 10% 采样，而错误按 100% 采样，以保证故障可诊断。"),
            ]),
        ],
    },
}

FAMILIES = tuple(CONTENT.keys())
LANGUAGES = ("en", "zh")


def iter_documents():
    """Yield (family, language, index, title, sections) in a stable, deterministic order."""
    for family in sorted(CONTENT):
        for language in sorted(CONTENT[family]):
            for index, (title, sections) in enumerate(CONTENT[family][language]):
                yield family, language, index, title, sections
