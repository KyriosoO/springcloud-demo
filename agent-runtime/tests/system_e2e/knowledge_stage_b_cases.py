"""Manually audited public-source gold; NEVER imported by online ranking."""
from __future__ import annotations

# Source inspection: immutable Stage A chunks, and read-only ES IDs. These are
# clause-presence/usefulness checks, not a claim about all current tax advice.
GOLD = {
    "lodging": {"chunk": "chunk-a099c95f4e5cc6fa034a6aac0c4ededf", "sha256": "f75587a18625412be4019c6f534ecf6ddfe133fd968984ce75406200cb77ebde", "clause": "住宿服务，是指提供住宿场所及配套服务等的活动。"},
    "living": {"chunk": "chunk-d901c3f6395113b9dc1fd0ef7b748236", "sha256": "6b845e33a7a53777961b871707601c8dec674cc8e7243a0a823ae2fd80a28d2a", "clause": "餐饮住宿服务"},
    "law_rate": {"chunk": "tax-ed86dea9630deb65973c6bb2#d0001", "sha256": "c0a21ef606eed5e4536e886f6bdb83fd7eb619fcae3d58b5126bfc3d92a5c58e", "clause": "税率为百分之六"},
    "law_effective": {"chunk": "tax-ed86dea9630deb65973c6bb2#d0005", "sha256": "a4206f5102c3ba63d4abb86178047453e8e8972c74beaa4f55c1f460c3aec426", "clause": "本法自2026年1月1日起施行"},
    "rent": {"chunk": "chunk-ceaf416255c52a326b13ef40fe81f8b9", "sha256": "7b9d059827d126d52aba25b64e5925938999f2423ca3fc9fef144b518dc37c4e", "clause": "经营租赁服务可分为有形动产经营租赁服务和不动产经营租赁服务"},
    "historical_rate": {"chunk": "chunk-622936954ae6957cf7f4a65c073694d7", "sha256": "0abcc7ef8ef9da34e2194b46a73ab7366fc0824cd486009dfd0c0884df12416a", "clause": "税率为6％"},
    "software": {"chunk": "tax-1240ea3c271f3f14f66d839a#d0000", "sha256": "1b48142931047016b0b78c30766718177f51ceaffeb685f01a2032b7b5a9bf5f", "clause": "取得省级软件产业主管部门认可的软件检测机构出具的检测证明材料"},
}


def case(case_id, question, domains, required=(), reason=None):
    return {"caseId": case_id, "question": question, "domains": list(domains),
            "requiredGold": list(required), "reason": reason}


CASES = (
    case("UAT-KB-001", "酒店行业的住宿费用，适用哪种税率？", (), reason="clarification_required"),
    case("UAT-KB-015a", "增值税政策中，生活服务中的住宿服务如何定义？", ("tax.policy",), ("lodging", "living")),
    case("UAT-KB-004", "住宿服务的政策分类和增值税法的税率规定是什么？", ("tax.policy", "tax.law"), ("lodging", "living", "law_rate")),
    case("UAT-KB-002", "一般纳税人采用一般计税方法，2026年提供住宿服务适用何种增值税税率？", ("tax.policy", "tax.law"), ("lodging", "law_rate", "law_effective")),
    case("UAT-KB-003", "住宿服务与不动产租赁的增值税分类有什么区别？", ("tax.policy",), ("lodging", "rent")),
    case("UAT-KB-005", "小规模纳税人提供住宿服务适用什么增值税征收率？", (), reason="clarification_required"),
    case("UAT-KB-006", "2016年一般纳税人按一般计税提供住宿服务的增值税税率是多少？", ("tax.policy",), ("lodging", "historical_rate")),
    case("UAT-KB-015b", "请查一下2026年一般纳税人采用一般计税的酒店住宿服务增值税税率及分类依据。", ("tax.policy", "tax.law"), ("lodging", "law_rate", "law_effective")),
    case("UAT-KB-016", "财税〔2011〕100号规定软件产品享受增值税即征即退需取得哪些证明材料？", ("tax.policy",), ("software",)),
    case("UAT-KB-008", "增值税法第十条规定销售服务适用的税率是什么？", ("tax.law",), ("law_rate",)),
)

LIMITS = {"e2e": len(CASES), "model": len(CASES) * 3,
          "search": len(CASES) * 4, "embedding": len(CASES) * 2, "rerank": len(CASES) * 2,
          "business": 0, "retry": 0, "resume": 0}


def assess(case_spec, response, observation, summary_evidence):
    """Compare only after execution; source hashes and exact clause checks."""
    result = response.get("result") or {}
    plans = [p["plan"] for p in observation.plans if p["type"] == "knowledge_retrieval_plan"]
    domains = plans[0].get("selected_domain_ids", []) if len(plans) == 1 else []
    expected_status = "no_result" if case_spec["reason"] else "success"
    points = result.get("points", [])
    checks = {}
    for name in case_spec["requiredGold"]:
        gold = GOLD[name]
        sources = [e for e in summary_evidence if e["sha256"] == gold["sha256"]]
        checks[name] = bool(sources) and any(
            gold["clause"] in p.get("quote", "") and any(p["quote"] in s["content"] for s in sources)
            for p in points)
    reasons_match = result.get("reason") == case_spec["reason"] if case_spec["reason"] else True
    passed = (response.get("status") == expected_status and response.get("capabilityId") == "knowledge.query"
              and domains == case_spec["domains"] and reasons_match and all(checks.values())
              and (bool(points) if not case_spec["reason"] else not points))
    return {"passed": passed, "domains": domains, "requiredClauseChecks": checks,
            "status": response.get("status"), "reason": result.get("reason"),
            "pointCount": len(points), "citationDomains": sorted({d for p in points for d in p.get("citation", {}).get("domainIds", [])})}
