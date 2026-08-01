from __future__ import annotations

import hashlib
from dataclasses import dataclass

from agent_runtime.knowledge.retrieval.contracts import AuthorizedKnowledgeCandidate
from agent_runtime.knowledge.retrieval.http import BoundedHttpRequest, BoundedHttpResponse


def candidate(*, chunk: str = "c1", domain: str = "tax.policy", rank: int = 1, content: str = "税务政策正文") -> AuthorizedKnowledgeCandidate:
    return AuthorizedKnowledgeCandidate(
        document_id="d1", chunk_id=chunk, domain_id=domain, title="标题", content=content,
        source_url=None, document_number=None, written_date=None, material_type="tax_policy",
        source_rank=rank, content_sha256=hashlib.sha256(content.encode("utf-8")).hexdigest(),
        read_policy_version="tax-public-authenticated-v1", policy_ref="policy-doc-v1",
        index_snapshot_id="a" * 64,
    )


@dataclass
class FakeTransport:
    response: BoundedHttpResponse

    def __post_init__(self) -> None:
        self.requests: list[BoundedHttpRequest] = []

    async def send(self, *, request: BoundedHttpRequest, timeout_s: float) -> BoundedHttpResponse:
        assert timeout_s > 0
        self.requests.append(request)
        return self.response

