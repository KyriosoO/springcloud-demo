from __future__ import annotations

import json
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

import httpx
import pytest

from knowledge_corpus_tools.errors import StateConflict
from knowledge_corpus_tools.release import AliasReleaseManager


class ReleaseServer:
    """No network: model one atomic alias change and independent postchecks."""

    def __init__(self) -> None:
        self.target = "old"
        self.flags: dict[str, Any] = {}
        self.candidate_aliases: dict[str, Any] = {}
        self.receipt: Any = {"acknowledged": True, "errors": False}
        self.post_flags: dict[str, Any] = {}
        self.post_uuid = "new-uuid"
        self.posts: list[dict[str, Any]] = []
        self.apply_switch = True

    def handle(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if request.method == "GET" and path == "/_alias/read":
            flags = self.flags if not self.posts else self.post_flags
            return httpx.Response(200, json={self.target: {"aliases": {"read": flags}}})
        if request.method == "GET" and path in {"/old", "/candidate"}:
            index = path[1:]
            uuid = "old-uuid" if index == "old" else self.post_uuid if self.posts else "new-uuid"
            return httpx.Response(200, json={index: {"settings": {"index": {"uuid": uuid}}}})
        if request.method == "GET" and path == "/candidate/_alias":
            return httpx.Response(200, json={"candidate": {"aliases": self.candidate_aliases}})
        if request.method == "POST" and path == "/_aliases":
            body = json.loads(request.content)
            self.posts.append(body)
            if self.apply_switch:
                self.target = body["actions"][1]["add"]["index"]
            return httpx.Response(200, json=self.receipt)
        raise AssertionError((request.method, path))


@contextmanager
def release_manager(server: ReleaseServer) -> Iterator[AliasReleaseManager]:
    with httpx.Client(transport=httpx.MockTransport(server.handle)) as client:
        manager = AliasReleaseManager("http://es.local", client=client)
        try:
            yield manager
        finally:
            manager.close()


def publish(manager: AliasReleaseManager) -> None:
    state = manager.switch(alias="read", expected_from_index="old", expected_from_uuid="old-uuid",
                           target_index="candidate", target_uuid="new-uuid", phase="published")
    assert state.phase == "published"


@pytest.mark.parametrize("flags", [
    {"filter": {"term": {"domain": "policy"}}},
    {"routing": "scope"},
    {"search_routing": "scope"},
    {"index_routing": "scope"},
    {"is_write_index": False},
    {"is_hidden": True},
])
def test_alias_flag_drift_rejects_before_any_write(flags: dict[str, Any]) -> None:
    server = ReleaseServer()
    server.flags = flags
    with release_manager(server) as manager, pytest.raises(StateConflict, match="alias metadata"):
        publish(manager)
    assert server.posts == []


@pytest.mark.parametrize("aliases", [
    {"read": {}},
    {"leftover-validation": {"is_write_index": False}},
    {"unrelated-alias": {}},
])
def test_candidate_with_any_alias_rejects_before_write(aliases: dict[str, Any]) -> None:
    server = ReleaseServer()
    server.candidate_aliases = aliases
    with release_manager(server) as manager, pytest.raises(StateConflict, match="no aliases"):
        publish(manager)
    assert server.posts == []


@pytest.mark.parametrize("receipt", [
    {},
    {"acknowledged": True},
    {"acknowledged": False, "errors": False},
    {"acknowledged": True, "errors": True},
    {"acknowledged": "true", "errors": False},
    {"acknowledged": 1, "errors": False},
    {"acknowledged": True, "errors": 0},
    {"acknowledged": True, "errors": "false"},
    [],
    "invalid",
])
def test_uncertain_receipt_is_not_success_or_retried(receipt: Any) -> None:
    server = ReleaseServer()
    server.receipt = receipt
    with release_manager(server) as manager, pytest.raises(StateConflict, match="acknowledgement"):
        publish(manager)
    # ES may have applied the write despite an invalid receipt. Do not retry or
    # issue an unverified compensating write against potentially changed state.
    assert server.target == "candidate"
    assert len(server.posts) == 1


def test_alias_flags_changed_after_write_do_not_produce_success() -> None:
    server = ReleaseServer()
    server.post_flags = {"filter": {"term": {"domain": "policy"}}}
    with release_manager(server) as manager, pytest.raises(StateConflict, match="alias metadata"):
        publish(manager)
    assert len(server.posts) == 1


def test_index_recreated_after_write_does_not_produce_success() -> None:
    server = ReleaseServer()
    server.post_uuid = "replacement-uuid"
    with release_manager(server) as manager, pytest.raises(StateConflict, match="verification"):
        publish(manager)
    assert len(server.posts) == 1


def test_acknowledgement_without_target_change_is_not_success() -> None:
    server = ReleaseServer()
    server.apply_switch = False
    with release_manager(server) as manager, pytest.raises(StateConflict, match="verification"):
        publish(manager)
    assert len(server.posts) == 1


def test_success_preserves_empty_flags_and_one_atomic_write() -> None:
    server = ReleaseServer()
    with release_manager(server) as manager:
        publish(manager)
    assert server.target == "candidate"
    assert server.posts == [{"actions": [
        {"remove": {"index": "old", "alias": "read"}},
        {"add": {"index": "candidate", "alias": "read"}},
    ]}]
