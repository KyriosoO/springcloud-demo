[CmdletBinding()]
param(
    [string]$RepositoryRoot = (Split-Path -Parent (Split-Path -Parent $PSScriptRoot)),
    [Parameter(Mandatory = $true)][string]$AuthorizedRunId,
    [Parameter(Mandatory = $true)][string]$AuthorizedManifestSha256,
    [Parameter(Mandatory = $true)][string]$AuthorizationReference,
    [Parameter(Mandatory = $true)][int]$MaximumPaidRequests
)

$ErrorActionPreference = 'Stop'
$repository = [IO.Path]::GetFullPath($RepositoryRoot)
if ($repository -ne 'D:\codex') {
    throw 'knowledge.p5_live_repository_invalid'
}

$runtimeRoot = Join-Path $repository 'agent-runtime'
$manifestPath = Join-Path $runtimeRoot 'tests\evaluation\knowledge\live\evidence\knowledge-p5-live-v1-20260813-candidate-04.manifest.json'
$manifest = Get-Content -LiteralPath $manifestPath -Raw -Encoding UTF8 | ConvertFrom-Json
$actualManifestSha256 = (Get-FileHash -LiteralPath $manifestPath -Algorithm SHA256).Hash.ToLowerInvariant()
if (
    [int]$manifest.schemaVersion -ne 2 -or
    $null -eq $manifest.retrievalBinding -or
    [string]$manifest.datasetPath -ne 'agent-runtime/tests/evaluation/knowledge/representative_questions.v2.jsonl' -or
    $AuthorizedRunId -ne [string]$manifest.runId -or
    $AuthorizationReference -ne [string]$manifest.authorizationReference -or
    $MaximumPaidRequests -ne [int]$manifest.paidRequestBudget.maximumPaidRequests -or
    $AuthorizedManifestSha256 -notmatch '^[0-9a-f]{64}$' -or
    $actualManifestSha256 -ne $AuthorizedManifestSha256
) {
    throw 'knowledge.p5_live_authorization_binding_invalid'
}

$datasetPath = Join-Path $runtimeRoot 'tests\evaluation\knowledge\representative_questions.v2.jsonl'
$outputRoot = Join-Path $runtimeRoot "tests\evaluation\knowledge\results\$AuthorizedRunId"
if (Test-Path -LiteralPath $outputRoot) {
    throw 'knowledge.p5_live_authorization_consumed'
}
if ((git -C $repository status --porcelain --untracked-files=all)) {
    throw 'knowledge.p5_live_worktree_dirty'
}

$ownedPorts = 18090, 19201
$dependencyPorts = 9200, 8908, 8909
if (Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue | Where-Object { $ownedPorts -contains $_.LocalPort }) {
    throw 'knowledge.p5_live_owned_port_occupied'
}
foreach ($port in $dependencyPorts) {
    if (-not (Get-NetTCPConnection -State Listen -LocalPort $port -ErrorAction SilentlyContinue)) {
        throw "knowledge.p5_live_dependency_unavailable:$port"
    }
}

Push-Location $runtimeRoot
try {
    $previousPythonPath = [Environment]::GetEnvironmentVariable('PYTHONPATH', 'Process')
    $env:PYTHONPATH = 'src'
    python -m pytest `
        tests/evaluation/knowledge/test_live_p5_candidate_04_preparation.py `
        tests/evaluation/knowledge/test_live_p5_candidate_03_preparation.py `
        tests/evaluation/knowledge/test_live_p5_diagnostics.py `
        tests/evaluation/knowledge/test_live_p5_candidate_01_history.py `
        tests/evaluation/knowledge/test_live_p5_candidate_02_history.py `
        tests/evaluation/knowledge/test_live_p5_preparation.py `
        tests/evaluation/knowledge/test_dataset_and_metrics.py `
        tests/evaluation/knowledge/test_reproducible_run.py `
        -q --tb=short
    if ($LASTEXITCODE -ne 0) {
        throw 'knowledge.p5_live_preflight_failed'
    }
} finally {
    Pop-Location
    [Environment]::SetEnvironmentVariable('PYTHONPATH', $previousPythonPath, 'Process')
}

$apiKey = [Environment]::GetEnvironmentVariable('LLM_API_KEY', 'Process')
if ([string]::IsNullOrWhiteSpace($apiKey)) {
    throw 'knowledge.p5_live_api_key_missing'
}

$environmentNames = @(
    'COMMON_SECURITY_JWT_HMAC_KEY_ACTIVE',
    'P5_KNOWLEDGE_MODE',
    'P5_KNOWLEDGE_LIVE_OPT_IN',
    'P5_KNOWLEDGE_USER_JWT',
    'P5_KNOWLEDGE_AUTH_EVIDENCE_REF',
    'P5_KNOWLEDGE_CANDIDATE',
    'AGENT_KNOWLEDGE_ES_BASE_URL',
    'AGENT_KNOWLEDGE_EMBEDDING_BASE_URL',
    'AGENT_KNOWLEDGE_RERANK_BASE_URL',
    'AGENT_KNOWLEDGE_READ_ALIAS',
    'AGENT_KNOWLEDGE_EXPECTED_INDEX_NAME',
    'AGENT_KNOWLEDGE_EXPECTED_INDEX_UUID',
    'AGENT_KNOWLEDGE_MAPPING_VERSION',
    'AGENT_KNOWLEDGE_POLICY_SNAPSHOT_ID',
    'AGENT_KNOWLEDGE_LAW_SNAPSHOT_ID',
    'AGENT_MODEL_PROVIDER',
    'AGENT_MODEL_MAX_CONCURRENCY',
    'PYTHONPATH'
)
$environmentSnapshot = @{}
foreach ($name in $environmentNames) {
    $environmentSnapshot[$name] = [Environment]::GetEnvironmentVariable($name, 'Process')
}

$tempBase = [IO.Path]::GetFullPath([IO.Path]::GetTempPath())
$runRoot = Join-Path $tempBase "codex-p5-live-$([Guid]::NewGuid().ToString('N'))"
New-Item -ItemType Directory -Path $runRoot | Out-Null
$reviewRoot = Join-Path $repository ".tmp\p5-live\$AuthorizedRunId"
$authOut = Join-Path $runRoot 'auth.out.log'
$authErr = Join-Path $runRoot 'auth.err.log'
$esOut = Join-Path $runRoot 'es.out.log'
$esErr = Join-Path $runRoot 'es.err.log'

$keyBytes = [Security.Cryptography.RandomNumberGenerator]::GetBytes(48)
$secret = [Convert]::ToBase64String($keyBytes)
$env:COMMON_SECURITY_JWT_HMAC_KEY_ACTIVE = $secret
$env:AGENT_KNOWLEDGE_READ_ALIAS = [string]$manifest.retrievalBinding.readAlias
$env:AGENT_KNOWLEDGE_EXPECTED_INDEX_NAME = [string]$manifest.retrievalBinding.expectedIndexName
$env:AGENT_KNOWLEDGE_EXPECTED_INDEX_UUID = [string]$manifest.retrievalBinding.expectedIndexUuid
$env:AGENT_KNOWLEDGE_MAPPING_VERSION = [string]$manifest.retrievalBinding.mappingVersion
$env:AGENT_KNOWLEDGE_POLICY_SNAPSHOT_ID = [string]$manifest.retrievalBinding.policySnapshotId
$env:AGENT_KNOWLEDGE_LAW_SNAPSHOT_ID = [string]$manifest.retrievalBinding.lawSnapshotId
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
$logLeakDetected = $false
$pythonExitCode = $null

function Wait-Ready([string]$Uri, [Diagnostics.Process]$Process) {
    for ($attempt = 0; $attempt -lt 120; $attempt++) {
        if ($Process.HasExited) {
            throw 'knowledge.p5_live_process_exited'
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
    throw 'knowledge.p5_live_readiness_timeout'
}

function Get-LocalPassword([string]$User) {
    $path = Join-Path $repository 'auth-service\src\main\resources\auth-users.yml'
    $text = Get-Content -LiteralPath $path -Raw -Encoding UTF8
    $match = [regex]::Match($text, "(?ms)^\s{4}${User}:\s*\r?\n\s+password:\s*([^\r\n]+)")
    if (-not $match.Success) {
        throw 'knowledge.p5_live_auth_fixture_missing'
    }
    $stored = $match.Groups[1].Value.Trim().Trim('"').Trim("'")
    if (-not $stored.StartsWith('{noop}')) {
        throw 'knowledge.p5_live_auth_fixture_not_local'
    }
    return $stored.Substring(6)
}

function Get-LoginToken([string]$User) {
    $session = [Microsoft.PowerShell.Commands.WebRequestSession]::new()
    $body = @{ userId = $User; password = (Get-LocalPassword $User) } | ConvertTo-Json -Compress
    $response = Invoke-WebRequest -Uri 'http://127.0.0.1:18090/login' -Method Post `
        -ContentType 'application/json' -Body $body -WebSession $session -TimeoutSec 5 -SkipHttpErrorCheck
    if ($response.StatusCode -ne 200) {
        throw 'knowledge.p5_live_login_failed'
    }
    $cookie = $session.Cookies.GetCookies('http://127.0.0.1:18090')['AUTH_TOKEN']
    if ($null -eq $cookie -or [string]::IsNullOrWhiteSpace($cookie.Value)) {
        throw 'knowledge.p5_live_token_missing'
    }
    return $cookie.Value
}

function Test-SensitiveLogValue {
    $logs = (Get-Content -LiteralPath $authOut, $authErr, $esOut, $esErr -Raw -ErrorAction SilentlyContinue) -join "`n"
    foreach ($sensitive in @($secret, $apiKey, $adminToken)) {
        if ($sensitive -and $logs.Contains([string]$sensitive)) {
            return $true
        }
    }
    foreach ($line in Get-Content -LiteralPath $datasetPath -Encoding UTF8) {
        if (-not [string]::IsNullOrWhiteSpace($line)) {
            $question = ($line | ConvertFrom-Json).question
            if ($question -and $logs.Contains([string]$question)) {
                return $true
            }
        }
    }
    return $false
}

try {
    $authJar = Join-Path $repository 'auth-service\target\auth-service-0.0.1-SNAPSHOT.jar'
    $authArgs = @('-jar', $authJar, '--server.port=18090') + $commonArgs
    $authProcess = Start-Process -FilePath 'java' -ArgumentList $authArgs `
        -WorkingDirectory (Join-Path $repository 'auth-service') -WindowStyle Hidden -PassThru `
        -RedirectStandardOutput $authOut -RedirectStandardError $authErr

    $esJar = Join-Path $repository 'es-query-service\target\es-query-service-0.0.1-SNAPSHOT.jar'
    $esArgs = @(
        '-jar', $esJar,
        '--server.port=19201',
        '--spring.profiles.active=datasource,es,knowledge-live',
        '--spring.elasticsearch.uris=http://127.0.0.1:9200',
        '--es.query.total-hits-threshold=10000',
        '--es.query.rebuild-source-allowed-hosts[0]=localhost',
        '--es.query.rebuild-max-batch-size=500'
    ) + $commonArgs
    $esProcess = Start-Process -FilePath 'java' -ArgumentList $esArgs `
        -WorkingDirectory (Join-Path $repository 'es-query-service') -WindowStyle Hidden -PassThru `
        -RedirectStandardOutput $esOut -RedirectStandardError $esErr

    Wait-Ready 'http://127.0.0.1:18090/public/test' $authProcess
    Wait-Ready 'http://127.0.0.1:19201/actuator/health' $esProcess
    $adminToken = Get-LoginToken 'admin'

    $embeddingWarmup = Invoke-RestMethod -Uri 'http://127.0.0.1:8908/embed' -Method Post `
        -ContentType 'application/json' -Body '{"texts":["税务政策公开信息"]}' -TimeoutSec 30
    if ($embeddingWarmup.dim -ne 1024 -or $embeddingWarmup.vectors.Count -ne 1) {
        throw 'knowledge.p5_live_embedding_warmup_failed'
    }
    $rerankWarmup = Invoke-RestMethod -Uri 'http://127.0.0.1:8909/rerank' -Method Post `
        -ContentType 'application/json' `
        -Body '{"query":"税务政策","documents":["税务政策公开信息"],"top_n":1,"normalize":true}' `
        -TimeoutSec 30
    if ($rerankWarmup.model -ne 'BAAI/bge-reranker-v2-m3' -or $rerankWarmup.results.Count -ne 1) {
        throw 'knowledge.p5_live_rerank_warmup_failed'
    }

    $env:P5_KNOWLEDGE_MODE = 'live'
    $env:P5_KNOWLEDGE_LIVE_OPT_IN = 'I_UNDERSTAND_LIVE_EXTERNAL_CALLS'
    $env:P5_KNOWLEDGE_USER_JWT = $adminToken
    $env:P5_KNOWLEDGE_AUTH_EVIDENCE_REF = 'WP-KRET-REAL-01:authorizationMatrix.admin'
    $env:P5_KNOWLEDGE_CANDIDATE = 'candidate-04'
    $env:AGENT_KNOWLEDGE_ES_BASE_URL = 'http://127.0.0.1:19201'
    $env:AGENT_KNOWLEDGE_EMBEDDING_BASE_URL = 'http://127.0.0.1:8908'
    $env:AGENT_KNOWLEDGE_RERANK_BASE_URL = 'http://127.0.0.1:8909'
    $env:AGENT_MODEL_PROVIDER = 'deepseek'
    $env:AGENT_MODEL_MAX_CONCURRENCY = '1'
    $env:PYTHONPATH = 'src'

    Push-Location $runtimeRoot
    try {
        python -m tests.evaluation.knowledge.live_runner --dataset $datasetPath --output $outputRoot
        $pythonExitCode = $LASTEXITCODE
    } finally {
        Pop-Location
    }

    $logLeakDetected = Test-SensitiveLogValue
    if ($logLeakDetected) {
        throw 'knowledge.p5_live_log_leak'
    }
    if ($pythonExitCode -ne 0) {
        throw 'knowledge.p5_live_execution_failed'
    }
    $resultPath = Join-Path $outputRoot 'result.json'
    $evidencePath = Join-Path $outputRoot 'evidence.json'
    if (-not (Test-Path -LiteralPath $resultPath) -or -not (Test-Path -LiteralPath $evidencePath)) {
        throw 'knowledge.p5_live_result_missing'
    }
    $launcherEvidence = [ordered]@{
        schemaVersion = 1
        status = 'passed'
        workPackageId = 'WP-KP5-LIVE-01'
        runId = $AuthorizedRunId
        manifestSha256 = $AuthorizedManifestSha256
        authorizationReference = $AuthorizationReference
        maximumPaidRequests = $MaximumPaidRequests
        authService = 'isolated-local'
        knowledgeProvider = 'isolated-local'
        embedding = 'BGE-M3'
        rerank = 'BAAI/bge-reranker-v2-m3'
        logLeakCount = 0
        rawLogsRetained = $false
        resultSha256 = (Get-FileHash -LiteralPath $resultPath -Algorithm SHA256).Hash.ToLowerInvariant()
        evidenceSha256 = (Get-FileHash -LiteralPath $evidencePath -Algorithm SHA256).Hash.ToLowerInvariant()
    }
    $launcherPath = Join-Path $outputRoot 'launcher-evidence.json'
    $json = $launcherEvidence | ConvertTo-Json -Depth 4 -Compress
    $bytes = [Text.UTF8Encoding]::new($false).GetBytes("$json`n")
    $stream = [IO.File]::Open($launcherPath, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write, [IO.FileShare]::None)
    try {
        $stream.Write($bytes, 0, $bytes.Length)
        $stream.Flush($true)
    } finally {
        $stream.Dispose()
    }
    [pscustomobject]@{
        status = 'passed'
        runId = $AuthorizedRunId
        result = $resultPath
        evidence = $evidencePath
        launcherEvidence = $launcherPath
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
    $apiKey = $null
    foreach ($name in $environmentNames) {
        [Environment]::SetEnvironmentVariable($name, $environmentSnapshot[$name], 'Process')
    }
    $resolvedReviewRoot = [IO.Path]::GetFullPath($reviewRoot)
    $allowedReviewRoot = [IO.Path]::GetFullPath((Join-Path $repository '.tmp\p5-live'))
    if (
        $resolvedReviewRoot.StartsWith($allowedReviewRoot + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase) -and
        (Test-Path -LiteralPath $resolvedReviewRoot)
    ) {
        Remove-Item -LiteralPath $resolvedReviewRoot -Recurse -Force
    }
    $resolvedRunRoot = [IO.Path]::GetFullPath($runRoot)
    if ($resolvedRunRoot.StartsWith($tempBase, [StringComparison]::OrdinalIgnoreCase) -and (Test-Path -LiteralPath $resolvedRunRoot)) {
        Remove-Item -LiteralPath $resolvedRunRoot -Recurse -Force
    }
    if ($logLeakDetected) {
        throw 'knowledge.p5_live_log_leak'
    }
}
