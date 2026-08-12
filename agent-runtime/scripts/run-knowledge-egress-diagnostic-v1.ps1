[CmdletBinding()]
param(
    [string]$RepositoryRoot = (Split-Path -Parent (Split-Path -Parent $PSScriptRoot)),
    [string]$AuthorizedRunId,
    [string]$AuthorizedManifestSha256,
    [string]$AuthorizationReference
)

$ErrorActionPreference = 'Stop'
$repository = [IO.Path]::GetFullPath($RepositoryRoot)
if ($repository -ne 'D:\codex') {
    throw 'knowledge.egress_diagnostic_repository_invalid'
}

$expectedRunId = 'knowledge-egress-diagnostic-v1-20260812-candidate-01'
$expectedAuthorizationReference = 'P3_00:GATE-041'
$runtimeRoot = Join-Path $repository 'agent-runtime'
$evidenceRoot = Join-Path $runtimeRoot 'tests\integration\knowledge\evidence'
$candidateManifest = Join-Path $evidenceRoot 'knowledge-egress-diagnostic-v1-20260812-candidate-01.manifest.json'
$consumedPath = Join-Path $evidenceRoot 'gate041-knowledge-egress-diagnostic-v1-20260812-candidate-01.consumed.json'

if (
    $AuthorizedRunId -ne $expectedRunId -or
    $AuthorizationReference -ne $expectedAuthorizationReference -or
    $AuthorizedManifestSha256 -notmatch '^[0-9a-f]{64}$'
) {
    throw 'knowledge.egress_diagnostic_authorization_binding_invalid'
}
$actualManifestSha256 = (Get-FileHash -LiteralPath $candidateManifest -Algorithm SHA256).Hash.ToLowerInvariant()
if ($actualManifestSha256 -ne $AuthorizedManifestSha256) {
    throw 'knowledge.egress_diagnostic_manifest_hash_mismatch'
}
if (Test-Path -LiteralPath $consumedPath) {
    throw 'knowledge.egress_diagnostic_authorization_consumed'
}

$previousPythonPath = [Environment]::GetEnvironmentVariable('PYTHONPATH', 'Process')
Push-Location $runtimeRoot
try {
    $env:PYTHONPATH = 'src'
    python -m pytest `
        tests/unit/knowledge/evidence/test_summary_validation_reasons.py `
        tests/integration/knowledge/test_egress_diagnostic_journal.py `
        tests/integration/knowledge/test_knowledge_egress_diagnostic_harness.py `
        tests/integration/knowledge/test_egress_diagnostic_candidate_manifest.py `
        tests/integration/knowledge/test_egress_live_candidate_manifest.py `
        -q --tb=short
    if ($LASTEXITCODE -ne 0) {
        throw 'knowledge.egress_diagnostic_non_live_preflight_failed'
    }
} finally {
    Pop-Location
    [Environment]::SetEnvironmentVariable('PYTHONPATH', $previousPythonPath, 'Process')
}

foreach ($port in 9201, 8908, 8909) {
    if (-not (Get-NetTCPConnection -State Listen -LocalPort $port -ErrorAction SilentlyContinue)) {
        throw "knowledge.egress_diagnostic_dependency_unavailable:$port"
    }
}
$adminToken = [Environment]::GetEnvironmentVariable('AGENT_KNOWLEDGE_ADMIN_JWT', 'Process')
if ([string]::IsNullOrWhiteSpace($adminToken)) {
    throw 'knowledge.egress_diagnostic_admin_jwt_missing'
}
$apiKey = [Environment]::GetEnvironmentVariable('LLM_API_KEY', 'Process')
if ([string]::IsNullOrWhiteSpace($apiKey)) {
    throw 'knowledge.egress_diagnostic_api_key_missing'
}

$environmentNames = @(
    'RUN_KNOWLEDGE_EGRESS_DIAGNOSTIC_V1',
    'AGENT_KNOWLEDGE_ES_BASE_URL',
    'AGENT_KNOWLEDGE_EMBEDDING_BASE_URL',
    'AGENT_KNOWLEDGE_RERANK_BASE_URL',
    'AGENT_KNOWLEDGE_DIAGNOSTIC_RESULT_OUTPUT',
    'AGENT_KNOWLEDGE_DIAGNOSTIC_CONSUMED_OUTPUT',
    'AGENT_KNOWLEDGE_DIAGNOSTIC_JOURNAL_OUTPUT',
    'AGENT_KNOWLEDGE_DIAGNOSTIC_RUN_ID',
    'AGENT_KNOWLEDGE_DIAGNOSTIC_AUTHORIZATION_REFERENCE',
    'AGENT_KNOWLEDGE_DIAGNOSTIC_MANIFEST_SHA256',
    'AGENT_MODEL_PROVIDER',
    'AGENT_MODEL_MAX_CONCURRENCY',
    'PYTHONPATH'
)
$environmentSnapshot = @{}
foreach ($name in $environmentNames) {
    $environmentSnapshot[$name] = [Environment]::GetEnvironmentVariable($name, 'Process')
}

$tempBase = [IO.Path]::GetFullPath([IO.Path]::GetTempPath())
$runRoot = Join-Path $tempBase "codex-k-egress-diagnostic-$([Guid]::NewGuid().ToString('N'))"
New-Item -ItemType Directory -Path $runRoot | Out-Null
$pytestLog = Join-Path $runRoot 'pytest.log'
$stagedResult = Join-Path $runRoot 'diagnostic-result.json'
$stagedJournal = Join-Path $runRoot 'diagnostic-attempt.jsonl'
$pytestExitCode = $null
$logLeakDetected = $false
$questions = @(
    '增值税小规模纳税人的现行税收政策有哪些',
    '个人所得税法关于居民个人有哪些规定',
    '税收征收管理法律与现行税务政策如何衔接'
)

function Test-SensitiveLogValue {
    $text = Get-Content -LiteralPath $pytestLog -Raw -ErrorAction SilentlyContinue
    foreach ($sensitive in @($apiKey, $adminToken) + $questions) {
        if ($sensitive -and $text.Contains([string]$sensitive)) {
            return $true
        }
    }
    return $false
}

try {
    $env:RUN_KNOWLEDGE_EGRESS_DIAGNOSTIC_V1 = '1'
    $env:AGENT_KNOWLEDGE_ES_BASE_URL = 'http://127.0.0.1:9201'
    $env:AGENT_KNOWLEDGE_EMBEDDING_BASE_URL = 'http://127.0.0.1:8908'
    $env:AGENT_KNOWLEDGE_RERANK_BASE_URL = 'http://127.0.0.1:8909'
    $env:AGENT_KNOWLEDGE_DIAGNOSTIC_RESULT_OUTPUT = $stagedResult
    $env:AGENT_KNOWLEDGE_DIAGNOSTIC_CONSUMED_OUTPUT = $consumedPath
    $env:AGENT_KNOWLEDGE_DIAGNOSTIC_JOURNAL_OUTPUT = $stagedJournal
    $env:AGENT_KNOWLEDGE_DIAGNOSTIC_RUN_ID = $AuthorizedRunId
    $env:AGENT_KNOWLEDGE_DIAGNOSTIC_AUTHORIZATION_REFERENCE = $AuthorizationReference
    $env:AGENT_KNOWLEDGE_DIAGNOSTIC_MANIFEST_SHA256 = $AuthorizedManifestSha256
    $env:AGENT_MODEL_PROVIDER = 'deepseek'
    $env:AGENT_MODEL_MAX_CONCURRENCY = '1'
    $env:PYTHONPATH = 'src'

    Push-Location $runtimeRoot
    try {
        & python -m pytest tests/integration/knowledge/test_real_knowledge_egress_diagnostic_v1.py -q -s --tb=short *> $pytestLog
        $pytestExitCode = $LASTEXITCODE
    } finally {
        Pop-Location
    }

    $logLeakDetected = Test-SensitiveLogValue
    if ($logLeakDetected) {
        throw 'knowledge.egress_diagnostic_log_leak'
    }
    if (-not (Test-Path -LiteralPath $stagedResult) -and (Test-Path -LiteralPath $stagedJournal)) {
        Push-Location $runtimeRoot
        try {
            python -c "from pathlib import Path; from tests.integration.knowledge.egress_diagnostic_journal import write_diagnostic_result_from_journal; write_diagnostic_result_from_journal(journal_path=Path(r'$stagedJournal'), output_path=Path(r'$stagedResult'))"
        } finally {
            Pop-Location
        }
    }
    if (-not (Test-Path -LiteralPath $stagedResult) -or -not (Test-Path -LiteralPath $stagedJournal)) {
        throw 'knowledge.egress_diagnostic_evidence_missing'
    }
    Push-Location $runtimeRoot
    try {
        python -m tests.integration.knowledge.egress_diagnostic_journal $stagedJournal $stagedResult
        if ($LASTEXITCODE -ne 0) {
            throw 'knowledge.egress_diagnostic_evidence_invalid'
        }
    } finally {
        Pop-Location
    }

    $stamp = [DateTime]::UtcNow.ToString('yyyyMMddTHHmmssZ')
    $suffix = if ($pytestExitCode -eq 0) { 'json' } else { 'failed.json' }
    $finalResult = Join-Path $evidenceRoot "wp-k-egress-diagnostic-01-$stamp.$suffix"
    $finalJournal = Join-Path $evidenceRoot "wp-k-egress-diagnostic-01-$stamp.attempt.jsonl"
    if ((Test-Path -LiteralPath $finalResult) -or (Test-Path -LiteralPath $finalJournal)) {
        throw 'knowledge.egress_diagnostic_evidence_conflict'
    }
    Move-Item -LiteralPath $stagedResult -Destination $finalResult
    Move-Item -LiteralPath $stagedJournal -Destination $finalJournal
    if ($pytestExitCode -ne 0) {
        throw 'knowledge.egress_diagnostic_integration_failed'
    }

    [pscustomobject]@{
        status = 'diagnostic_completed'
        summaryCalls = 9
        retryCount = 0
        logLeakCount = 0
        result = $finalResult
        journal = $finalJournal
    }
} finally {
    if (-not $logLeakDetected) {
        $logLeakDetected = Test-SensitiveLogValue
    }
    $adminToken = $null
    $apiKey = $null
    foreach ($name in $environmentNames) {
        [Environment]::SetEnvironmentVariable($name, $environmentSnapshot[$name], 'Process')
    }
    $resolvedRunRoot = [IO.Path]::GetFullPath($runRoot)
    if ($resolvedRunRoot.StartsWith($tempBase, [StringComparison]::OrdinalIgnoreCase) -and (Test-Path -LiteralPath $resolvedRunRoot)) {
        Remove-Item -LiteralPath $resolvedRunRoot -Recurse -Force
    }
    if ($logLeakDetected) {
        throw 'knowledge.egress_diagnostic_log_leak'
    }
}
