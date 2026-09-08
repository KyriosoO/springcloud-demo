import hashlib
import json
from pathlib import Path

import httpx
import pytest

from knowledge_corpus_tools.validation_alias import IndexIdentity, ValidationAlias

SOURCE = IndexIdentity("agent-doc-tax-policy-v4-20260903-corpus-a5", "s" * 22)
TARGET = IndexIdentity("agent-doc-tax-policy-v5-20260907-vector-b2", "t" * 22)
PUBLISHED = "agent-doc-tax-policy-v2-read"


def reply(status, value):
    return httpx.Response(status, stream=httpx.ByteStream(json.dumps(value).encode()),
                          headers={"content-type": "application/json"})


class FakeEs:
    def __init__(self):
        self.aliases = {PUBLISHED: SOURCE.name}
        self.uuids = {SOURCE.name: SOURCE.uuid, TARGET.name: TARGET.uuid}
        self.blocked = True
        self.calls = []
        self.lose_response = False

    def __call__(self, request):
        self.calls.append((request.method, request.url.path))
        path = request.url.path
        if request.method == "POST":
            for action in json.loads(request.content)["actions"]:
                operation, spec = next(iter(action.items()))
                assert spec["alias"] != PUBLISHED
                if operation == "remove":
                    assert self.aliases.pop(spec["alias"]) == spec["index"]
                else:
                    assert spec["is_write_index"] is False
                    self.aliases[spec["alias"]] = spec["index"]
            if self.lose_response:
                self.lose_response = False
                raise httpx.ReadTimeout("private upstream payload")
            return reply(200, {"acknowledged": True, "errors": False})
        if path.startswith("/_alias/"):
            name = path.split("/")[-1]
            if name not in self.aliases:
                return reply(404, {})
            flags = {} if name == PUBLISHED else {"is_write_index": False}
            return reply(200, {self.aliases[name]: {"aliases": {name: flags}}})
        name = path.split("/")[1]
        return reply(200, {name: {"settings": {"index": {
            "uuid": self.uuids[name], "blocks": {"write": str(self.blocked).lower()},
        }}}})


def lease(fake):
    return ValidationAlias(source=SOURCE, candidate=TARGET, published_alias=PUBLISHED,
                           transport=httpx.MockTransport(fake))


def test_create_rehearse_remove_preserves_published_and_indexes():
    fake = FakeEs()
    item = lease(fake)
    with item as name:
        assert fake.aliases[name] == TARGET.name
        item.move(SOURCE)
        item.move(TARGET)
    assert fake.aliases == {PUBLISHED: SOURCE.name}
    assert item.writes == 4 and item.reads <= 40
    assert all(path == "/_aliases" for method, path in fake.calls if method != "GET")
    item.close()


@pytest.mark.parametrize("problem", ["uuid", "block", "published", "existing"])
def test_preflight_changes_cause_zero_writes(problem):
    fake = FakeEs()
    item = lease(fake)
    if problem == "uuid":
        fake.uuids[TARGET.name] = "changed"
    elif problem == "block":
        fake.blocked = False
    elif problem == "published":
        fake.aliases[PUBLISHED] = TARGET.name
    else:
        fake.aliases[item.name] = SOURCE.name
    with pytest.raises(ValueError):
        with item:
            pytest.fail("must not enter")
    assert item.writes == 0


def test_lost_create_response_cleans_only_proven_owner_without_retry():
    fake = FakeEs()
    fake.lose_response = True
    item = lease(fake)
    with pytest.raises(ValueError, match="validation_transport_failed"):
        with item:
            pytest.fail("no enter on unknown response")
    assert item.writes == 2
    assert fake.aliases == {PUBLISHED: SOURCE.name}


def test_exception_cleanup_and_no_reentry():
    fake = FakeEs()
    item = lease(fake)
    with pytest.raises(RuntimeError):
        with item:
            raise RuntimeError("test failure")
    assert fake.aliases == {PUBLISHED: SOURCE.name}
    with pytest.raises(ValueError, match="reentry"):
        item.open()


@pytest.mark.parametrize("change", ["uuid", "published", "owner"])
def test_cleanup_conflict_is_not_overwritten(change):
    fake = FakeEs()
    item = lease(fake)
    item.open()
    if change == "uuid":
        fake.uuids[TARGET.name] = "changed"
    elif change == "published":
        fake.aliases[PUBLISHED] = TARGET.name
    else:
        fake.aliases[item.name] = "someone-elses-index"
    with pytest.raises(ValueError):
        item.close()
    assert item.writes == 1


def test_lost_move_response_cleanup_and_no_replay():
    fake = FakeEs()
    item = lease(fake)
    with pytest.raises(ValueError, match="transport_failed"):
        with item:
            fake.lose_response = True
            item.move(SOURCE)
    assert item.writes == 3 and fake.aliases == {PUBLISHED: SOURCE.name}


@pytest.mark.parametrize("name", ["*", "../_all", SOURCE.name + "/_doc", "unrelated-index"])
def test_reject_unbound_index_names(name):
    with pytest.raises(ValueError, match="binding_invalid"):
        IndexIdentity(name, SOURCE.uuid)


def test_budget_before_network_and_bad_response():
    item = lease(FakeEs())
    item.reads = 40
    with pytest.raises(ValueError, match="read_budget"):
        item.open()
    item.close()
    bad = ValidationAlias(source=SOURCE, candidate=TARGET, published_alias=PUBLISHED,
                          transport=httpx.MockTransport(lambda _: reply(200, [])))
    with pytest.raises(ValueError, match="response_invalid"):
        with bad:
            pytest.fail("invalid response")


@pytest.mark.parametrize("flags", [{"is_write_index": True}, {"filter": {"term": {"x": "y"}}}, {"routing": "1"}])
def test_changed_published_alias_metadata_is_not_accepted(flags):
    fake = FakeEs()
    def handler(request):
        if request.url.path == f"/_alias/{PUBLISHED}":
            return reply(200, {SOURCE.name: {"aliases": {PUBLISHED: flags}}})
        return fake(request)
    item = lease(handler)
    with pytest.raises(ValueError, match="published_alias_changed"):
        with item:
            pytest.fail("changed metadata")
    assert item.writes == 0


def test_cleanup_budget_reserved_and_other_known_index_not_owned():
    fake = FakeEs()
    item = lease(fake)
    with item:
        item.move(SOURCE)
        item.move(TARGET)
        with pytest.raises(ValueError, match="cleanup_budget_reserved"):
            item.move(SOURCE)
    assert item.writes == 4
    item = lease(fake)
    item.open()
    fake.aliases[item.name] = SOURCE.name
    with pytest.raises(ValueError, match="owner_changed"):
        item.close()
    assert item.writes == 1


@pytest.mark.parametrize("raw", [None, {}, {"acknowledged": True}, {"acknowledged": 1, "errors": False},
    {"acknowledged": True, "errors": 0}, {"acknowledged": True, "errors": True},
    {"acknowledged": True, "errors": False, "action_results": []}])
def test_exact_es9_ack_rejects_errors_and_numeric_boolean(raw):
    assert not ValidationAlias._acknowledged(raw)


def test_alias_flags_cannot_coerce_numeric_zero():
    assert not ValidationAlias._is_target({TARGET.name: {"aliases": {"x": {"is_write_index": 0}}}}, "x", TARGET)


@pytest.mark.parametrize("number,expected", [
    (1, "ecf611dbcdbcd73d370ea009da3b477db590a4c23f424b99795c6d97ba3120aa"),
    (2, "26cf361e3aa5ec2eade3ab1fdeeef8dd0574c3ecbe87c1d397a4bacc7b4f1085"),
    (3, "e1af256d29ef7874cf8191a1a6a1cfdf455526f4882ea6923a6438af72d9f764"),
    (4, "c1e7b29ee099bcbbfeb4e640e70e70844003b6de555b73ec85d140c21ff25c95"),
])
def test_typed_results_are_immutable_and_do_not_claim_publication(number, expected):
    path = Path(__file__).parents[1] / "evidence/policy-vector-publication-20260907-b2" / f"typed-validation-20260908-0{number}.json"
    raw = path.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == expected
    result = json.loads(raw)
    assert result["status"] == ("passed" if number == 4 else "failed")
    assert all(type(result[key]) is int and result[key] == 0 for key in (
        "modelCalls", "businessCalls", "rerankCalls", "retry", "resume", "onlineAliasWrites"))
    assert set(result["limitations"]) == {
        "not_online_publication", "not_quality_v3_e2e", "not_real_summary", "rollback_not_rehearsed",
    }
    if number == 4:
        assert result["typedCalls"] == len(result["checks"]) == 16 and result["embeddingCalls"] == 2
        assert result["validationAliasWrites"] == 2 and result["esManagementReads"] == 13
        assert all(result[key] is True for key in ("ownedProcessesStopped", "profileVerifierStartupPassed",
            "rawLogsDeleted", "secretScanPassed", "validationAliasRemoved", "onlineBindingUnchanged"))
        successful = [item for item in result["checks"] if "verifiedCandidates" in item]
        denied = [item for item in result["checks"] if "httpStatus" in item]
        assert len(successful) == len(denied) == 8
        assert sum(item["verifiedCandidates"] for item in successful) == 160
        assert all(item["status"] == "passed" for item in result["checks"])
        assert all(item["bodyReturned"] is False and item["httpStatus"] in (401, 403) for item in denied)
    else:
        assert result["typedCalls"] == result["embeddingCalls"] == 0 and not result["checks"]
