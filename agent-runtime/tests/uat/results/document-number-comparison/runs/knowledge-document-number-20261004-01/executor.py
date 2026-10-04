"""One-shot human-authorized preparation; no comparison, inference or service."""
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from pathlib import Path
import json
import os
import re
import sys

ROOT = Path('D:/codex')
sys.path[:0] = [str(ROOT / 'agent-runtime'), str(ROOT / 'agent-runtime/src'),
                str(ROOT / 'knowledge-corpus-tools/src')]
import httpx
from tests.evaluation.knowledge import rebuild_document_number_comparison as p
from tests.evaluation.knowledge.rebuild_document_number_projection import projected_java_pair
from tests.evaluation.knowledge.rebuild_document_number_owned import ReadBinding
from tests.evaluation.knowledge.rebuild_document_number_identity import IdentityLedger, IdentitySession, ModelBinding
from tests.evaluation.knowledge.rebuild_document_number_inventory import InventorySession
from tests.evaluation.knowledge.rebuild_document_number_journal import AttemptJournal, JournalBinding, CleanupReport
from tests.evaluation.knowledge.rebuild_document_number_transport import BudgetPlan
from tests.evaluation.knowledge.rebuild_b_local_runner import _bounded_model_process
from knowledge_corpus_tools import b_model_identity_v1 as models

HEAD = '27b18191449b3641a0951fc7e142922d720b2b1b'
RUN = 'knowledge-document-number-20261004-01'
BASE = ROOT / 'agent-runtime/tests/uat/results/document-number-comparison'
DOCKER = Path('C:/Program Files/Docker/Docker/resources/bin/docker.exe')
DOCKER_SHA = '575b19fdc3cc3054714e6cbe92bcf86b708cc5dc46ad5e75bfd7591220de86fe'
HOST = 'npipe:////./pipe/docker_engine'
BINDING = ReadBinding('agent-doc-tax-policy-v2-read', 'agent-doc-tax-policy-v5-20260907-vector-b2',
                      'jJ5Ww3LCRWWycfDkUZvmdw', 'agent-knowledge-tax-v3-policy-context-v1')
MAPPING = '1c2ab9b48ae5b3fcd37b91fec883b6141d3616b2331cdf3a430ea4500a40db82'
N = 15521

def exclusive_write(path, raw):
    with path.open('xb') as stream:
        if stream.write(raw) != len(raw):
            raise p.ProtocolError('preparation_short_write')
        stream.flush()
        os.fsync(stream.fileno())

def main():
    # Checks are local only. No attempt or current external fact is asserted here.
    p.require(p._git(ROOT, 'rev-parse', 'HEAD').decode().strip() == HEAD and
              p._git(ROOT, 'branch', '--show-current').decode().strip() == 'codex_0915' and
              not p._git(ROOT, 'status', '--porcelain=v1', '--untracked-files=no').strip(),
              'preparation_repository_drift')
    models._require_locked_corpus_environment()
    p.require(sha256(DOCKER.read_bytes()).hexdigest() == DOCKER_SHA, 'preparation_docker_drift')
    marker = BASE / 'consumed' / (RUN + '.json')
    directory = BASE / 'runs' / RUN
    p.require(not marker.exists() and not directory.exists(), 'preparation_reuse_forbidden')
    script_sha = sha256(Path(__file__).read_bytes()).hexdigest()
    old = json.loads((ROOT / 'knowledge-corpus-tools/evidence/policy-vector-candidate-20260907-b2/binding.json').read_bytes())
    expected_model = sha256(models._canonical(old['modelSnapshot']['model'])).hexdigest()
    print('offline_build_started', flush=True)
    final = None
    with projected_java_pair() as pair:
        p.require(pair.draft.frozen_head == HEAD, 'preparation_projection_drift')
        now = datetime.now(timezone.utc)
        expires = now + timedelta(minutes=60)
        # Direct human reply to the exact preceding scope is the authority;
        # this envelope records it, and is not a self-issued execution grant.
        grant = {'kind': 'human_authorized_preparation_v1', 'runId': RUN,
            'frozenHead': HEAD, 'reference': 'P3_01:14.56-preparation',
            'humanDecision': '授权，继续推进', 'exclusiveWindowConfirmed': True,
            'createdAt': now.isoformat(), 'expiresAt': expires.isoformat(),
            'esHttpMaximum': 67, 'dockerDiscoveryMaximum': 4, 'modelIdentityMaximum': 4,
            'expectedBinding': asdict(BINDING), 'expectedMappingSha256': MAPPING,
            'expectedCount': N, 'expectedEmbeddingModelSha256': expected_model,
            'dockerExecutableSha256': DOCKER_SHA, 'dockerHost': HOST, 'executorSha256': script_sha,
            'forbidden': {'inference': 0, 'services': 0, 'writes': 0, 'measure': 0, 'retry': 0, 'resume': 0}}
        raw_grant = p.canonical(grant)
        def guard():
            p.require(datetime.now(timezone.utc) < expires, 'preparation_window_expired')
            p.require(p._git(ROOT, 'rev-parse', 'HEAD').decode().strip() == HEAD and
                      not p._git(ROOT, 'status', '--porcelain=v1', '--untracked-files=no').strip(),
                      'preparation_repository_drift')
            p.require(sha256(Path(__file__).read_bytes()).hexdigest() == script_sha and
                      sha256(DOCKER.read_bytes()).hexdigest() == DOCKER_SHA, 'preparation_executor_drift')
        limits = tuple((key, value if key in ('snapshotPreparation', 'preparationMetadata') else 0)
                       for key, value in BudgetPlan(N).rows())
        BASE.joinpath('runs').mkdir(parents=True, exist_ok=True)
        BASE.joinpath('consumed').mkdir(parents=True, exist_ok=True)
        journal = AttemptJournal(directory=directory,
            binding=JournalBinding(RUN, HEAD, sha256(p.canonical(pair.draft.preview())).hexdigest(),
                sha256(p.canonical([asdict(proof) for proof in pair.proofs])).hexdigest(),
                sha256(p.canonical(grant['expectedBinding'])).hexdigest(), sha256(raw_grant).hexdigest(), 'live_attempts'),
            limits=limits, identity_phases=('preparation',), operation_guard=guard)
        def checkpoint(event, ticket, attempt):
            if event == 'started':
                guard()
            journal._append({'event': 'docker_discovery_' + event, 'ticket': ticket,
                             'attempt': None if attempt is None else asdict(attempt)})
        discovery = IdentityLedger(phases=('preparation',), checkpoint=checkpoint)
        client = None
        reason = 'prepared'
        consumed = False
        try:
            exclusive_write(directory / 'authorization.json', raw_grant)
            exclusive_write(directory / 'executor.py', Path(__file__).read_bytes())
            exclusive_write(directory / 'projection.json', p.canonical(pair.report))
            exclusive_write(marker, p.canonical({'runId': RUN, 'frozenHead': HEAD,
                'authorizationSha256': sha256(raw_grant).hexdigest(), 'phase': 'preparation',
                'consumedAt': datetime.now(timezone.utc).isoformat()}))
            consumed = True
            journal._append({'event': 'preparation_consumed', 'nonHttpDiscoveryLimit': 4})
            ids = []
            for port in (8908, 8909):
                for suffix in (['ps', '--filter', f'publish={port}', '--format', '{{.ID}}'],
                               ['inspect', '--format', '{{.Id}}']):
                    command = [str(DOCKER), '--host', HOST, *suffix]
                    if suffix[0] == 'inspect':
                        command.append(short)
                    ticket = discovery.begin('preparation', sum(discovery.view()['counts'].values()), command, b'')
                    try:
                        output = _bounded_model_process(command, payload=b'', timeout=15)
                    except Exception:
                        discovery.finish(ticket, failed=True)
                        raise p.ProtocolError('preparation_discovery_process_failed') from None
                    discovery.finish(ticket, failed=False)
                    lines = output.decode('ascii').strip().splitlines()
                    p.require(len(lines) == 1 and re.fullmatch(r'[0-9a-f]{12,64}', lines[0]) is not None,
                              'preparation_container_not_unique')
                    if suffix[0] == 'ps':
                        short = lines[0]
                    else:
                        p.require(len(lines[0]) == 64 and lines[0].startswith(short), 'preparation_container_drift')
                        ids.append(lines[0])
            p.require(len(set(ids)) == 2, 'preparation_container_collision')
            assert journal.identity_ledger is not None
            model = ModelBinding(ids[0], ids[1], expected_model, DOCKER, DOCKER_SHA, HOST)
            identity = IdentitySession(pair=pair, binding=BINDING, model=model,
                ledger=journal.identity_ledger,
                process=lambda command, raw: _bounded_model_process(command, payload=raw, timeout=300)).capture('preparation')
            exclusive_write(directory / 'identity.json', identity.material)
            print('model_identity_captured_no_inference', flush=True)
            client = httpx.Client(base_url='http://127.0.0.1:9200', trust_env=False,
                follow_redirects=False, timeout=httpx.Timeout(30), transport=httpx.HTTPTransport(retries=0))
            inventory = InventorySession(draft=pair.draft, binding=BINDING, mapping_sha256=MAPPING,
                record_count=N, ledger=journal.ledger, client=client).capture('preparation')
            exclusive_write(directory / 'inventory.json', inventory.inventory)
            exclusive_write(directory / 'captures.json', p.canonical({'identity': identity.preview(), 'inventory': inventory.preview()}))
            guard()
            print('inventory_captured', flush=True)
        except (Exception, KeyboardInterrupt) as error:
            # Exclusive marker creation consumes this identity even when its
            # durable write fails; that failure cannot permit any operation.
            consumed = consumed or marker.exists()
            reason = str(error) if type(error) is p.ProtocolError and re.fullmatch(r'[a-z0-9_]{1,96}', str(error)) else 'preparation_failed'
        finally:
            cleanup_failed = False
            if client is not None:
                try:
                    client.close()
                except Exception:
                    cleanup_failed = True
            for ledger in (discovery, journal.ledger, journal.identity_ledger):
                if ledger is not None:
                    try:
                        ledger.abort()
                    except Exception:
                        cleanup_failed = True
            if cleanup_failed:
                reason = 'preparation_cleanup_failed'
            closure = None
            try:
                p.require(discovery.view()['pending'] == 0, 'preparation_discovery_pending')
                closure = journal.seal_cleanup(CleanupReport(True, client is None or client.is_closed, True, True))
            except Exception:
                reason = 'preparation_journal_seal_failed'
            finally:
                try:
                    journal.dispose()
                except Exception:
                    reason = 'preparation_journal_close_failed'
            http_view = journal.ledger.view()
            identity_view = journal.identity_ledger.view()
            final = {'kind': 'document_number_preparation_result_v1', 'runId': RUN, 'frozenHead': HEAD,
                'status': 'prepared' if reason == 'prepared' else ('failed_consumed' if consumed else 'failed_unconsumed'),
                'reason': reason, 'httpCounts': http_view['counts'], 'dockerDiscoveryCounts': discovery.view()['counts'],
                'modelIdentityCounts': identity_view['counts'], 'journalSealed': closure is not None,
                'unresolvedReceipts': {'http': http_view['pending'], 'identity': identity_view['pending'],
                                       'discovery': discovery.view()['pending']},
                'qualityAssessment': 'Not assessed', 'releaseAllowed': False,
                'modelInference': 0, 'serviceStart': 0, 'indexAliasWrites': 0, 'retry': 0, 'resume': 0}
    # The actual build lease has now closed and removed only its owned temporary tree.
    final['offlineBuildLeaseReleased'] = True
    exclusive_write(directory / 'result.json', p.canonical(final))
    print(json.dumps(final, ensure_ascii=False), flush=True)
    return 0 if final['status'] == 'prepared' else 2

if __name__ == '__main__':
    try:
        sys.exit(main())
    except Exception:
        print('preparation_terminal_executor_failure_no_retry', flush=True)
        sys.exit(3)
