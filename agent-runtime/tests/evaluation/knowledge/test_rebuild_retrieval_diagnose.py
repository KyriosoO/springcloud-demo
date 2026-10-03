"""Pure offline tests; existing frozen blobs and synthetic public text only."""

from dataclasses import replace
from hashlib import sha256
import json
from pathlib import Path
import socket

import pytest

from tests.evaluation.knowledge import rebuild_retrieval_diagnose as d
from tests.evaluation.knowledge.rebuild_b_comparator import CandidateRef


SOURCE = CandidateRef("document-one", "chunk-one", "a" * 64)
OTHER = CandidateRef("document-two", "chunk-two", "b" * 64)


def _diagnose(*, observations=(), inventory=(SOURCE,), **kwargs):
    return d.diagnose_source(source=SOURCE, source_domain="tax.policy",
        selected_domains=("tax.policy",), inventory=inventory,
        observations=observations, **kwargs)


def _initial(keyword, vector):
    return (d.Observation("keyword", "tax.policy", keyword),
            d.Observation("vector", "tax.policy", vector))


@pytest.mark.parametrize("observations,expected", [
    ((), "missing_record"),
    (_initial(None, None), "missing_record"),
    (_initial((), ()), "no_hit"),
    (_initial((OTHER,), (OTHER,)), "no_hit"),
])
def test_missing_stage_is_not_confirmed_miss(observations, expected):
    result = _diagnose(observations=observations)
    assert result["stages"][0]["state"] == expected
    assert result["stages"][0]["rank"] is None
    assert result["observedLoss"] == ("initial_recall_or_prior" if expected == "no_hit" else "unknown")
    assert result["rootCause"] == result["authorization"] == result["filterDecision"] == "unknown"


@pytest.mark.parametrize("inventory,expected", [
    (None, "source_provenance_unknown"), ((), "absent_frozen_inventory"),
    ((SOURCE,), "initial_recall_or_prior"),
])
def test_complete_inventory_not_current_index_assumption(inventory, expected):
    result = _diagnose(observations=_initial((), ()), inventory=inventory)
    assert result["observedLoss"] == expected


def test_unselected_domain_is_separate_and_inconsistent_hit_rejected():
    args = dict(source=SOURCE, source_domain="tax.policy", selected_domains=("tax.law",),
                inventory=(SOURCE,), observations=())
    assert d.diagnose_source(**args)["observedLoss"] == "domain_not_selected"
    with pytest.raises(d.DiagnosisError):
        d.diagnose_source(**{**args, "observations": _initial((SOURCE,), ())})


@pytest.mark.parametrize("stage", ["rrf", "rerank", "final20", "evidence"])
def test_only_first_observed_exclusion_is_attributed(stage):
    observations = list(_initial((OTHER, SOURCE), ()))
    for current in ("rrf", "rerank", "final20", "evidence"):
        domain = "tax.policy" if current == "rerank" else "all"
        observations.append(d.Observation(current, domain, () if current == stage else (SOURCE,)))
        if current == stage:
            break
    result = _diagnose(observations=tuple(observations))
    assert result["observedLoss"] == f"excluded_at_{stage}"
    assert result["stages"][0]["rank"] == 2
    assert result["answerQuality"] == "not_assessed"


def test_rrf_low_rank_restored_by_rerank_is_not_a_ranking_loss():
    others = tuple(CandidateRef(f"doc-{i}", f"chunk-{i}", "b" * 64) for i in range(30))
    observations = _initial((), (SOURCE,)) + (
        d.Observation("rrf", "all", others + (SOURCE,)),
        d.Observation("rerank", "tax.policy", (SOURCE,)),
        d.Observation("final20", "all", (SOURCE,)),
    )
    result = _diagnose(observations=observations)
    assert result["observedLoss"] == "retained_in_final20"
    assert result["stages"][2]["rank"] == 31
    assert result["stages"][-1]["state"] == "missing_record"
    assert result["answerQuality"] == "not_assessed"


@pytest.mark.parametrize("observations", [
    _initial((), ()) + (d.Observation("rrf", "all", (SOURCE,)),),
    (d.Observation("rrf", "all", ()), d.Observation("rerank", "tax.policy", (SOURCE,))),
    (d.Observation("rerank", "tax.policy", ()), d.Observation("final20", "all", (SOURCE,))),
    (d.Observation("final20", "all", ()), d.Observation("evidence", "all", (SOURCE,))),
])
def test_source_cannot_appear_after_complete_input_excluded_it(observations):
    with pytest.raises(d.DiagnosisError, match="^diagnosis_input_invalid$"):
        _diagnose(observations=observations)


def test_identity_hash_drift_duplicate_or_illegal_input_fails_closed():
    drift = replace(SOURCE, content_sha256="c" * 64)
    with pytest.raises(d.DiagnosisError):
        _diagnose(inventory=(drift,))
    with pytest.raises(d.DiagnosisError):
        _diagnose(observations=_initial((drift,), ()))
    with pytest.raises(d.DiagnosisError):
        _diagnose(inventory=(SOURCE, SOURCE))
    with pytest.raises(d.DiagnosisError):
        _diagnose(observations=_initial((), ()) * 2)
    with pytest.raises(d.DiagnosisError):
        d.Observation("keyword", "tax.policy", (SOURCE,) * 81)
    with pytest.raises(ValueError):
        CandidateRef("bad\nidentity", "chunk", "a" * 64)


def _public(text):
    return d.ApprovedPublicText(CandidateRef("synthetic-public", "span-one",
                                sha256(text.encode()).hexdigest()), text)


def test_literal_not_regex_shell_or_body_output(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("external_operation_forbidden")
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(Path, "open", forbidden)
    text = "合成公开资料：a.*b；$(shell)；a.*b；不匹配axxxb。"
    source = _public(text)
    result = d.locate_literals(sources=(source,), terms=("a.*b", "$(shell)"))
    assert len(result["hits"]) == 3
    for hit in result["hits"]:
        term = ("a.*b", "$(shell)")[hit["termOrdinal"] - 1]
        assert text[hit["start"]:hit["end"]] == term
    serialized = json.dumps(result)
    assert text not in serialized and "a.*b" not in serialized and "$(shell)" not in serialized
    assert text not in repr(source)


def test_literal_maximum_and_no_match_are_explicit():
    source = _public("x" * 32)
    assert d.locate_literals(sources=(source,), terms=("x",), max_results=2)["truncated"] is True
    assert d.locate_literals(sources=(source,), terms=("x",), max_results=32)["truncated"] is False
    assert d.locate_literals(sources=(source,), terms=("y",))["hits"] == []


@pytest.mark.parametrize("terms,max_results", [((), 16), (("",), 16), (("x", "x"), 16),
    (("x\ny",), 16), (("x" * 129,), 16), (("x",), 0), (("x",), 33), (("x",), True)])
def test_literal_limits_reject(terms, max_results):
    with pytest.raises(d.DiagnosisError):
        d.locate_literals(sources=(_public("x"),), terms=terms, max_results=max_results)


def test_public_source_hash_and_source_scope_limits():
    with pytest.raises(d.DiagnosisError):
        d.ApprovedPublicText(SOURCE, "not-the-frozen-source")
    with pytest.raises(d.DiagnosisError):
        _public("x" * 65537)
    with pytest.raises(d.DiagnosisError):
        d.locate_literals(sources=(_public("x"),) * 31, terms=("x",))
    with pytest.raises(d.DiagnosisError):
        d.locate_literals(sources=(_public("x"),) * 2, terms=("x",))


def test_sealed_b_replay_no_network_or_body_or_reclassification(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("network_forbidden")
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    directory = review_directory()
    files = tuple(path for path in directory.iterdir() if path.is_file())
    hashes = {path: sha256(path.read_bytes()).hexdigest() for path in files}
    report = d.diagnose_b(directory)
    assert report["comparisonResultSha256"] == "50a03b7dc8cb8e2667c0bc509346e4db12f4fc6c5ceee953ed8dbd39ac21a934"
    assert len(report["diagnoses"]) == 32  # 16 necessary occurrences x two arms.
    losses = [item for item in report["diagnoses"] if item["observedLoss"] == "initial_recall_or_prior"]
    assert [(item["caseId"], item["arm"]) for item in losses] == [
        ("UAT-KM-003", "baseline"), ("UAT-KM-003", "candidate"),
        ("UAT-KM-012", "baseline"), ("UAT-KM-012", "candidate")]
    assert all(item["rootCause"] == "unknown" and item["answerQuality"] == "not_assessed"
               for item in report["diagnoses"])
    law = [item for item in report["diagnoses"] if item["sourceDomain"] == "tax.law"]
    assert law and all(item["inventory"] == "present" for item in law)
    assert report["newExternalCalls"] == 0 and report["onlineChangeSelected"] is False
    assert {path: sha256(path.read_bytes()).hexdigest() for path in files} == hashes
    serialized = json.dumps(report)
    assert all(key not in serialized for key in ("query_text", "question", "quote", "queryVector", "JWT"))


def review_directory():
    return Path(__file__).resolve().parents[4] / "knowledge-corpus-tools/evidence/knowledge-b-reuse-20261003-01"


def test_unadmitted_path_rejected_without_reading_other_files(tmp_path):
    with pytest.raises(d.DiagnosisError, match="^diagnosis_input_invalid$"):
        d.diagnose_b(tmp_path)


def test_cli_error_has_no_path_or_source_content(monkeypatch, capsys):
    import sys
    monkeypatch.setattr(sys, "argv", ["diagnose", "--run-directory", "secret-invalid-path"])
    assert d.main() == 1
    assert json.loads(capsys.readouterr().out) == {
        "status": "not_assessed", "reason": "diagnosis_input_invalid"}


@pytest.fixture(scope="module")
def admitted_b():
    return d.review.load_completed(review_directory())


@pytest.mark.parametrize("stage,domain", [("keyword", "tax.policy"),
    ("vector", "tax.policy"), ("final20", "all")])
def test_observation_rejects_twenty_first_record_not_truncates(stage, domain):
    refs = tuple(CandidateRef(f"d-{i}", f"c-{i}", "a" * 64) for i in range(21))
    with pytest.raises(d.DiagnosisError):
        d.Observation(stage, domain, refs)


@pytest.mark.parametrize("field", ["keyword", "vector", "reranked"])
def test_b_rejects_invalid_path_or_domain(field, admitted_b):
    case, trace = admitted_b.spec.cases[0], admitted_b.run.cases[0]
    entries = getattr(trace.baseline, field)
    for changed in (replace(entries[0], path="not-a-valid-path"),
                    replace(entries[0], domain_id="tax.law")):
        altered = replace(trace.baseline, **{field: (changed, *entries[1:])})
        with pytest.raises(d.DiagnosisError):
            d._b_observations(case, altered)


@pytest.mark.parametrize("field", ["keyword", "vector", "final20"])
def test_b_rejects_frozen_window_overflow(field, admitted_b):
    case, trace = admitted_b.spec.cases[1], admitted_b.run.cases[1]
    refs = tuple(CandidateRef(f"d-{i}", f"c-{i}", "a" * 64) for i in range(21))
    value = refs if field == "final20" else (replace(getattr(trace.baseline, field)[0], ranked=refs),)
    with pytest.raises(d.DiagnosisError):
        d._b_observations(case, replace(trace.baseline, **{field: value}))


def test_b_stage_membership_drift_and_missing_rerank_rejected(admitted_b):
    case, trace = admitted_b.spec.cases[0], admitted_b.run.cases[0]
    for altered in (replace(trace.baseline, fused=(OTHER,)),
                    replace(trace.baseline, reranked=()),
                    replace(trace.baseline, final20=(OTHER,))):
        with pytest.raises(d.DiagnosisError):
            d._b_observations(case, altered)
