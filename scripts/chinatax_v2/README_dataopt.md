# Chinatax v2 Data Optimization Runbook

This runbook documents the data-layer optimization flow for the tax-policy document retrieval index.
It does not require Java service code changes.

## Scope

The optimization implements six data-layer actions:

1. Build a versioned gold-query set for core tax-policy questions.
2. Build a new ES index with Chinese tax-policy analyzers instead of the old `standard` analyzer.
3. Enrich metadata for retrieval and rerank signals.
4. Reshape chunks and enrich embedding input text.
5. Re-run BGE embeddings into the candidate index and compare retrieval metrics.
6. Add current-answer curated chunks with source references and validation gates.

## Artifacts

| Path | Purpose |
| --- | --- |
| `tax_policy_gold_queries.v1.json` | Core gold-query set. |
| `build_chinatax_dataopt_index.py` | Builds the candidate data-optimized index from the current v2 ES index. |
| `evaluate_tax_policy_retrieval.py` | Runs gold-query hybrid retrieval against an index or alias. |
| `validate_curated_sources.py` | Verifies curated summary chunks reference real source chunks. |
| `dataopt_cutover_readiness.py` | Builds a read-only cutover readiness report. |
| `switch_dataopt_alias.py` | Dry-run-first alias cutover and rollback helper. |

## Candidate Index

Default candidate index:

```powershell
agent-doc-tax-policy-v3-20260710-dataopt-bge-m3
```

Default candidate aliases:

```powershell
agent-doc-tax-policy-v3-dataopt-read
agent-doc-tax-policy-v3-dataopt-write
```

Current production aliases remain:

```powershell
agent-doc-tax-policy-v2-read
agent-doc-tax-policy-v2-write
```

## Build

Dry-run on a small sample:

```powershell
python scripts\chinatax_v2\build_chinatax_dataopt_index.py --dry-run --limit-documents 5
```

Build or rebuild the candidate index:

```powershell
python scripts\chinatax_v2\build_chinatax_dataopt_index.py --target-index agent-doc-tax-policy-v3-20260710-dataopt-bge-m3 --recreate
```

The build reads from `agent-doc-tax-policy-v2-read`, writes a new candidate index, and does not switch production aliases unless `--switch-alias` is explicitly provided.

## Validate

Run gold-query retrieval:

```powershell
python scripts\chinatax_v2\evaluate_tax_policy_retrieval.py --index agent-doc-tax-policy-v3-dataopt-read --output .tmp\chinatax-v2\dataopt-alias-gold-report.json
```

Validate curated summary sources:

```powershell
python scripts\chinatax_v2\validate_curated_sources.py --target-index agent-doc-tax-policy-v3-dataopt-read --source-index agent-doc-tax-policy-v2-read --output .tmp\chinatax-v2\curated-source-report.json
```

Build the cutover readiness report:

```powershell
python scripts\chinatax_v2\dataopt_cutover_readiness.py --output .tmp\chinatax-v2\dataopt-cutover-readiness.json
```

Expected gate before cutover:

- `readyForManualCutover=true`
- `topKHitRate >= 1.0`
- `mrr >= 0.85`
- `missingSourceReferenceCount=0`
- `titleMismatchCount=0`
- candidate alias resolves to a different index than the current production alias

## Cutover

Preview the production alias switch:

```powershell
python scripts\chinatax_v2\switch_dataopt_alias.py --output .tmp\chinatax-v2\dataopt-alias-switch-plan.json
```

Execute only after manual approval:

```powershell
python scripts\chinatax_v2\switch_dataopt_alias.py --execute
```

Rollback dry-run:

```powershell
python scripts\chinatax_v2\switch_dataopt_alias.py --rollback --output .tmp\chinatax-v2\dataopt-alias-rollback-plan.json
```

Rollback execute:

```powershell
python scripts\chinatax_v2\switch_dataopt_alias.py --rollback --execute
```

## Post-cutover Checks

After cutover, run representative `/agent/chat` questions:

```text
增值税有哪些税率？
目前增值税一般纳税人适用的税率有哪些？
小规模纳税人增值税征收率是多少？
企业所得税税率是多少？
```

If generation quality regresses, execute rollback and preserve the reports under `.tmp/chinatax-v2/` for diagnosis.

## Current Known Risk

The curated summary chunks are marked `NEEDS_HUMAN_REVIEW`. They are source-linked and gate-validated, but they should not be treated as manually approved legal content until reviewed.
