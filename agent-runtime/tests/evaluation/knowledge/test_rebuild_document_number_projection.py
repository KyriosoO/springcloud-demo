"""Offline preparation tests; fake outputs do not prove actual Java projection."""
from dataclasses import replace
from io import BytesIO
import json
from pathlib import Path
import stat
import subprocess
from zipfile import ZipFile, ZipInfo

import pytest

from tests.evaluation.knowledge import rebuild_document_number_comparison as p
from tests.evaluation.knowledge import rebuild_document_number_projection as x
from tests.evaluation.knowledge.rebuild_b_local_transport import _request_hashes
from tests.evaluation.knowledge.test_rebuild_document_number_transport import physical


@pytest.fixture
def draft():
    return p.draft_from_bytes(fixture_raw=(p.ROOT / p.FIXTURE).read_bytes(), head="f" * 40,
        old_helper=b"synthetic-old", current_helper=b"synthetic-current", changed_paths=(p.HELPER,))


def zipped(entries):
    out = BytesIO()
    with ZipFile(out, "w") as archive:
        for name, raw in entries:
            if isinstance(name, str):
                info = ZipInfo(name)
                # Windows ZipInfo normally converts backslashes before writing;
                # keep the adversarial wire spelling for the reader test.
                info.filename = name
            else:
                info = name
            archive.writestr(info, raw)
    return out.getvalue()


def jar(arm, config=b"synthetic-config"):
    return zipped([(x.JAR_CONFIG, config),
        ("BOOT-INF/classes/com/dylan/esquery/service/KnowledgeSearchService.class", b"shared-class"),
        (x.CLASS_HELPER + ".class", arm.encode()),
        ("BOOT-INF/lib/mapper.jar", b"same-dependency")])


def outputs(draft, arm):
    return b"".join(p.canonical({"caseId": case.case_id, "domain": domain,
        "request": physical(case, domain=domain, signal=arm == "current" and case.case_id == "UAT-KM-003")})
        for case in draft.cases for domain in case.plan.selected_domain_ids)


def proof(draft, arm):
    _, fingerprints = x._artifacts(jar(arm), config_raw=b"synthetic-config")
    return x.ProjectionProof(arm, "0" * 64, "1" * 64, "2" * 64, *fingerprints,
        x._parse_projection(outputs(draft, arm), draft=draft, arm=arm))


def test_all_ten_cases_and_both_profiles_are_bound_without_quality_claim(draft):
    pair = tuple(proof(draft, arm) for arm in p.ARMS)
    x._validate_pair(pair, draft)
    assert len(pair[0].rows) == len(pair[1].rows) == 11
    changed = [left.case_id for left, right in zip(pair[0].rows, pair[1].rows, strict=True)
               if left.canonical_sha256 != right.canonical_sha256]
    assert changed == ["UAT-KM-003"]
    assert pair[0].for_case(draft.cases[5])[0][0] == "tax.policy"
    assert pair[0].for_case(draft.cases[5])[1][0] == "tax.law"
    assert "question" not in repr(pair) and "合成机关" not in repr(pair)


@pytest.mark.parametrize("mutation", ["count", "order", "domain", "duplicate", "query", "category",
    "law-signal", "field", "unknown", "number", "duplicate-json"])
def test_bad_output_cannot_become_an_expected_hash(draft, mutation):
    rows = [json.loads(line) for line in outputs(draft, "current").splitlines()]
    if mutation == "count":
        rows.pop()
    elif mutation == "order":
        rows[0], rows[1] = rows[1], rows[0]
    elif mutation == "domain":
        rows[0]["domain"] = "tax.law"
    elif mutation == "duplicate":
        rows[1] = rows[0]
    elif mutation == "query":
        rows[0]["request"]["query"]["bool"]["must"][0]["multi_match"]["query"] = "changed"
    elif mutation == "category":
        rows[0]["request"]["query"]["bool"]["filter"] = []
    elif mutation == "law-signal":
        case = draft.cases[5]
        rows[6]["request"] = physical(case, domain="tax.law", signal=True)
    elif mutation == "field":
        rows[0]["request"]["_source"]["includes"].append("unexpected")
    elif mutation == "unknown":
        rows[0]["extra"] = True
    elif mutation == "number":
        rows[0]["request"]["size"] = True
    raw = b"".join(p.canonical(row) for row in rows)
    if mutation == "duplicate-json":
        raw = raw.replace(b'"size":21', b'"size":21,"size":21', 1)
    with pytest.raises(p.ProtocolError):
        x._parse_projection(raw, draft=draft, arm="current")


@pytest.mark.parametrize("mutation", ["config", "inspector", "classes", "dependency", "helper", "law", "order"])
def test_two_builds_must_differ_only_in_helper_and_policy_projection(draft, mutation):
    old, current = (proof(draft, arm) for arm in p.ARMS)
    field = {"config": "config_sha256", "inspector": "inspector_sha256", "classes": "shared_classes_sha256",
             "dependency": "dependencies_sha256", "helper": "helper_classes_sha256"}.get(mutation)
    if field:
        current = replace(current, **{field: getattr(old, field) if mutation == "helper" else "a" * 64})
    elif mutation == "law":
        current = replace(current, rows=tuple(replace(row, canonical_sha256="b" * 64) if row.domain == "tax.law"
                                            else row for row in current.rows))
    else:
        current = replace(current, rows=current.rows[::-1])
    with pytest.raises(p.ProtocolError):
        x._validate_pair((old, current), draft)


@pytest.mark.parametrize("name", ["../escape", "/absolute", "C:/absolute", "dir\\escape", "a/../b", "a//b"])
def test_archive_rejects_noncanonical_or_escaping_paths(name):
    with pytest.raises(p.ProtocolError, match="archive_invalid"):
        x._entry_map(zipped([(name, b"bad")]))


@pytest.mark.parametrize("name", ["NUL", "CON.txt", "aux/data", "sub/COM1.bin", "LPT².txt",
    "foo.", "foo ", "sub/foo./child", "CONIN$", "a?b", "a\x00b"])
def test_windows_device_or_ambiguous_path_is_rejected_without_writing(tmp_path, name):
    with pytest.raises(p.ProtocolError, match="archive_invalid"):
        x._entry_map(zipped([(name, b"bad")]))
    with pytest.raises(p.ProtocolError, match="archive_invalid"):
        x._extract({name: b"bad"}, tmp_path)
    assert not tuple(tmp_path.iterdir())


def test_case_insensitive_archive_aliases_are_rejected_before_extract(tmp_path):
    values = {"one/Foo": b"a", "ONE/foo": b"b"}
    with pytest.raises(p.ProtocolError, match="archive_invalid"):
        x._entry_map(zipped(list(values.items())))
    with pytest.raises(p.ProtocolError, match="archive_invalid"):
        x._extract(values, tmp_path)
    assert not tuple(tmp_path.iterdir())


@pytest.mark.parametrize("mode", [stat.S_IFLNK, stat.S_IFIFO, stat.S_IFCHR])
def test_archive_rejects_links_and_device_nodes(mode):
    info = ZipInfo("bad")
    info.external_attr = (mode | 0o777) << 16
    with pytest.raises(p.ProtocolError, match="archive_invalid"):
        x._entry_map(zipped([(info, b"bad")]))


def test_duplicate_and_broken_archives_fail_closed():
    with pytest.warns(UserWarning):
        raw = zipped([("same", b"a"), ("same", b"b")])
    for invalid in (raw, b"bad zip", b""):
        with pytest.raises(p.ProtocolError, match="archive_invalid"):
            x._entry_map(invalid)


def test_archive_and_jar_identity_are_content_bound(tmp_path):
    values = x._entry_map(zipped([("safe/a", b"one"), ("safe/b", b"two")]))
    x._extract(values, tmp_path)
    assert (tmp_path / "safe/a").read_bytes() == b"one"
    with pytest.raises(FileExistsError):
        x._extract(values, tmp_path)
    with pytest.raises(p.ProtocolError, match="config_drift"):
        x._artifacts(jar("old"), config_raw=b"changed")
    with pytest.raises(p.ProtocolError, match="artifact_invalid"):
        x._artifacts(zipped([(x.JAR_CONFIG, b"synthetic-config")]), config_raw=b"synthetic-config")


@pytest.mark.parametrize("failure", ["timeout", "exit", "oversize"])
def test_subprocess_failure_has_finite_reason_no_raw_exception_or_options(monkeypatch, tmp_path, failure):
    seen = []
    monkeypatch.setattr(x.os, "environ", {"JAVA_HOME": "synthetic", "PATH": "safe",
        "LLM_API_KEY": "synthetic-do-not-inherit", "JAVA_TOOL_OPTIONS": "synthetic-do-not-inherit"})
    def run(args, **kwargs):
        seen.append((args, kwargs))
        if failure == "timeout":
            raise subprocess.TimeoutExpired(args, 1, output=b"private", stderr=b"private")
        return subprocess.CompletedProcess(args, 1 if failure == "exit" else 0,
            stdout=b"x" * (2 * 1024 * 1024 + 1) if failure == "oversize" else b"", stderr=b"private")
    monkeypatch.setattr(x.subprocess, "run", run)
    with pytest.raises(p.ProtocolError, match="offline_command_failed") as caught:
        x._command(["fake-java"], cwd=tmp_path)
    assert caught.value.__context__ is None and caught.value.__cause__ is None
    assert seen[0][1]["env"] == {"JAVA_HOME": "synthetic", "PATH": "safe"}
    assert "shell" not in seen[0][1] and seen[0][1]["check"] is False


def test_project_invokes_actual_inspector_with_ten_questions_in_memory(monkeypatch, tmp_path, draft):
    commands = []
    def command(args, **kwargs):
        commands.append((args, kwargs))
        return b"" if "-proc:none" in args else outputs(draft, "current")
    monkeypatch.setattr(x, "_command", command)
    result = x._project(jar("current"), draft=draft, arm="current", config_raw=b"synthetic-config",
        inspector_raw=x.INSPECTOR.read_bytes(), java=Path("java"), javac=Path("javac"), root=tmp_path)
    assert len(result.rows) == 11 and len(commands) == 2
    assert "-proc:none" in commands[0][0]
    assert "com.dylan.esquery.service.DocumentNumberProjection" in commands[1][0]
    sent = json.loads(commands[1][1]["input_raw"])
    assert len(sent) == 11 and sent[5]["domain"] == "tax.policy" and sent[6]["domain"] == "tax.law"
    assert all(row["question"] == next(case.plan.original_question for case in draft.cases
                                     if case.case_id == row["caseId"]) for row in sent)


def test_raw_java_numeric_spelling_is_not_rounded_by_hash_projection(draft):
    raw = outputs(draft, "old")
    # Benign numeric shape is strict: size21.0 is rejected rather than normalized
    # to21. Future allowed decimals must retain their actual Java spelling.
    with pytest.raises(p.ProtocolError):
        x._parse_projection(raw.replace(b'"size":21', b'"size":21.0', 1), draft=draft, arm="old")
    value = {"size": 21}
    assert _request_hashes("POST", b'{"size":21}')[1] != _request_hashes("POST", b'{"size":21.0}')[1]
    assert value["size"] == 21


def test_complete_offline_build_flow_is_isolated_and_not_real_execution(monkeypatch, tmp_path, draft):
    config = b"synthetic-config"
    archive = zipped([(x.CONFIG, config), (p.HELPER, b"synthetic-current"), ("serviceCenter/pom.xml", b"pom")])
    monkeypatch.setattr(p, "draft_from_repository", lambda root: draft)
    def git(root, *args):
        if args[0] == "archive":
            return archive
        if "--format=%ct" in args:
            return b"1791080000\n"
        return config if args[-1].endswith(x.CONFIG) else b"synthetic-old" if args[-1].startswith(p.OLD_HEAD) else b"synthetic-current"
    monkeypatch.setattr(p, "_git", git)
    maven = tmp_path / "maven/bin/mvn.cmd"
    maven.parent.mkdir(parents=True)
    maven.write_bytes(b"wrapper-not-executed")
    (maven.parent / "m2.conf").write_bytes(b"config")
    loader = tmp_path / "maven/boot/plexus-classworlds-1.jar"
    loader.parent.mkdir()
    loader.write_bytes(b"loader")
    home = tmp_path / "jdk"
    (home / "bin").mkdir(parents=True)
    for name in ("java.exe", "javac.exe", "java", "javac"):
        (home / "bin" / name).write_bytes(b"fake-executable")
    monkeypatch.setenv("JAVA_HOME", str(home))
    monkeypatch.setattr(x.shutil, "which", lambda _: str(maven))
    builds = []
    def command(args, **kwargs):
        if "-version" in args:
            return b'java version "25.0.2"'
        root = kwargs["cwd"]
        if "org.codehaus.plexus.classworlds.launcher.Launcher" in args:
            assert "--offline" in args and "-DskipTests" in args and str(maven) not in args
            assert "-Dproject.build.outputTimestamp=1791080000" in args
            build = root.parent
            builds.append(build)
            jar_file = build / "es-query-service/target/es-query-service-0.0.1-SNAPSHOT.jar"
            jar_file.parent.mkdir(parents=True)
            jar_file.write_bytes(jar(build.name))
            assert (build / p.HELPER).read_bytes() == (b"synthetic-old" if build.name == "old" else b"synthetic-current")
            return b"build-success"
        return b"" if "-proc:none" in args else outputs(draft, "old" if root.name.startswith("old") else "current")
    monkeypatch.setattr(x, "_command", command)
    result = x.offline_project_repository(tmp_path)
    assert result["realExecutionAllowed"] is False and result["networkRequests"] == result["servicesStarted"] == 0
    assert result["mavenTestsExecuted"] is False and result["temporaryBuildsRemoved"] is True
    assert result["qualityAssessment"] == "Not assessed" and len(result["proofs"]) == 2
    assert all(not build.exists() for build in builds)
    assert (maven.parent / "m2.conf").read_bytes() == b"config"


def test_inspector_never_constructs_network_or_spring_context_and_binds_each_domain():
    source = x.INSPECTOR.read_text(encoding="utf-8")
    assert "new KnowledgeSearchService(null," in source and "service.buildSearchBody(request, profile)" in source
    assert "tax-law-v1" in source and "tax-policy-v1" in source
    assert "new RestClient" not in source and "SpringApplication" not in source
    assert "System.getenv" not in source
