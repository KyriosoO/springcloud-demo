from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

import httpx

from .errors import StateConflict
from .models import ReleaseState


class AliasReleaseManager:
    def __init__(self, endpoint: str, *, client: httpx.Client | None = None) -> None:
        self._endpoint = endpoint.rstrip("/")
        self._owned = client is None
        self._client = client or httpx.Client(timeout=30.0)

    def close(self) -> None:
        if self._owned:
            self._client.close()

    def _uuid(self, index: str) -> str:
        response = self._client.get(f"{self._endpoint}/{index}")
        response.raise_for_status()
        return str(response.json()[index]["settings"]["index"]["uuid"])

    def _targets(self, alias: str) -> tuple[str, ...]:
        response = self._client.get(f"{self._endpoint}/_alias/{alias}")
        response.raise_for_status()
        bindings = response.json()
        # The approved published alias has empty flags. A filter, routing or
        # write-index flag is a different binding, not a target-only match.
        if (type(bindings) is not dict or not bindings
                or any(type(index) is not str or not index
                       or metadata != {"aliases": {alias: {}}}
                       for index, metadata in bindings.items())):
            raise StateConflict("alias metadata differs from frozen precondition")
        return tuple(sorted(bindings))

    def switch(
        self,
        *,
        alias: str,
        expected_from_index: str,
        expected_from_uuid: str,
        target_index: str,
        target_uuid: str,
        phase: Literal["candidate", "rolled_back", "published"],
    ) -> ReleaseState:
        if self._targets(alias) != (expected_from_index,):
            raise StateConflict("alias target differs from frozen precondition")
        if self._uuid(expected_from_index) != expected_from_uuid or self._uuid(target_index) != target_uuid:
            raise StateConflict("index UUID differs from frozen precondition")
        candidate_alias = self._client.get(f"{self._endpoint}/{target_index}/_alias")
        candidate_alias.raise_for_status()
        if candidate_alias.json() != {target_index: {"aliases": {}}}:
            raise StateConflict("target must have no aliases")
        response = self._client.post(
            f"{self._endpoint}/_aliases",
            json={"actions": [{"remove": {"index": expected_from_index, "alias": alias}}, {"add": {"index": target_index, "alias": alias}}]},
        )
        response.raise_for_status()
        receipt = response.json()
        if (type(receipt) is not dict or receipt.get("acknowledged") is not True
                or receipt.get("errors") is not False):
            raise StateConflict("alias switch acknowledgement invalid")
        if (self._targets(alias) != (target_index,)
                or self._uuid(target_index) != target_uuid):
            raise StateConflict("alias switch verification failed")
        return ReleaseState(
            schema_version=1,
            alias=alias,
            old_index=expected_from_index,
            old_index_uuid=expected_from_uuid,
            candidate_index=target_index,
            candidate_index_uuid=target_uuid,
            phase=phase,
            executed_at_utc=datetime.now(UTC),
        )
