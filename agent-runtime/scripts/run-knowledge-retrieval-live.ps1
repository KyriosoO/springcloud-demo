[CmdletBinding()]
param(
    [string]$RepositoryRoot = (Split-Path -Parent $PSScriptRoot),
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
    throw 'knowledge.live_repository_invalid'
}

$requiredPorts = 8090, 9201
$occupied = Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue |
    Where-Object { $requiredPorts -contains $_.LocalPort }
if ($occupied) {
    throw 'knowledge.live_port_occupied'
}

$environmentNames = @(
    'COMMON_SECURITY_JWT_HMAC_KEY_ACTIVE',
    'AGENT_KNOWLEDGE_READ_ALIAS',
    'AGENT_KNOWLEDGE_EXPECTED_INDEX_NAME',
    'AGENT_KNOWLEDGE_EXPECTED_INDEX_UUID',
    'AGENT_KNOWLEDGE_MAPPING_VERSION',
    'AGENT_KNOWLEDGE_POLICY_SNAPSHOT_ID',
    'AGENT_KNOWLEDGE_LAW_SNAPSHOT_ID',
    'RUN_KNOWLEDGE_RETRIEVAL_LIVE',
    'AGENT_KNOWLEDGE_ES_BASE_URL',
    'AGENT_KNOWLEDGE_ES_STATS_BASE_URL',
    'AGENT_KNOWLEDGE_EMBEDDING_BASE_URL',
    'AGENT_KNOWLEDGE_RERANK_BASE_URL',
    'AGENT_KNOWLEDGE_ADMIN_JWT',
    'AGENT_KNOWLEDGE_VIEWER_JWT',
    'AGENT_KNOWLEDGE_UNKNOWN_ROLE_JWT',
    'AGENT_KNOWLEDGE_SERVICE_JWT',
    'PYTHONPATH'
)
$environmentSnapshot = @{}
foreach ($name in $environmentNames) {
    $environmentSnapshot[$name] = [Environment]::GetEnvironmentVariable($name, 'Process')
}

$runRoot = Join-Path $repository ".tmp\kret-real\$([DateTime]::UtcNow.ToString('yyyyMMddTHHmmssZ'))"
New-Item -ItemType Directory -Path $runRoot -Force | Out-Null
$authOut = Join-Path $runRoot 'auth.out.log'
$authErr = Join-Path $runRoot 'auth.err.log'
$esOut = Join-Path $runRoot 'es.out.log'
$esErr = Join-Path $runRoot 'es.err.log'

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
$syntheticQuestion = '增值税相关税收法规政策'
$adminToken = $null
$viewerToken = $null
$unknownToken = $null
$serviceToken = $null

function Wait-Ready([string]$Uri, [Diagnostics.Process]$Process) {
    for ($attempt = 0; $attempt -lt 90; $attempt++) {
        if ($Process.HasExited) {
            throw 'knowledge.live_process_exited'
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
    throw 'knowledge.live_readiness_timeout'
}

function Get-LocalPassword([string]$User) {
    $path = Join-Path $repository 'auth-service\src\main\resources\auth-users.yml'
    $text = Get-Content -LiteralPath $path -Raw -Encoding UTF8
    $match = [regex]::Match($text, "(?ms)^\s{4}${User}:\s*\r?\n\s+password:\s*([^\r\n]+)")
    if (-not $match.Success) {
        throw 'knowledge.live_auth_fixture_missing'
    }
    $stored = $match.Groups[1].Value.Trim().Trim('"').Trim("'")
    if (-not $stored.StartsWith('{noop}')) {
        throw 'knowledge.live_auth_fixture_not_local'
    }
    return $stored.Substring(6)
}

function Get-LoginToken([string]$User) {
    $session = [Microsoft.PowerShell.Commands.WebRequestSession]::new()
    $body = @{ userId = $User; password = (Get-LocalPassword $User) } | ConvertTo-Json -Compress
    $response = Invoke-WebRequest -Uri 'http://127.0.0.1:8090/login' -Method Post `
        -ContentType 'application/json' -Body $body -WebSession $session -TimeoutSec 5 -SkipHttpErrorCheck
    if ($response.StatusCode -ne 200) {
        throw 'knowledge.live_login_failed'
    }
    $cookie = $session.Cookies.GetCookies('http://127.0.0.1:8090')['AUTH_TOKEN']
    if ($null -eq $cookie -or [string]::IsNullOrWhiteSpace($cookie.Value)) {
        throw 'knowledge.live_token_missing'
    }
    return $cookie.Value
}

function ConvertTo-Base64Url([byte[]]$Bytes) {
    return [Convert]::ToBase64String($Bytes).TrimEnd('=').Replace('+', '-').Replace('/', '_')
}

function New-TestJwt([string]$Subject, [string]$TokenType, [string[]]$Roles) {
    $now = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds()
    $header = [ordered]@{ alg = 'HS256'; kid = 'ACTIVE' } | ConvertTo-Json -Compress
    $claims = [ordered]@{
        sub = $Subject
        iat = $now
        exp = $now + 3600
        token_type = $TokenType
        role = $Roles
    } | ConvertTo-Json -Compress
    $unsigned = "$(ConvertTo-Base64Url ([Text.Encoding]::UTF8.GetBytes($header))).$(ConvertTo-Base64Url ([Text.Encoding]::UTF8.GetBytes($claims)))"
    $hmac = [Security.Cryptography.HMACSHA256]::new($keyBytes)
    try {
        $signature = ConvertTo-Base64Url ($hmac.ComputeHash([Text.Encoding]::ASCII.GetBytes($unsigned)))
    } finally {
        $hmac.Dispose()
    }
    return "$unsigned.$signature"
}

function Test-SensitiveLogValue {
    $logs = (Get-Content -LiteralPath $authOut, $authErr, $esOut, $esErr -Raw -ErrorAction SilentlyContinue) -join "`n"
    foreach ($sensitive in @($secret, $adminToken, $viewerToken, $unknownToken, $serviceToken, $syntheticQuestion)) {
        if ($sensitive -and $logs.Contains([string]$sensitive)) {
            return $true
        }
    }
    return $false
}

try {
    $authJar = Join-Path $repository 'auth-service\target\auth-service-0.0.1-SNAPSHOT.jar'
    $authArgs = @('-jar', $authJar) + $commonArgs
    $authProcess = Start-Process -FilePath 'java' -ArgumentList $authArgs `
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
    $viewerToken = Get-LoginToken 'viewer_t'
    $unknownToken = New-TestJwt 'unknown-live-user' 'user' @('UNKNOWN')
    $serviceToken = New-TestJwt 'knowledge-live-service' 'service' @('ADMIN')

    $env:RUN_KNOWLEDGE_RETRIEVAL_LIVE = '1'
    $env:AGENT_KNOWLEDGE_ES_BASE_URL = 'http://127.0.0.1:9201'
    $env:AGENT_KNOWLEDGE_ES_STATS_BASE_URL = 'http://127.0.0.1:9200'
    $env:AGENT_KNOWLEDGE_EMBEDDING_BASE_URL = 'http://127.0.0.1:8908'
    $env:AGENT_KNOWLEDGE_RERANK_BASE_URL = 'http://127.0.0.1:8909'
    $env:AGENT_KNOWLEDGE_ADMIN_JWT = $adminToken
    $env:AGENT_KNOWLEDGE_VIEWER_JWT = $viewerToken
    $env:AGENT_KNOWLEDGE_UNKNOWN_ROLE_JWT = $unknownToken
    $env:AGENT_KNOWLEDGE_SERVICE_JWT = $serviceToken

    Push-Location (Join-Path $repository 'agent-runtime')
    try {
        $env:PYTHONPATH = 'src'
        python -m pytest tests/integration/knowledge/test_real_retrieval_live.py -vv --tb=long
        $pytestExitCode = $LASTEXITCODE
    } finally {
        Pop-Location
    }

    if (Test-SensitiveLogValue) {
        throw 'knowledge.live_log_leak'
    }
    if ($pytestExitCode -ne 0) {
        throw 'knowledge.live_pytest_failed'
    }

    [pscustomobject]@{
        authReady = $true
        providerReady = $true
        liveTests = 'passed'
        logLeakCount = 0
        runDirectory = $runRoot
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
    $logLeakDetected = Test-SensitiveLogValue
    [Array]::Clear($keyBytes, 0, $keyBytes.Length)
    $secret = $null
    $adminToken = $null
    $viewerToken = $null
    $unknownToken = $null
    $serviceToken = $null
    foreach ($name in $environmentNames) {
        [Environment]::SetEnvironmentVariable($name, $environmentSnapshot[$name], 'Process')
    }
    if ($logLeakDetected) {
        throw 'knowledge.live_log_leak'
    }
}
