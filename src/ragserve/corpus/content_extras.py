"""Additional closing section per topic: exceptions, escalation or related provisions.

Why this is a separate module: the main content modules hold the substance of each topic, and
this one adds the fourth section that real policy and specification documents almost always
carry - who decides the exception, where an issue is escalated, or what adjacent rule applies.
It also makes documents long enough that chunking with overlap is genuinely exercised: without
it, half the corpus was a single chunk.
"""
from __future__ import annotations

from typing import Dict, Tuple

# topic -> language -> (heading, body)
EXTRAS: Dict[str, Dict[str, Tuple[str, str]]] = {
    "annual_leave": {
        "en": ("Exceptions",
               "Unused entitlement above the carry-over cap is forfeited unless the employee was "
               "unable to take leave due to certified illness. Managers may approve unpaid leave "
               "of up to 10 days where entitlement is exhausted."),
        "zh": ("例外",
               "超过结转上限的未休假额度将被作废，但因出具证明的疾病而无法休假者除外。"
               "额度用尽时，主管可批准最多 10 天无薪假期。"),
    },
    "remote_work": {
        "en": ("Exceptions and review",
               "Exceptions for roles excluded from remote work are reviewed annually by the "
               "department head. Persistent connectivity failures are treated as a facilities "
               "issue, not a performance issue."),
        "zh": ("例外与复核",
               "被排除在远程办公之外的岗位例外由部门负责人每年复核一次。"
               "持续性连接故障按设施问题处理，而非绩效问题。"),
    },
    "expenses": {
        "en": ("Exceptions",
               "Late claims are accepted up to 60 days with a written justification from the "
               "budget owner. Disputed lines are escalated to finance, whose decision is final."),
        "zh": ("例外",
               "经预算负责人书面说明，最迟可在 60 天内受理逾期报销。"
               "有争议的明细升级至财务，其决定为最终决定。"),
    },
    "performance": {
        "en": ("Appeals",
               "An employee may request a review of their rating within 10 working days of "
               "release. The appeal is heard by the manager's manager and one peer manager."),
        "zh": ("申诉",
               "员工可在结果发布后 10 个工作日内申请复核评级。申诉由上级的上级与一名同级主管共同听审。"),
    },
    "onboarding": {
        "en": ("Early departure",
               "If either side ends the relationship during probation, equipment is returned "
               "within 3 working days and system access is revoked the same day."),
        "zh": ("提前结束",
               "试用期内任一方终止关系时，设备须在 3 个工作日内归还，系统权限当日撤销。"),
    },
    "learning": {
        "en": ("Exceptions",
               "Unused budget does not carry into the following year. Mandatory compliance "
               "training is funded separately and does not consume the learning budget."),
        "zh": ("例外",
               "未使用的预算不结转至次年。强制性合规培训另行出资，不占用学习预算。"),
    },
    "parental_leave": {
        "en": ("Related provisions",
               "Parental leave runs concurrently with statutory entitlements rather than in "
               "addition to them. Pension contributions continue at the normal rate during leave."),
        "zh": ("相关条款",
               "育儿假与法定假期并行计算，而非在其之外叠加。假期期间养老金缴款按正常比例继续。"),
    },
    "business_travel": {
        "en": ("Escalation",
               "Travel disrupted by an unplanned event is escalated to the duty manager, who "
               "authorises alternative arrangements and any additional cost."),
        "zh": ("升级",
               "因突发情况受阻的差旅升级至值班经理，由其批准替代方案及任何额外费用。"),
    },
    "conduct": {
        "en": ("Investigation",
               "Alleged breaches are investigated by compliance within 20 working days. Where a "
               "breach is substantiated, disciplinary action follows the standard process."),
        "zh": ("调查",
               "涉嫌违规由合规部门在 20 个工作日内调查。违规成立的，按标准流程进行纪律处分。"),
    },
    "health_safety": {
        "en": ("Escalation",
               "Any life-threatening situation is escalated immediately to emergency services "
               "before the internal reporting chain is used."),
        "zh": ("升级",
               "任何危及生命的情况须立即升级至急救服务，然后再走内部报告链路。"),
    },

    "data_retention": {
        "en": ("Exceptions",
               "Backups are retained for 35 days for operational recovery and are not used to "
               "satisfy subject requests. Retention may be shortened where a lawful basis is "
               "recorded by the legal team."),
        "zh": ("例外",
               "备份为运营恢复留存 35 天，不用于满足主体请求。法务团队记录合法依据时可缩短留存期。"),
    },
    "access_review": {
        "en": ("Escalation",
               "Accounts belonging to leavers are disabled on the exit date, and any access that "
               "survives 24 hours past exit is escalated to the security lead."),
        "zh": ("升级",
               "离职人员的账号在离职当日停用；离职后超过 24 小时仍存续的权限升级至安全负责人。"),
    },
    "incident_response": {
        "en": ("Severity definitions",
               "Severity 1 means confirmed loss or exposure of customer data, or a complete "
               "outage. Severity 2 means degraded service with a workaround in place."),
        "zh": ("分级定义",
               "一级指客户数据确认丢失或泄露，或整体中断。二级指服务降级但存在可用的绕行方案。"),
    },
    "vendor_diligence": {
        "en": ("Exceptions",
               "A vendor may be engaged before assessment completes only with a documented risk "
               "acceptance valid for 90 days and signed by the accountable executive."),
        "zh": ("例外",
               "仅在有经责任高管签署、有效期 90 天的书面风险接受文件时，方可在评估完成前启用供应商。"),
    },
    "audit_logging": {
        "en": ("Clock and integrity",
               "Log timestamps use coordinated universal time with the offset recorded, and a "
               "daily checksum of the previous day's log is stored separately."),
        "zh": ("时钟与完整性",
               "日志时间戳使用协调世界时并记录偏移量；前一日日志的每日校验和另行存储。"),
    },
    "pii_handling": {
        "en": ("Exceptions",
               "Personal data may be processed outside the primary region only with a recorded "
               "transfer assessment and the data subject categories listed."),
        "zh": ("例外",
               "个人数据仅在完成书面传输评估并列出数据主体类别后，方可在主区域以外处理。"),
    },
    "regulatory_reporting": {
        "en": ("Escalation",
               "A return that cannot be filed by the deadline is escalated to the accountable "
               "executive on the day before the deadline, with a draft attached."),
        "zh": ("升级",
               "无法按期报送的报表须在截止日前一天升级至责任高管，并附上草稿。"),
    },
    "anti_bribery": {
        "en": ("Reporting",
               "Suspected bribery is reported to the compliance lead within 24 hours, and no "
               "payment may be made while the suspicion is open."),
        "zh": ("报告",
               "疑似贿赂须在 24 小时内报告合规负责人；在嫌疑未澄清前不得支付任何款项。"),
    },
    "export_control": {
        "en": ("Escalation",
               "A potential match against the sanctions list is escalated to legal before any "
               "goods, software or technical data are released."),
        "zh": ("升级",
               "与制裁名单存在潜在匹配时，须在任何货物、软件或技术数据放行前升级至法务。"),
    },
    "records_management": {
        "en": ("Related provisions",
               "Draft material is not a record unless it is circulated for decision. Where a "
               "decision is recorded only in chat, the decision is copied to the repository."),
        "zh": ("相关条款",
               "草稿材料不属于记录，除非为作出决定而传阅。仅在聊天中记录的决定须抄录至存储库。"),
    },

    "ingestion_api": {
        "en": ("Failure handling",
               "A batch that fails validation is rejected entirely rather than partially, so a "
               "caller never has to reconcile which documents landed."),
        "zh": ("失败处理",
               "校验失败的批次整体拒绝而非部分接收，调用方无需核对哪些文档已落地。"),
    },
    "query_service": {
        "en": ("Degradation",
               "When generation exceeds its budget the request returns a refusal rather than a "
               "partial answer, because an incomplete answer reads as a complete one."),
        "zh": ("降级",
               "当生成超出预算时，请求返回拒答而非部分答案，因为不完整的答案会被读成完整答案。"),
    },
    "embedding_pipeline": {
        "en": ("Operational notes",
               "Vectorisation runs on the calling thread during index build, which is why index "
               "build time is reported on startup rather than assumed."),
        "zh": ("运维说明",
               "向量化在索引构建期间运行于调用线程，因此索引构建时间在启动时实测报告而非假设。"),
    },
    "cache_layer": {
        "en": ("Poisoning guards",
               "Refusals are never cached, and a semantic entry is written only after the answer "
               "passes the same quality checks used in evaluation."),
        "zh": ("污染防护",
               "拒答结果一律不缓存；语义层条目仅在答案通过评估所用的同等质量校验后写入。"),
    },
    "auth_service": {
        "en": ("Operational notes",
               "Key rotation is supported with two active keys for 24 hours so that rotation "
               "never causes an outage."),
        "zh": ("运维说明",
               "密钥轮换支持 24 小时内两把密钥同时有效，因此轮换不会造成中断。"),
    },
    "event_bus": {
        "en": ("Poison messages",
               "A message that fails five times is moved to a dead-letter topic and is inspected "
               "weekly rather than retried indefinitely."),
        "zh": ("毒消息",
               "失败 5 次的消息转入死信主题并每周检查，而非无限重试。"),
    },
    "storage_engine": {
        "en": ("Operational notes",
               "Writes are atomic: a temporary file is written and then renamed, so a concurrent "
               "reader never observes a half-written artefact."),
        "zh": ("运维说明",
               "写入是原子的：先写临时文件再重命名，因此并发读取者不会看到写了一半的产物。"),
    },
    "observability_stack": {
        "en": ("Cost control",
               "High-cardinality fields such as chunk identifiers are recorded in logs only, not "
               "as metric labels, to keep metric cost bounded."),
        "zh": ("成本控制",
               "块标识等高基数字段仅记录在日志中，不作为指标标签，以控制指标成本。"),
    },
    "deployment_pipeline": {
        "en": ("Gates",
               "The contract stage blocks a merge when any required check fails, and no check may "
               "be skipped by the repository owner."),
        "zh": ("门禁",
               "任一必需检查失败时契约阶段即阻止合并，且仓库负责人不得跳过任何检查。"),
    },
    "rate_limiting": {
        "en": ("Exceptions",
               "Internal health checks bypass the limit, and a tenant may request a temporary "
               "increase for a planned batch with 3 working days notice."),
        "zh": ("例外",
               "内部健康检查不受限；租户可就计划批次提前 3 个工作日申请临时提额。"),
    },

    "multitenant": {
        "en": ("Related decisions",
               "Tenant configuration is versioned with the corpus, so a configuration change and "
               "a corpus change cannot be applied half-and-half."),
        "zh": ("相关决策",
               "租户配置与语料一同版本化，因此配置变更与语料变更不会出现各应用一半的情况。"),
    },
    "retrieval_pipeline": {
        "en": ("Operational notes",
               "Retrieval mode and reranking are read from configuration at service start, which "
               "is what makes the comparison between configurations a configuration change only."),
        "zh": ("运维说明",
               "检索模式与重排在服务启动时从配置读取，这正是配置间对比只需改配置即可完成的原因。"),
    },
    "scaling": {
        "en": ("Trigger to revisit",
               "The design is revisited when measured p95 approaches half the latency budget on "
               "a single instance, not when traffic merely grows."),
        "zh": ("重新评估的触发条件",
               "当单实例实测 p95 接近延迟预算的一半时重新评估设计，而非仅在流量增长时评估。"),
    },
    "failure_modes": {
        "en": ("Related decisions",
               "Every failure path emits a distinct reason code, so a spike in refusals can be "
               "attributed to a cause rather than observed as a rate."),
        "zh": ("相关决策",
               "每条失败路径发出独立的理由码，因此拒答上升可归因到具体原因，而不只是一个比率。"),
    },
    "data_flow": {
        "en": ("Operational notes",
               "Chunk identifiers are stamped into every response, so an answer can be traced to "
               "the exact passage it came from after the fact."),
        "zh": ("运维说明",
               "块标识写入每个响应，因此答案事后可追溯到其来源的具体段落。"),
    },
    "deployment_topology": {
        "en": ("Related decisions",
               "Promoting the same artefact between environments is preferred over rebuilding, "
               "because a rebuild can differ without any source change being visible."),
        "zh": ("相关决策",
               "倾向于在环境间晋级同一产物而非重建，因为重建可能产生无任何源码变更可见的差异。"),
    },
    "security_architecture": {
        "en": ("Operational notes",
               "Redaction runs at emit time, so an unredacted value never exists in the log "
               "pipeline at all, rather than being scrubbed later."),
        "zh": ("运维说明",
               "脱敏在发出时执行，因此未脱敏的值根本不存在于日志流水线中，而非事后清除。"),
    },
    "cost_model": {
        "en": ("Related decisions",
               "Cost is reported per thousand calls rather than per call, because per-call figures "
               "invite false precision at this scale."),
        "zh": ("相关决策",
               "成本按每千次调用而非每次调用报告，因为此规模下按次报告会造成虚假精度。"),
    },
    "migration_plan": {
        "en": ("Related decisions",
               "The shadow evaluation reuses the labelled set rather than live traffic, so a "
               "promotion decision is made on repeatable evidence."),
        "zh": ("相关决策",
               "影子评估复用标注集而非实时流量，因此晋级决定基于可复复现的证据。"),
    },
    "decision_log": {
        "en": ("Related decisions",
               "Each decision records the alternative considered and the condition under which the "
               "decision would be reversed."),
        "zh": ("相关决策",
               "每项决策记录所考虑的备选方案，以及在何种条件下该决策会被推翻。"),
    },
}
