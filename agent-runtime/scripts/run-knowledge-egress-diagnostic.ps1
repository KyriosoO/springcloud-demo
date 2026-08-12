[CmdletBinding()]
param(
    [string]$RepositoryRoot = (Split-Path -Parent (Split-Path -Parent $PSScriptRoot)),
    [string]$ReadAlias = 'agent-doc-tax-policy-v2-read',
    [string]$ExpectedIndexName = 'agent-doc-tax-policy-v3-20260803-agent-read-v1',
    [string]$ExpectedIndexUuid = 'k97bn1gxROSfVm7zGfzbOg',
    [string]$MappingVersion = 'agent-knowledge-tax-v1',
    [string]$PolicySnapshotId = '7c71202794927a9497fed9df7cc0db5a052a53f0f6c2afdb6c0a16089f1c96ed',
    [string]$LawSnapshotId = '99ae962ae1c8e5026187c864eada38b3c3b82d6b017e6e8f076f116aba53fce2'
)

$ErrorActionPreference = 'Stop'
$repository = [IO.Path]::GetFullPath($RepositoryRoot)
if ($repository -ne 'D:\codex') {
    throw 'knowledge.egress_diagnostic_repository_invalid'
}

$ownedPorts = 8090, 9201
$dependencyPorts = 9200, 8908, 8909
if (Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue | Where-Object { $ownedPorts -contains $_.LocalPort }) {
    throw 'knowledge.egress_diagnostic_owned_port_occupied'
}
foreach ($port in $dependencyPorts) {
    if (-not (Get-NetTCPConnection -State Listen -LocalPort $port -ErrorAction SilentlyContinue)) {
        throw "knowledge.egress_diagnostic_dependency_unavailable:$port"
    }
}

$embeddingWarmup = Invoke-RestMethod -Uri 'http://127.0.0.1:8908/embed' -Method Post `
    -ContentType 'application/json' -Body '{"texts":["税务政策公开信息"]}' -TimeoutSec 30
if ($embeddingWarmup.dim -ne 1024 -or $embeddingWarmup.vectors.Count -ne 1) {
    throw 'knowledge.egress_diagnostic_embedding_warmup_failed'
}
$rerankWarmup = Invoke-RestMethod -Uri 'http://127.0.0.1:8909/rerank' -Method Post `
    -ContentType 'application/json' `
    -Body '{"query":"税务政策","documents":["税务政策公开信息"],"top_n":1,"normalize":true}' `
    -TimeoutSec 30
if ($rerankWarmup.model -ne 'BAAI/bge-reranker-v2-m3' -or $rerankWarmup.results.Count -ne 1) {
    throw 'knowledge.egress_diagnostic_rerank_warmup_failed'
}

$runtimeRoot = Join-Path $repository 'agent-runtime'
$evidenceRoot = Join-Path $runtimeRoot 'tests\integration\knowledge\evidence'
$preflightPythonPath = [Environment]::GetEnvironmentVariable('PYTHONPATH', 'Process')
Push-Location $runtimeRoot
try {
    $env:PYTHONPATH = 'src'
    python tools/validate_knowledge_egress_catalog.py `
        --catalog src/agent_runtime/knowledge/evidence/egress-policy-catalog.json `
        --manifest tests/integration/knowledge/evidence/knowledge-egress-export-20260812-01.manifest.json
    if ($LASTEXITCODE -ne 0) {
        throw 'knowledge.egress_diagnostic_catalog_preflight_failed'
    }
    python -m pytest `
        tests/integration/knowledge/test_egress_diagnostic_evidence.py `
        tests/integration/knowledge/test_egress_attempt_journal.py `
        tests/integration/knowledge/test_knowledge_egress_live_harness.py `
        -q --tb=short
    if ($LASTEXITCODE -ne 0) {
        throw 'knowledge.egress_diagnostic_non_live_preflight_failed'
    }
} finally {
    Pop-Location
    [Environment]::SetEnvironmentVariable('PYTHONPATH', $preflightPythonPath, 'Process')
}

$environmentNames = @(
    'COMMON_SECURITY_JWT_HMAC_KEY_ACTIVE',
    'AGENT_KNOWLEDGE_READ_ALIAS',
    'AGENT_KNOWLEDGE_EXPECTED_INDEX_NAME',
    'AGENT_KNOWLEDGE_EXPECTED_INDEX_UUID',
    'AGENT_KNOWLEDGE_MAPPING_VERSION',
    'AGENT_KNOWLEDGE_POLICY_SNAPSHOT_ID',
    'AGENT_KNOWLEDGE_LAW_SNAPSHOT_ID',
    'RUN_KNOWLEDGE_EGRESS_DIAGNOSTIC',
    'AGENT_KNOWLEDGE_ES_BASE_URL',
    'AGENT_KNOWLEDGE_EMBEDDING_BASE_URL',
    'AGENT_KNOWLEDGE_RERANK_BASE_URL',
    'AGENT_KNOWLEDGE_ADMIN_JWT',
    'AGENT_KNOWLEDGE_EGRESS_DIAGNOSTIC_OUTPUT',
    'PYTHONPATH'
)
$environmentSnapshot = @{}
foreach ($name in $environmentNames) {
    $environmentSnapshot[$name] = [Environment]::GetEnvironmentVariable($name, 'Process')
}

$tempBase = [IO.Path]::GetFullPath([IO.Path]::GetTempPath())
$runRoot = Join-Path $tempBase "codex-k-egress-diagnostic-$([Guid]::NewGuid().ToString('N'))"
New-Item -ItemType Directory -Path $runRoot | Out-Null
$authOut = Join-Path $runRoot 'auth.out.log'
$authErr = Join-Path $runRoot 'auth.err.log'
$esOut = Join-Path $runRoot 'es.out.log'
$esErr = Join-Path $runRoot 'es.err.log'
$stagedEvidence = Join-Path $runRoot 'knowledge-egress-diagnostic.json'

$keyBytes = [Security.Cryptography.RandomNumberGenerator]::GetBytes(48)
$secret = [Convert]::ToBase64String($keyBytes)
$env:COMMON_SECURITY_JWT_HMAC_KEY_ACTIVE = $secret
$env:AGENT_KNOWLEDGE_READ_ALIAS = $ReadAlias
$env:AGENT_KNOWLEDGE_EXPECTED_INDEX_NAME = $ExpectedIndexName
$env:AGENT_KNOWLEDGE_EXPECTED_INDEX_UUID = $ExpectedIndexUuid
$env:AGENT_KNOWLEDGE_MAPPING_VERSION = $MappingVersion
$env:AGENT_KNOWLEDGE_POLICY_SNAPSHOT_ID = $PolicySnapshotId
$env:AGENT_KNOWLEDGE_LAW_SNAPSHOT_ID = $LawSnapshotId

$commonArgs = @(
    '--spring.cloud.config.enabled=false',
    '--spring.config.additional-location=optional:file:D:/codex/config-service/src/main/resources/config/',
    '--eureka.client.enabled=false',
    '--common.security.secrets.source-order[0]=environment',
    '--common.security.secrets.allow-config-values=false',
    '--common.security.secrets.fail-fast=true',
    '--common.security.secrets.jwt.active-key-id=ACTIVE',
    '--common.security.secrets.jwt.keys.ACTIVE.env=COMMON_SECURITY_JWT_HMAC_KEY_ACTIVE',
    '--common.security.secrets.jwt.keys.ACTIVE.value='
)
$authProcess = $null
$esProcess = $null
$adminToken = $null
$questions = @(
    '增值税小规模纳税人的现行税收政策有哪些',
    '个人所得税法关于居民个人有哪些规定',
    '税收征收管理法律与现行税务政策如何衔接'
)
$logLeakDetected = $false

function Wait-Ready([string]$Uri, [Diagnostics.Process]$Process) {
    for ($attempt = 0; $attempt -lt 90; $attempt++) {
        if ($Process.HasExited) {
            throw 'knowledge.egress_diagnostic_process_exited'
        }
        try {
            $response = Invoke-WebRequest -Uri $Uri -Method Get -TimeoutSec 2 -SkipHttpErrorCheck
            if ($response.StatusCode -eq 200) {
                return
            }
        } catch {
        }
        Start-Sleep -Milliseconds 500
    }
    throw 'knowledge.egress_diagnostic_readiness_timeout'
}

function Get-LocalPassword([string]$User) {
    $path = Join-Path $repository 'auth-service\src\main\resources\auth-users.yml'
    $text = Get-Content -LiteralPath $path -Raw -Encoding UTF8
    $match = [regex]::Match($text, "(?ms)^\s{4}${User}:\s*\r?\n\s+password:\s*([^\r\n]+)")
    if (-not $match.Success) {
        throw 'knowledge.egress_diagnostic_auth_fixture_missing'
    }
    $stored = $match.Groups[1].Value.Trim().Trim('"').Trim("'")
    if (-not $stored.StartsWith('{noop}')) {
        throw 'knowledge.egress_diagnostic_auth_fixture_not_local'
    }
    return $stored.Substring(6)
}

function Get-LoginToken([string]$User) {
    $session = [Microsoft.PowerShell.Commands.WebRequestSession]::new()
    $body = @{ userId = $User; password = (Get-LocalPassword $User) } | ConvertTo-Json -Compress
    $response = Invoke-WebRequest -Uri 'http://127.0.0.1:8090/login' -Method Post `
        -ContentType 'application/json' -Body $body -WebSession $session -TimeoutSec 5 -SkipHttpErrorCheck
    if ($response.StatusCode -ne 200) {
        throw 'knowledge.egress_diagnostic_login_failed'
    }
    $cookie = $session.Cookies.GetCookies('http://127.0.0.1:8090')['AUTH_TOKEN']
    if ($null -eq $cookie -or [string]::IsNullOrWhiteSpace($cookie.Value)) {
        throw 'knowledge.egress_diagnostic_token_missing'
    }
    return $cookie.Value
}

function Test-SensitiveLogValue {
    $logs = (Get-Content -LiteralPath $authOut, $authErr, $esOut, $esErr -Raw -ErrorAction SilentlyContinue) -join "`n"
    foreach ($sensitive in @($secret, $adminToken) + $questions) {
        if ($sensitive -and $logs.Contains([string]$sensitive)) {
            return $true
        }
    }
    return $false
}

try {
    $authJar = Join-Path $repository 'auth-service\target\auth-service-0.0.1-SNAPSHOT.jar'
    $authProcess = Start-Process -FilePath 'java' -ArgumentList (@('-jar', $authJar) + $commonArgs) `
        -WorkingDirectory (Join-Path $repository 'auth-service') -WindowStyle Hidden -PassThru `
        -RedirectStandardOutput $authOut -RedirectStandardError $authErr

    $esJar = Join-Path $repository 'es-query-service\target\es-query-service-0.0.1-SNAPSHOT.jar'
    $esArgs = @(
        '-jar', $esJar,
        '--spring.profiles.active=datasource,es,knowledge-live',
        '--spring.elasticsearch.uris=http://127.0.0.1:9200',
        '--es.query.total-hits-threshold=10000',
        '--es.query.rebuild-source-allowed-hosts[0]=localhost',
        '--es.query.rebuild-max-batch-size=500'
    ) + $commonArgs
    $esProcess = Start-Process -FilePath 'java' -ArgumentList $esArgs `
        -WorkingDirectory (Join-Path $repository 'es-query-service') -WindowStyle Hidden -PassThru `
        -RedirectStandardOutput $esOut -RedirectStandardError $esErr

    Wait-Ready 'http://127.0.0.1:8090/public/test' $authProcess
    Wait-Ready 'http://127.0.0.1:9201/actuator/health' $esProcess
    $adminToken = Get-LoginToken 'admin'

    $env:RUN_KNOWLEDGE_EGRESS_DIAGNOSTIC = '1'
    $env:AGENT_KNOWLEDGE_ES_BASE_URL = 'http://127.0.0.1:9201'
    $env:AGENT_KNOWLEDGE_EMBEDDING_BASE_URL = 'http://127.0.0.1:8908'
    $env:AGENT_KNOWLEDGE_RERANK_BASE_URL = 'http://127.0.0.1:8909'
    $env:AGENT_KNOWLEDGE_ADMIN_JWT = $adminToken
    $env:AGENT_KNOWLEDGE_EGRESS_DIAGNOSTIC_OUTPUT = $stagedEvidence
    $env:PYTHONPATH = 'src'

    Push-Location $runtimeRoot
    try {
        python -m pytest tests/integration/knowledge/test_real_knowledge_egress_diagnostic.py -q -s --tb=short
        $pytestExitCode = $LASTEXITCODE
    } finally {
        Pop-Location
    }

    $logLeakDetected = Test-SensitiveLogValue
    if ($logLeakDetected) {
        throw 'knowledge.egress_diagnostic_log_leak'
    }
    if ($pytestExitCode -ne 0) {
        throw 'knowledge.egress_diagnostic_integration_failed'
    }
    if (-not (Test-Path -LiteralPath $stagedEvidence)) {
        throw 'knowledge.egress_diagnostic_evidence_missing'
    }

    $stamp = [DateTime]::UtcNow.ToString('yyyyMMddTHHmmssZ')
    $finalEvidence = Join-Path $evidenceRoot "wp-k-egress-diagnostic-$stamp.json"
    if (Test-Path -LiteralPath $finalEvidence) {
        throw 'knowledge.egress_diagnostic_evidence_conflict'
    }
    Move-Item -LiteralPath $stagedEvidence -Destination $finalEvidence

    [pscustomobject]@{
        status = 'passed'
        realRetrievalCases = 3
        localSummaryCalls = 3
        externalModelCalls = 0
        negativeCases = 5
        logLeakCount = 0
        evidence = $finalEvidence
    }
} finally {
    foreach ($process in @($esProcess, $authProcess)) {
        if ($null -ne $process -and -not $process.HasExited) {
            Stop-Process -Id $process.Id -ErrorAction SilentlyContinue
            if (-not $process.WaitForExit(5000)) {
                Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
            }
        }
    }
    if (-not $logLeakDetected) {
        $logLeakDetected = Test-SensitiveLogValue
    }
    [Array]::Clear($keyBytes, 0, $keyBytes.Length)
    $secret = $null
    $adminToken = $null
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
