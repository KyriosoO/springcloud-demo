from __future__ import annotations

import re

from agent_runtime.knowledge.contracts import (
    LogicalDomainCatalog,
    LogicalKnowledgeDomain,
    RetrievalPath,
)
from agent_runtime.knowledge.errors import KnowledgeConfigurationError

CATALOG_VERSION = "tax-domain-catalog-v2"
TAX_ANCHORS = ("税", "税务", "税收", "纳税", "增值税", "所得税", "企业所得税", "个人所得税", "发票")
STRONG_POLICY_TERMS = ("政策", "公告", "通知", "指引", "口径", "征管", "实施")
WEAK_POLICY_TERMS = ("优惠",)
POLICY_TERMS = STRONG_POLICY_TERMS + WEAK_POLICY_TERMS
INDEPENDENT_POLICY_TERMS = ("政策", "公告", "通知", "指引", "口径")
LAW_TERMS = ("税法", "法律", "法规", "条例", "司法解释", "法条", "违法", "处罚", "征管法", "征收管理法")
ARTICLE_PATTERN = r"第[零〇一二三四五六七八九十百千万0-9]{1,12}(条|款|项)"


def build_tax_domain_catalog() -> LogicalDomainCatalog:
    domains = (
        LogicalKnowledgeDomain(
            domain_id="tax.policy",
            display_name="税务政策",
            order=10,
            anchor_terms=TAX_ANCHORS,
            classifier_terms=POLICY_TERMS,
            classifier_pattern=None,
            allowed_paths=(RetrievalPath.KEYWORD, RetrievalPath.VECTOR),
            default_egress_policy_ref="knowledge.egress.tax_policy.v1",
        ),
        LogicalKnowledgeDomain(
            domain_id="tax.law",
            display_name="税收法律",
            order=20,
            anchor_terms=TAX_ANCHORS,
            classifier_terms=LAW_TERMS,
            classifier_pattern=ARTICLE_PATTERN,
            allowed_paths=(RetrievalPath.KEYWORD, RetrievalPath.VECTOR),
            default_egress_policy_ref="knowledge.egress.tax_law.v1",
        ),
    )
    if len({item.domain_id for item in domains}) != len(domains):
        raise KnowledgeConfigurationError("knowledge.catalog_invalid")
    if any(item.allowed_paths != (RetrievalPath.KEYWORD, RetrievalPath.VECTOR) for item in domains):
        raise KnowledgeConfigurationError("knowledge.catalog_invalid")
    for item in domains:
        if item.classifier_pattern is not None:
            re.compile(item.classifier_pattern)
    return LogicalDomainCatalog(version=CATALOG_VERSION, domains=domains)
