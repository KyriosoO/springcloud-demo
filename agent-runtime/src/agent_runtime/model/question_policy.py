from __future__ import annotations

import re
import unicodedata

from agent_runtime.model.contracts import QuestionDataClass


QUESTION_EGRESS_POLICY_VERSION = "question-egress-v1"

_WHITESPACE = re.compile(r"\s+")
_JWT = re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}(?:\.[A-Za-z0-9_-]{8,})?\b")
_API_KEY = re.compile(r"(?i)(?:sk-[A-Za-z0-9_-]{12,}|api[_ -]?key\s*[:=]\s*\S+|bearer\s+\S+)")
_PRIVATE_KEY = re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")
_PASSWORD = re.compile(r"(?i)(?:password|passwd|密码|口令|secret)\s*[:=：]\s*\S+")
_PROMPT_INJECTION = re.compile(
    r"(?i)(?:ignore (?:all |the )?(?:previous|above) instructions|system prompt|developer message|"
    r"忽略(?:之前|以上|所有)?(?:指令|规则)|系统提示词|扮演(?:系统|管理员)|越过(?:权限|规则))"
)
_CHINESE_ID = re.compile(r"(?<!\d)\d{17}[0-9Xx](?!\d)")
_PHONE = re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)")
_EMAIL = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
_EMPLOYEE_ID = re.compile(r"(?:员工编号|工号|employee\s*id)\s*[:=：#]?\s*[A-Za-z0-9_-]{2,}", re.IGNORECASE)
_TRANSACTION_ID = re.compile(r"(?:交易号|流水号|transaction\s*id)\s*[:=：#]?\s*[A-Za-z0-9_-]{4,}", re.IGNORECASE)
_FINANCIAL_ACCOUNT = re.compile(r"(?:银行卡|银行账户|账号|account)\s*[:=：#]?\s*\d{6,}", re.IGNORECASE)
_FREE_TEXT_SENSITIVE = re.compile(r"(?:病历|病史|家庭住址|薪资明细|绩效评价|征信记录)")
_PUBLIC_KNOWLEDGE = re.compile(r"(?:税|纳税|发票|法律|法规|政策|条例|司法解释|行政规定)")
_GENERIC_BUSINESS = re.compile(
    r"^(?:查询|查看|了解)?(?:员工列表|员工查询|交易记录|交易查询)(?:支持|允许|可以使用|有哪些)(?:哪些|什么)?(?:条件|字段|时间范围|筛选项|查询项)[？?。]?$"
)


DENY_CLASSES = frozenset(
    {
        QuestionDataClass.PERSONAL_IDENTIFIER,
        QuestionDataClass.EMPLOYEE_IDENTIFIER,
        QuestionDataClass.TRANSACTION_IDENTIFIER,
        QuestionDataClass.FINANCIAL_ACCOUNT,
        QuestionDataClass.CONTACT,
        QuestionDataClass.CREDENTIAL_OR_SECRET,
        QuestionDataClass.INSTRUCTION_INJECTION,
        QuestionDataClass.FREE_TEXT_SENSITIVE,
        QuestionDataClass.UNKNOWN,
    }
)


def normalize_question(question: str) -> str:
    normalized = unicodedata.normalize("NFC", question)
    return _WHITESPACE.sub(" ", normalized.strip())


def contains_forbidden_control(question: str) -> bool:
    return any(
        character == "\x00"
        or (unicodedata.category(character) in {"Cc", "Cf"} and not character.isspace())
        for character in question
    )


def classify_question(question: str) -> frozenset[QuestionDataClass]:
    classes: set[QuestionDataClass] = set()
    if _JWT.search(question) or _API_KEY.search(question) or _PRIVATE_KEY.search(question) or _PASSWORD.search(question):
        classes.add(QuestionDataClass.CREDENTIAL_OR_SECRET)
    if _PROMPT_INJECTION.search(question):
        classes.add(QuestionDataClass.INSTRUCTION_INJECTION)
    if _CHINESE_ID.search(question):
        classes.add(QuestionDataClass.PERSONAL_IDENTIFIER)
    if _PHONE.search(question) or _EMAIL.search(question):
        classes.add(QuestionDataClass.CONTACT)
    if _EMPLOYEE_ID.search(question):
        classes.add(QuestionDataClass.EMPLOYEE_IDENTIFIER)
    if _TRANSACTION_ID.search(question):
        classes.add(QuestionDataClass.TRANSACTION_IDENTIFIER)
    if _FINANCIAL_ACCOUNT.search(question):
        classes.add(QuestionDataClass.FINANCIAL_ACCOUNT)
    if _FREE_TEXT_SENSITIVE.search(question):
        classes.add(QuestionDataClass.FREE_TEXT_SENSITIVE)
    if _PUBLIC_KNOWLEDGE.search(question):
        classes.add(QuestionDataClass.PUBLIC_KNOWLEDGE)
    if _GENERIC_BUSINESS.fullmatch(question):
        classes.add(QuestionDataClass.GENERIC_BUSINESS)
    if not classes:
        classes.add(QuestionDataClass.UNKNOWN)
    return frozenset(classes)

