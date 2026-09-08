"""DR-KRET-032: owned temporary alias, never a production publication helper."""
from __future__ import annotations

from dataclasses import dataclass
import json
import re
import secrets
from typing import Any

import httpx


@dataclass(frozen=True)
class IndexIdentity:
    name: str
    uuid: str

    def __post_init__(self) -> None:
        if (re.fullmatch(r"agent-doc-tax-policy-v[0-9]+-[0-9]{8}-(corpus-a|vector-b)[0-9]+", self.name) is None
                or re.fullmatch(r"[A-Za-z0-9_-]{22}", self.uuid) is None):
            raise ValueError("validation_binding_invalid")


def _unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("validation_response_invalid")
        result[key] = value
    return result


class ValidationAlias:
    """One local operator only; prechecks are not a distributed ES CAS.

    A possibly successful write is never retried. Cleanup rechecks exact owner
    identity and leaves conflicts untouched for explicit operator handling.
    """

    def __init__(self, *, source: IndexIdentity, candidate: IndexIdentity,
                 published_alias: str, transport: httpx.BaseTransport | None = None) -> None:
        if (source == candidate or source.name == candidate.name or source.uuid == candidate.uuid
                or re.fullmatch(r"agent-doc-tax-policy-v[0-9]+-read", published_alias) is None):
            raise ValueError("validation_binding_invalid")
        self.source, self.candidate = source, candidate
        self.published_alias = published_alias
        self.name = "agent-knowledge-validation-" + secrets.token_hex(16)
        self.reads = self.writes = 0
        self._attempted = False
        self._closed = False
        self._target = candidate
        self._possible_owners: tuple[IndexIdentity, ...] = (candidate,)
        self._client = httpx.Client(base_url="http://127.0.0.1:9200", trust_env=False,
                                    follow_redirects=False, timeout=5, transport=transport,
                                    headers={"Accept-Encoding": "identity"})

    def _request(self, method: str, path: str, body: dict[str, Any] | None = None) -> dict[str, Any] | None:
        if method == "GET":
            if self.reads >= 40:
                raise ValueError("validation_read_budget")
            self.reads += 1
        else:
            if self.writes >= 4:
                raise ValueError("validation_write_budget")
            self.writes += 1
        try:
            with self._client.stream(method, path, json=body) as response:
                if response.status_code == 404 and path.startswith("/_alias/") and method == "GET":
                    return None
                if (response.status_code != 200
                        or response.headers.get("content-encoding", "identity") != "identity"
                        or response.headers.get("content-type", "").split(";")[0] != "application/json"):
                    raise ValueError("validation_response_invalid")
                raw = bytearray()
                for chunk in response.iter_raw():
                    raw.extend(chunk)
                    if len(raw) > 2 * 1024 * 1024:
                        raise ValueError("validation_response_limit")
                value = json.loads(raw, object_pairs_hook=_unique)
                if type(value) is not dict:
                    raise ValueError("validation_response_invalid")
                return value
        except (httpx.HTTPError, UnicodeError, json.JSONDecodeError):
            raise ValueError("validation_transport_failed") from None

    def _index(self, identity: IndexIdentity) -> None:
        raw = self._request("GET", f"/{identity.name}/_settings")
        try:
            assert raw is not None
            settings = raw[identity.name]["settings"]["index"]
            valid = (set(raw) == {identity.name} and settings["uuid"] == identity.uuid
                     and (settings["blocks"]["write"] is True or settings["blocks"]["write"] == "true"))
        except (AssertionError, KeyError, TypeError):
            valid = False
        if not valid:
            raise ValueError("validation_index_changed")

    @staticmethod
    def _is_target(raw: dict[str, Any] | None, name: str, identity: IndexIdentity) -> bool:
        try:
            return (type(raw) is dict and set(raw) == {identity.name}
                    and type(raw[identity.name]) is dict and set(raw[identity.name]) == {"aliases"}
                    and type(raw[identity.name]["aliases"]) is dict and set(raw[identity.name]["aliases"]) == {name}
                    and type(raw[identity.name]["aliases"][name]) is dict
                    and set(raw[identity.name]["aliases"][name]) == {"is_write_index"}
                    and raw[identity.name]["aliases"][name]["is_write_index"] is False)
        except (KeyError, TypeError):
            return False

    @staticmethod
    def _acknowledged(raw: dict[str, Any] | None) -> bool:
        return (type(raw) is dict and set(raw) == {"acknowledged", "errors"}
                and raw["acknowledged"] is True and raw["errors"] is False)

    def _precheck(self) -> None:
        self._index(self.source)
        self._index(self.candidate)
        # The immutable Stage A published alias was created without alias flags.
        # Both underlying indexes are still required to be explicitly write-blocked.
        if self._request("GET", f"/_alias/{self.published_alias}") != {
            self.source.name: {"aliases": {self.published_alias: {}}},
        }:
            raise ValueError("validation_published_alias_changed")

    def open(self) -> str:
        if self._attempted or self._closed:
            raise ValueError("validation_reentry_forbidden")
        self._precheck()
        if self._request("GET", f"/_alias/{self.name}") is not None:
            raise ValueError("validation_alias_exists")
        self._attempted = True
        raw = self._request("POST", "/_aliases", {"actions": [
            {"add": {"index": self.candidate.name, "alias": self.name, "is_write_index": False}},
        ]})
        if not self._acknowledged(raw) or not self._is_target(
            self._request("GET", f"/_alias/{self.name}"), self.name, self.candidate,
        ):
            raise ValueError("validation_alias_confirmation_failed")
        return self.name

    def move(self, target: IndexIdentity) -> None:
        if not self._attempted or self._closed or target not in (self.source, self.candidate) or target == self._target:
            raise ValueError("validation_transition_invalid")
        if self.writes >= 3 or self.reads > 25:
            raise ValueError("validation_cleanup_budget_reserved")
        self._precheck()
        if not self._is_target(self._request("GET", f"/_alias/{self.name}"), self.name, self._target):
            raise ValueError("validation_alias_owner_changed")
        old = self._target
        # Keep both possibilities verifiable if the atomic response is lost.
        self._possible_owners = (old, target)
        raw = self._request("POST", "/_aliases", {"actions": [
            {"remove": {"index": old.name, "alias": self.name, "must_exist": True}},
            {"add": {"index": target.name, "alias": self.name, "is_write_index": False}},
        ]})
        self._target = target
        if not self._acknowledged(raw) or not self._is_target(
            self._request("GET", f"/_alias/{self.name}"), self.name, target,
        ):
            raise ValueError("validation_alias_confirmation_failed")
        self._possible_owners = (target,)

    def close(self) -> None:
        if self._closed:
            return
        try:
            if self._attempted:
                self._precheck()
                raw = self._request("GET", f"/_alias/{self.name}")
                if raw is not None:
                    owners = [item for item in self._possible_owners
                              if self._is_target(raw, self.name, item)]
                    if len(owners) != 1:
                        raise ValueError("validation_alias_owner_changed")
                    response = self._request("POST", "/_aliases", {"actions": [{"remove": {
                        "index": owners[0].name, "alias": self.name, "must_exist": True,
                    }}]})
                    if not self._acknowledged(response) or self._request("GET", f"/_alias/{self.name}") is not None:
                        raise ValueError("validation_cleanup_failed")
                self._precheck()
        finally:
            self._closed = True
            self._client.close()

    def __enter__(self) -> str:
        try:
            return self.open()
        except BaseException:
            self.close()
            raise

    def __exit__(self, *args: object) -> None:
        self.close()
