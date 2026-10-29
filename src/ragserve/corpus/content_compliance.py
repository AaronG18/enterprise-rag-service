"""Synthetic corpus content - compliance guides family.

Fully synthetic. Each guide carries concrete obligations (windows, frequencies, thresholds)
because a retrieval system is judged on whether it can return the exact figure a question asks
for, not merely a topically related paragraph.
"""
from __future__ import annotations

from typing import Dict, List, Tuple

COMPLIANCE: Dict[str, Dict[str, Tuple[str, List[Tuple[str, str]]]]] = {
    "data_retention": {
        "en": ("Data Retention Standard", [
            ("Retention windows",
             "Customer records are retained for 7 years after the end of the relationship. "
             "Application logs are retained for 90 days and then deleted."),
            ("Legal hold",
             "A legal hold suspends deletion for the matters it names and is lifted only in "
             "writing by the legal team."),
            ("Deletion evidence",
             "Every deletion run writes a certificate listing the record counts and the "
             "execution timestamp, retained for 3 years."),
        ]),
        "zh": ("数据留存标准", [
            ("留存期限",
             "客户记录在关系结束后留存 7 年。应用日志留存 90 天后删除。"),
            ("法律保全",
             "法律保全会暂停其所指事项的删除，仅由法务团队书面解除。"),
            ("删除凭证",
             "每次删除执行都会生成凭证，列明记录数量与执行时间戳，留存 3 年。"),
        ]),
    },
    "access_review": {
        "en": ("Access Review Procedure", [
            ("Frequency",
             "Privileged access is reviewed quarterly; standard access is reviewed every "
             "6 months. Reviews are due within 10 working days of the review opening."),
            ("Scope",
             "The review covers production databases, administrative consoles and any account "
             "holding the ability to export customer data."),
            ("Evidence",
             "Reviewers must record a decision per account. Accounts with no decision after "
             "15 days are disabled automatically."),
        ]),
        "zh": ("访问权限复核程序", [
            ("频率",
             "特权访问权限每季度复核一次，普通权限每 6 个月复核一次。复核须在开启后 10 个工作日内完成。"),
            ("范围",
             "复核覆盖生产数据库、管理控制台以及任何具备导出客户数据能力的账号。"),
            ("证据",
             "复核人须为每个账号记录决定。超过 15 天无决定的账号将被自动停用。"),
        ]),
    },
    "incident_response": {
        "en": ("Security Incident Response Plan", [
            ("Severity and timing",
             "Severity 1 incidents are declared within 15 minutes of detection and are "
             "communicated to the executive sponsor within 1 hour."),
            ("Roles",
             "Each incident has an incident commander, a communications lead and a technical "
             "lead, named explicitly in the incident channel."),
            ("Post-incident",
             "A written post-incident review is published within 5 working days and lists "
             "corrective actions with owners and due dates."),
        ]),
        "zh": ("安全事件响应计划", [
            ("分级与时效",
             "一级事件在发现后 15 分钟内宣布，并在 1 小时内通报执行层负责人。"),
            ("角色",
             "每起事件设有事件指挥官、沟通负责人和技术负责人，并在事件频道中明确指名。"),
            ("事后",
             "事后评审报告在 5 个工作日内发布，列出纠正措施、责任人与截止日期。"),
        ]),
    },
    "vendor_diligence": {
        "en": ("Vendor Due Diligence Guide", [
            ("Assessment tiers",
             "Vendors processing customer personal data are tier 1 and require a full security "
             "assessment; tier 2 vendors complete a lighter questionnaire."),
            ("Reassessment",
             "Tier 1 vendors are reassessed every 12 months, and immediately after any "
             "subcontractor change affecting data."),
            ("Contract terms",
             "Contracts must include breach notification within 24 hours, an audit right and a "
             "documented data deletion obligation."),
        ]),
        "zh": ("供应商尽职调查指南", [
            ("评估分级",
             "处理客户个人数据的供应商为一级，须完成完整安全评估；二级供应商填写简化问卷。"),
            ("重新评估",
             "一级供应商每 12 个月重新评估一次，并在任何影响数据的分包变更后立即重新评估。"),
            ("合同条款",
             "合同须包含 24 小时内违规通报、审计权以及明确的数据删除义务。"),
        ]),
    },
    "audit_logging": {
        "en": ("Audit Logging Requirements", [
            ("Events to log",
             "Every authentication, permission change, data export and configuration change "
             "must be logged with actor, target, timestamp and outcome."),
            ("Immutability",
             "Audit logs are append-only and are shipped to the log archive within 5 minutes. "
             "Application administrators cannot delete audit records."),
            ("Review",
             "The compliance team samples audit logs monthly and escalates anomalies to the "
             "security lead within 2 working days."),
        ]),
        "zh": ("审计日志要求", [
            ("需记录的事件",
             "每次认证、权限变更、数据导出与配置变更都须记录操作者、对象、时间戳与结果。"),
            ("不可篡改",
             "审计日志仅可追加，并在 5 分钟内传送至日志归档。应用管理员不得删除审计记录。"),
            ("审阅",
             "合规团队每月抽样审阅审计日志，并在 2 个工作日内将异常升级至安全负责人。"),
        ]),
    },
    "pii_handling": {
        "en": ("Personal Data Handling Standard", [
            ("Classification",
             "Personal data is classified as restricted. National identifiers, payment card "
             "numbers and health data are classified as highly restricted."),
            ("In transit and at rest",
             "Restricted data is encrypted in transit with TLS 1.2 or above and at rest with "
             "AES-256. Highly restricted data additionally requires field-level encryption."),
            ("Access requests",
             "Subject access requests are fulfilled within 30 days, and identity must be "
             "verified before any data is disclosed."),
        ]),
        "zh": ("个人数据处理标准", [
            ("分类",
             "个人数据列为受限级。国家标识符、支付卡号与健康数据列为高度受限级。"),
            ("传输与存储",
             "受限数据传输使用 TLS 1.2 及以上加密，存储使用 AES-256。高度受限数据还需字段级加密。"),
            ("访问请求",
             "主体访问请求须在 30 天内完成，且在披露任何数据前必须完成身份验证。"),
        ]),
    },
    "regulatory_reporting": {
        "en": ("Regulatory Reporting Procedure", [
            ("Schedule",
             "The quarterly regulatory return is filed within 20 days of quarter end. The "
             "annual return is filed within 60 days of year end."),
            ("Ownership",
             "Compliance prepares the return, finance reconciles the figures, and the "
             "accountable executive signs before submission."),
            ("Corrections",
             "Material errors in a filed return are corrected within 5 working days of "
             "discovery, with a written explanation to the regulator."),
        ]),
        "zh": ("监管报送程序", [
            ("时间表",
             "季度监管报表在季度结束后 20 天内报送。年度报表在年度结束后 60 天内报送。"),
            ("责任",
             "合规部门编制报表，财务核对数字，由责任高管签署后提交。"),
            ("更正",
             "已报送报表中的重大错误须在发现后 5 个工作日内更正，并向监管机构提交书面说明。"),
        ]),
    },
    "anti_bribery": {
        "en": ("Anti-Bribery and Corruption Policy", [
            ("Prohibited conduct",
             "Offering, promising or accepting anything of value to obtain an improper "
             "advantage is prohibited, directly or through an intermediary."),
            ("Facilitation payments",
             "Facilitation payments are prohibited without exception and must be reported if "
             "demanded."),
            ("Third parties",
             "Agents and consultants acting on behalf of the company must be screened and "
             "bound by equivalent anti-bribery terms."),
        ]),
        "zh": ("反贿赂与反腐败政策", [
            ("禁止行为",
             "禁止直接或经由中介提供、承诺或接受任何有价物以获取不当利益。"),
            ("通融费",
             "通融费一律禁止；若被索要，必须上报。"),
            ("第三方",
             "代表公司行事的代理与顾问须经过筛查，并受同等反贿赂条款约束。"),
        ]),
    },
    "export_control": {
        "en": ("Export Control and Sanctions Policy", [
            ("Screening",
             "Counterparties are screened against the sanctions list before contracting and "
             "again before each shipment."),
            ("Restricted technology",
             "Encryption software and high-performance computing hardware are controlled items "
             "and require classification before export."),
            ("Records",
             "Classification decisions and licences are retained for 5 years and are available "
             "for audit on request."),
        ]),
        "zh": ("出口管制与制裁政策", [
            ("筛查",
             "合作方在签约前以及每次发货前均须对照制裁名单进行筛查。"),
            ("受限技术",
             "加密软件与高性能计算硬件属于管制物项，出口前须完成分类。"),
            ("记录",
             "分类决定与许可证留存 5 年，并可应审计要求提供。"),
        ]),
    },
    "records_management": {
        "en": ("Records Management Policy", [
            ("Definition of a record",
             "A record is any information created or received in the course of business that "
             "evidences a decision, obligation or transaction."),
            ("Storage",
             "Records are stored in the designated repository; personal copies in mailboxes or "
             "local drives are not records and are deleted on exit."),
            ("Disposal",
             "Records are disposed of according to the retention schedule, and disposal is "
             "logged with the record class and date."),
        ]),
        "zh": ("记录管理政策", [
            ("记录的定义",
             "记录是业务过程中产生或接收、能够证明决定、义务或交易的任何信息。"),
            ("存储",
             "记录存放在指定存储库；邮箱或本地磁盘中的个人副本不属于记录，离职时删除。"),
            ("处置",
             "记录按留存计划处置，处置时记录记录类别与日期。"),
        ]),
    },
}


def compliance_documents() -> List[Tuple[str, str, str, List[Tuple[str, str]]]]:
    out: List[Tuple[str, str, str, List[Tuple[str, str]]]] = []
    for _topic, by_language in COMPLIANCE.items():
        for language in ("en", "zh"):
            title, sections = by_language[language]
            out.append(("compliance", language, title, sections))
    return out
