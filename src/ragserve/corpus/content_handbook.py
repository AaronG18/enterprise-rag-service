"""Synthetic corpus content - employee handbook family.

Fully synthetic, no third-party or internal material (RULES R6). Content is literal rather than
randomly assembled word soup: retrieval quality depends on passages that read like real policy
text and carry concrete figures a question can ask for.

Every topic exists in EN and ZH with the same facts, so bilingual retrieval is a fair test
rather than two different corpora.
"""
from __future__ import annotations

from typing import Dict, List, Tuple

# topic -> language -> (title, [(heading, body), ...])
# A fourth section per topic is appended from `content_extras` by `iter_documents()`.
HANDBOOK: Dict[str, Dict[str, Tuple[str, List[Tuple[str, str]]]]] = {
    "annual_leave": {
        "en": ("Annual Leave Policy", [
            ("Entitlement",
             "Full-time employees accrue 15 working days of paid annual leave per calendar year. "
             "Part-time employees accrue leave pro rata based on contracted hours, rounded up to "
             "the nearest half day."),
            ("Carry-over",
             "Up to 5 unused days may be carried into the next calendar year. Carried-over days "
             "expire on 31 March and are not paid out on departure."),
            ("Request process",
             "Leave of more than 3 consecutive days requires line-manager approval at least 10 "
             "working days in advance. Requests are submitted through the people portal, which "
             "records the approval decision."),
        ]),
        "zh": ("年假政策", [
            ("额度",
             "全职员工每个日历年享有 15 个工作日带薪年假。兼职员工按合同工时按比例折算，"
             "不足半日按半日计。"),
            ("结转",
             "未使用的年假最多可结转 5 天至下一个日历年。结转的假期于 3 月 31 日失效，"
             "离职时不折现。"),
            ("申请流程",
             "连续超过 3 天的假期需提前 10 个工作日获得直属主管批准。申请通过人事门户提交，"
             "系统记录审批结果。"),
        ]),
    },
    "remote_work": {
        "en": ("Remote Work Policy", [
            ("Eligibility",
             "Employees may work remotely up to 3 days per week after completing a 90-day "
             "onboarding period. Roles requiring physical access to production hardware are "
             "excluded."),
            ("Equipment and allowance",
             "The company provides a laptop and a one-off home-office allowance of 250 units. "
             "Replacement cycles follow the standard 3-year hardware refresh."),
            ("Expectations",
             "Remote workers must be reachable during core hours of 10:00 to 16:00 local time. "
             "Teams must keep a written record of which days each member works on site."),
        ]),
        "zh": ("远程办公政策", [
            ("适用条件",
             "员工完成 90 天入职期后，每周最多可远程办公 3 天。需要现场接触生产硬件的岗位除外。"),
            ("设备与补贴",
             "公司提供笔记本电脑以及一次性 250 单位家庭办公补贴。设备更换遵循 3 年标准更新周期。"),
            ("工作要求",
             "远程办公员工须在当地时间 10:00 至 16:00 的核心时段保持可联系。"
             "团队须书面记录每位成员的现场办公日期。"),
        ]),
    },
    "expenses": {
        "en": ("Expense Reimbursement Policy", [
            ("Limits",
             "Travel and subsistence claims must be submitted within 30 days of the expense date. "
             "Claims above 500 units require a second approver."),
            ("Receipts",
             "Itemised receipts are required for every claim line. Missing receipts may be "
             "replaced by a signed declaration once per quarter."),
            ("Payment timing",
             "Approved claims are paid in the payroll run following approval, normally within "
             "14 days. Rejected lines are returned with a stated reason."),
        ]),
        "zh": ("费用报销政策", [
            ("限额",
             "差旅与食宿费用须在费用发生之日起 30 天内提交。超过 500 单位的报销需第二审批人。"),
            ("票据",
             "每一条报销明细都需提供逐项票据。缺失票据每季度可用一次签署声明替代。"),
            ("付款时间",
             "已批准的报销在批准后的工资发放周期内支付，通常为 14 天内。被驳回的明细会附理由退回。"),
        ]),
    },
    "performance": {
        "en": ("Performance Review Policy", [
            ("Cadence",
             "Formal reviews run twice a year, in June and December, covering the preceding "
             "6 months. New joiners receive a lighter review after their first 90 days."),
            ("Ratings",
             "Reviews use four ratings: needs improvement, meets expectations, exceeds "
             "expectations, outstanding. A written rationale is mandatory for the top and "
             "bottom ratings."),
            ("Calibration",
             "Managers calibrate ratings in cross-team sessions before results are released, so "
             "that the distribution stays comparable across departments."),
        ]),
        "zh": ("绩效评估政策", [
            ("周期",
             "正式评估每年两次，分别在 6 月和 12 月，覆盖前 6 个月。新入职员工在首个 90 天后"
             "进行一次简化评估。"),
            ("等级",
             "评估使用四个等级：待改进、符合预期、超出预期、杰出。最高与最低等级必须附书面理由。"),
            ("校准",
             "结果发布前，主管在跨团队会议中对等级进行校准，以保证各部门之间的分布可比。"),
        ]),
    },
    "onboarding": {
        "en": ("Onboarding and Probation Policy", [
            ("First week",
             "New joiners complete identity verification, equipment collection and security "
             "awareness training within their first 5 working days."),
            ("Probation",
             "The probationary period is 6 months. During probation the notice period is "
             "1 week on either side."),
            ("Buddy and checkpoints",
             "Each new joiner is assigned a buddy for the first 30 days, and the manager holds "
             "checkpoints at day 30, day 60 and day 90."),
        ]),
        "zh": ("入职与试用期政策", [
            ("第一周",
             "新员工须在入职后 5 个工作日内完成身份验证、设备领取与安全意识培训。"),
            ("试用期",
             "试用期为 6 个月。试用期内双方的通知期均为 1 周。"),
            ("伙伴与检查点",
             "每位新员工在前 30 天配有一名伙伴，主管在第 30、60、90 天各进行一次检查点沟通。"),
        ]),
    },
    "learning": {
        "en": ("Learning and Development Policy", [
            ("Budget",
             "Each employee has an annual learning budget of 1200 units, usable for courses, "
             "conferences and books."),
            ("Study time",
             "Up to 4 hours per week may be spent on learning during working hours, subject to "
             "delivery commitments."),
            ("Certifications",
             "Certifications relevant to the role are reimbursed in full on passing. "
             "Examination resits are reimbursed once."),
        ]),
        "zh": ("学习与发展政策", [
            ("预算",
             "每位员工每年有 1200 单位学习预算，可用于课程、会议与书籍。"),
            ("学习时间",
             "在不影响交付的前提下，每周可用最多 4 小时工作时间用于学习。"),
            ("认证",
             "与岗位相关的认证在通过后全额报销。考试重考可报销一次。"),
        ]),
    },
    "parental_leave": {
        "en": ("Parental Leave Policy", [
            ("Entitlement",
             "Primary carers receive 16 weeks of paid leave; secondary carers receive 4 weeks. "
             "Leave may be taken in up to 3 blocks within the first year."),
            ("Notice",
             "Notice of 8 weeks is required before the intended start date, with the expected "
             "date confirmed in writing."),
            ("Return to work",
             "Returning employees may request a phased return at 60 percent of contracted hours "
             "for the first 4 weeks."),
        ]),
        "zh": ("育儿假政策", [
            ("额度",
             "主要照护人享有 16 周带薪假期，次要照护人享有 4 周。假期可在首年内分最多 3 段使用。"),
            ("通知",
             "须在计划开始日期前 8 周通知，并以书面形式确认预计日期。"),
            ("返岗",
             "返岗员工可申请在前 4 周按合同工时的 60% 逐步恢复工作。"),
        ]),
    },
    "business_travel": {
        "en": ("Business Travel Policy", [
            ("Approval",
             "All travel requires approval at least 7 days before departure. Travel to a high-risk "
             "destination additionally requires security sign-off."),
            ("Bookings and caps",
             "Flights of more than 6 hours may be booked in premium economy. Hotel spend is capped "
             "at 180 units per night in major cities."),
            ("Insurance and duty of care",
             "Travellers are covered by the corporate travel insurance policy and must register "
             "their itinerary in the travel register before departure."),
        ]),
        "zh": ("差旅政策", [
            ("审批",
             "所有差旅须在出发前至少 7 天获得批准。前往高风险目的地的差旅还需安全部门签核。"),
            ("预订与上限",
             "飞行时间超过 6 小时可预订超级经济舱。主要城市住宿每晚上限 180 单位。"),
            ("保险与照护责任",
             "出差人员受公司差旅保险保障，须在出发前将行程登记到差旅登记表。"),
        ]),
    },
    "conduct": {
        "en": ("Code of Conduct", [
            ("Standards",
             "Employees act with integrity, avoid conflicts of interest, and treat colleagues and "
             "customers with respect regardless of role or location."),
            ("Gifts and hospitality",
             "Gifts above 50 units must be declared in the gifts register. Cash and cash "
             "equivalents may never be accepted."),
            ("Speaking up",
             "Concerns may be raised with a manager, with compliance, or anonymously through the "
             "speak-up line. Retaliation for raising a concern is itself a breach."),
        ]),
        "zh": ("行为准则", [
            ("标准",
             "员工须诚信行事、避免利益冲突，并尊重同事与客户，无论岗位或地点。"),
            ("礼品与招待",
             "超过 50 单位的礼品须登记到礼品登记册。现金及现金等价物一律不得接受。"),
            ("提出关切",
             "关切可向主管、合规部门提出，或通过匿名举报热线反映。因提出关切而遭到报复本身即属违规。"),
        ]),
    },
    "health_safety": {
        "en": ("Health and Safety Policy", [
            ("Workplace",
             "Each office maintains a fire warden rota and runs an evacuation drill every "
             "6 months. First-aid kits are inspected quarterly."),
            ("Incident reporting",
             "Any injury, near miss or unsafe condition must be reported within 24 hours, "
             "including incidents with no lost time."),
            ("Display equipment",
             "Employees using display equipment are entitled to a workstation assessment and to "
             "an eye test every 24 months."),
        ]),
        "zh": ("健康与安全政策", [
            ("工作场所",
             "各办公室维护消防员轮值表，并每 6 个月进行一次疏散演练。急救箱每季度检查一次。"),
            ("事件报告",
             "任何伤害、险情或不安全状况须在 24 小时内上报，包括未造成工时损失的事件。"),
            ("显示设备",
             "使用显示设备的员工有权获得工位评估，并每 24 个月进行一次视力检查。"),
        ]),
    },
}


def handbook_documents() -> List[Tuple[str, str, str, List[Tuple[str, str]]]]:
    """Flatten to (family, language, title, sections), ordered by topic then language."""
    out: List[Tuple[str, str, str, List[Tuple[str, str]]]] = []
    for _topic, by_language in HANDBOOK.items():
        for language in ("en", "zh"):
            title, sections = by_language[language]
            out.append(("handbook", language, title, sections))
    return out
