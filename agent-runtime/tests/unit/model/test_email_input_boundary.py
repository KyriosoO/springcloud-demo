"""CONTACT remains denied even without spaces around an ASCII email."""
import pytest

from agent_runtime.model.input_guard import QuestionEgressGuard
from agent_runtime.model.contracts import QuestionDataClass, QuestionEgressDisposition
from agent_runtime.model.question_policy import classify_question


@pytest.mark.parametrize("question", [
    "税务问题，邮箱someone@example.com", "someone@example.com的税务问题", "税务someone@example.com问题",
    "税务someone+tag@sub.example.com问题", "税务 someone@example.com 问题", "税务（someone@example.com）",
    "税务someone@example.com.", "税务someone@example.com。", "税务someone@example.com,后续条件",
    "税务someone@example.com;", "税务someone@example.com!", "税务someone@example.com?",
])
def test_contact_class_and_both_guards_deny_chinese_adjacent_email(question):
    assert QuestionDataClass.CONTACT in classify_question(question)
    assert QuestionEgressGuard().evaluate(question).disposition is QuestionEgressDisposition.DENIED
    assert QuestionEgressGuard().evaluate_business("员工查询，" + question).disposition is QuestionEgressDisposition.DENIED


@pytest.mark.parametrize("question", ["现行增值税政策", "税率为6%", "税务邮箱服务适用规则", "税务电子邮件服务定义"])
def test_no_contact_value_does_not_expand_denial_to_topics(question):
    assert QuestionDataClass.CONTACT not in classify_question(question)
    assert QuestionEgressGuard().evaluate(question).disposition is QuestionEgressDisposition.ALLOWED
