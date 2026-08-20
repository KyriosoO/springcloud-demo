[CmdletBinding()]
param(
    [string]$RepositoryRoot = (Split-Path -Parent (Split-Path -Parent $PSScriptRoot)),
    [string]$EvidencePath = (Join-Path $PSScriptRoot '..\tests\system_e2e\evidence\system-e2e-v1.result.json')
)

$ErrorActionPreference = 'Stop'
$repository = [IO.Path]::GetFullPath($RepositoryRoot)
if ($repository -ne 'D:\codex') {
    throw 'system_e2e.repository_invalid'
}
$evidence = [IO.Path]::GetFullPath($EvidencePath)
$evidenceRoot = [IO.Path]::GetFullPath((Join-Path $repository 'agent-runtime\tests\system_e2e\evidence'))
if (-not $evidence.StartsWith($evidenceRoot + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase) -or
        [IO.Path]::GetExtension($evidence) -ne '.json') {
    throw 'system_e2e.evidence_path_invalid'
}
$employeeIdentifier = [Environment]::GetEnvironmentVariable('SYSTEM_E2E_EMPLOYEE_IDENTIFIER', 'Process')
if ([string]::IsNullOrWhiteSpace($employeeIdentifier)) {
    throw 'system_e2e.employee_identifier_missing'
}

$ownedPorts = 8090, 9201, 9210, 8182
$occupied = Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue |
    Where-Object { $ownedPorts -contains $_.LocalPort }
if ($occupied) {
    throw 'system_e2e.owned_port_occupied'
}

function Test-TcpReady([int]$Port) {
    $client = [Net.Sockets.TcpClient]::new()
    try {
        $connect = $client.ConnectAsync('127.0.0.1', $Port)
        return $connect.Wait(2000) -and $client.Connected
    } catch {
        return $false
    } finally {
        $client.Dispose()
    }
}

foreach ($port in 9200, 8908, 8909) {
    if (-not (Test-TcpReady $port)) {
        throw 'system_e2e.infrastructure_unavailable'
    }
}

$runRoot = Join-Path $repository ".tmp\system-e2e\$([DateTime]::UtcNow.ToString('yyyyMMddTHHmmssfffZ'))"
New-Item -ItemType Directory -Path $runRoot -Force | Out-Null
$runtimeLog = Join-Path $runRoot 'runtime.log'
$runtimeStop = Join-Path $runRoot 'runtime.stop'
$buildOut = Join-Path $runRoot 'build.out.log'
$buildErr = Join-Path $runRoot 'build.err.log'
$mavenOut = Join-Path $runRoot 'maven.out.log'
$mavenErr = Join-Path $runRoot 'maven.err.log'
$authOut = Join-Path $runRoot 'auth.out.log'
$authErr = Join-Path $runRoot 'auth.err.log'
$esOut = Join-Path $runRoot 'es.out.log'
$esErr = Join-Path $runRoot 'es.err.log'
$employeeOut = Join-Path $runRoot 'employee.out.log'
$employeeErr = Join-Path $runRoot 'employee.err.log'
$transactionOut = Join-Path $runRoot 'transaction.out.log'
$transactionErr = Join-Path $runRoot 'transaction.err.log'
$surefireReports = [IO.Path]::GetFullPath((Join-Path $runRoot 'surefire-reports'))
if (-not $surefireReports.StartsWith($runRoot + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) {
    throw 'system_e2e.report_path_invalid'
}
$rawLogs = @(
    $runtimeLog, $buildOut, $buildErr, $mavenOut, $mavenErr,
    $authOut, $authErr, $esOut, $esErr, $employeeOut, $employeeErr,
    $transactionOut, $transactionErr
)
if (Test-Path -LiteralPath $evidence) {
    Remove-Item -LiteralPath $evidence -Force
}

function Invoke-CapturedProcess(
    [string]$FilePath,
    [string[]]$ArgumentList,
    [string]$WorkingDirectory,
    [string]$StandardOutput,
    [string]$StandardError
) {
    $process = Start-Process -FilePath $FilePath -ArgumentList $ArgumentList `
        -WorkingDirectory $WorkingDirectory -WindowStyle Hidden -PassThru -Wait `
        -RedirectStandardOutput $StandardOutput -RedirectStandardError $StandardError
    return $process.ExitCode
}

function Start-OwnedProcess(
    [string]$FilePath,
    [string[]]$ArgumentList,
    [string]$WorkingDirectory,
    [string]$StandardOutput,
    [string]$StandardError
) {
    return Start-Process -FilePath $FilePath -ArgumentList $ArgumentList `
        -WorkingDirectory $WorkingDirectory -WindowStyle Hidden -PassThru `
        -RedirectStandardOutput $StandardOutput -RedirectStandardError $StandardError
}

function Wait-OwnedReady(
    [string]$Uri,
    [int]$Port,
    [Diagnostics.Process]$Process,
    [int[]]$AllowedStatus
) {
    for ($attempt = 0; $attempt -lt 120; $attempt++) {
        if ($Process.HasExited) {
            throw 'system_e2e.service_process_exited'
        }
        $listener = Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue |
            Where-Object { $_.OwningProcess -eq $Process.Id }
        if ($listener) {
            try {
                $response = Invoke-WebRequest -Uri $Uri -Method Get -TimeoutSec 2 -SkipHttpErrorCheck
                if ($AllowedStatus -contains [int]$response.StatusCode) {
                    return
                }
            } catch {
            }
        }
        Start-Sleep -Milliseconds 500
    }
    throw 'system_e2e.service_readiness_timeout'
}

function Stop-Owned([Diagnostics.Process]$Process) {
    if ($null -eq $Process) {
        return
    }
    try {
        $Process.Refresh()
        if (-not $Process.HasExited) {
            Stop-Process -Id $Process.Id -ErrorAction SilentlyContinue
            if (-not $Process.WaitForExit(5000)) {
                Stop-Process -Id $Process.Id -Force -ErrorAction SilentlyContinue
                [void]$Process.WaitForExit(3000)
            }
        }
    } catch {
    }
}

function Get-LocalPassword([string]$User) {
    $path = Join-Path $repository 'auth-service\src\main\resources\auth-users.yml'
    $text = Get-Content -LiteralPath $path -Raw -Encoding UTF8
    $match = [regex]::Match($text, "(?ms)^\s{4}${User}:\s*\r?\n\s+password:\s*([^\r\n]+)")
    if (-not $match.Success) {
        throw 'system_e2e.auth_fixture_missing'
    }
    $stored = $match.Groups[1].Value.Trim().Trim('"').Trim("'")
    if (-not $stored.StartsWith('{noop}')) {
        throw 'system_e2e.auth_fixture_invalid'
    }
    return $stored.Substring(6)
}

function Get-LoginToken([string]$User) {
    $session = [Microsoft.PowerShell.Commands.WebRequestSession]::new()
    $body = @{ userId = $User; password = (Get-LocalPassword $User) } | ConvertTo-Json -Compress
    $response = Invoke-WebRequest -Uri 'http://127.0.0.1:8090/login' -Method Post `
        -ContentType 'application/json' -Body $body -WebSession $session -TimeoutSec 5 -SkipHttpErrorCheck
    if ($response.StatusCode -ne 200) {
        throw 'system_e2e.auth_login_failed'
    }
    $cookie = $session.Cookies.GetCookies('http://127.0.0.1:8090')['AUTH_TOKEN']
    if ($null -eq $cookie -or [string]::IsNullOrWhiteSpace($cookie.Value)) {
        throw 'system_e2e.auth_token_missing'
    }
    return $cookie.Value
}

function ConvertTo-Base64Url([byte[]]$Bytes) {
    return [Convert]::ToBase64String($Bytes).TrimEnd('=').Replace('+', '-').Replace('/', '_')
}

function New-UnknownRoleJwt([byte[]]$KeyBytes) {
    $now = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds()
    $header = [ordered]@{ alg = 'HS256'; kid = 'ACTIVE' } | ConvertTo-Json -Compress
    $claims = [ordered]@{
        sub = 'system-e2e-unknown'
        iat = $now
        exp = $now + 3600
        token_type = 'user'
        role = @('UNKNOWN')
    } | ConvertTo-Json -Compress
    $unsigned = "$(ConvertTo-Base64Url ([Text.Encoding]::UTF8.GetBytes($header))).$(ConvertTo-Base64Url ([Text.Encoding]::UTF8.GetBytes($claims)))"
    $hmac = [Security.Cryptography.HMACSHA256]::new($KeyBytes)
    try {
        $signature = ConvertTo-Base64Url ($hmac.ComputeHash([Text.Encoding]::ASCII.GetBytes($unsigned)))
    } finally {
        $hmac.Dispose()
    }
    return "$unsigned.$signature"
}

function Get-SafeFailureCode([string]$Message) {
    if ($Message -match '^system_e2e\.[a-z0-9_]+$') {
        return $Message
    }
    return 'system_e2e.unexpected_failure'
}

$keyBytes = [Security.Cryptography.RandomNumberGenerator]::GetBytes(48)
$secret = [Convert]::ToBase64String($keyBytes)
$adminToken = $null
$unknownToken = $null
$authProcess = $null
$esProcess = $null
$employeeProcess = $null
$transactionProcess = $null
$failureCode = $null
$logLeakCount = 0
$rawLogsDeleted = $false
$ownedProcessesStopped = $false
$knowledgeQuestion = '增值税相关税收法规政策'
$transactionQuestion = '查询交易 金额=0.01'

try {
    $maven = (Get-Command mvn.cmd -ErrorAction Stop).Source
    $python = Join-Path $repository '.tmp\agent-runtime-venv\Scripts\python.exe'
    if (-not (Test-Path -LiteralPath $python)) {
        throw 'system_e2e.python_missing'
    }
    $buildExit = Invoke-CapturedProcess $maven @(
        '-f', 'serviceCenter/pom.xml',
        '-pl', ':auth-service,:es-query-service,:employee-service,:mq-procedure-service',
        '-am', '-DskipTests', 'package'
    ) $repository $buildOut $buildErr
    if ($buildExit -ne 0) {
        throw 'system_e2e.service_build_failed'
    }

    $authJar = Join-Path $repository 'auth-service\target\auth-service-0.0.1-SNAPSHOT.jar'
    $esJar = Join-Path $repository 'es-query-service\target\es-query-service-0.0.1-SNAPSHOT.jar'
    $employeeJar = Join-Path $repository 'employee-service\target\employee-service-0.0.1-SNAPSHOT.jar'
    $transactionJar = Join-Path $repository 'mq-procedure-service\target\mq-procedure-service-0.0.1-SNAPSHOT.jar'
    if (@($authJar, $esJar, $employeeJar, $transactionJar) | Where-Object { -not (Test-Path -LiteralPath $_) }) {
        throw 'system_e2e.service_jar_missing'
    }

    $env:LLM_API_KEY = $null
    $env:COMMON_SECURITY_JWT_HMAC_KEY_ACTIVE = $secret
    $env:AGENT_KNOWLEDGE_READ_ALIAS = 'agent-doc-tax-policy-v2-read'
    $env:AGENT_KNOWLEDGE_EXPECTED_INDEX_NAME = 'agent-doc-tax-policy-v3-20260803-agent-read-v1'
    $env:AGENT_KNOWLEDGE_EXPECTED_INDEX_UUID = 'k97bn1gxROSfVm7zGfzbOg'
    $env:AGENT_KNOWLEDGE_MAPPING_VERSION = 'agent-knowledge-tax-v1'
    $env:AGENT_KNOWLEDGE_POLICY_SNAPSHOT_ID = '7c71202794927a9497fed9df7cc0db5a052a53f0f6c2afdb6c0a16089f1c96ed'
    $env:AGENT_KNOWLEDGE_LAW_SNAPSHOT_ID = '99ae962ae1c8e5026187c864eada38b3c3b82d6b017e6e8f076f116aba53fce2'
    $commonArgs = @(
        '--spring.main.banner-mode=off',
        '--spring.cloud.config.enabled=false',
        '--spring.config.import=',
        '--spring.config.additional-location=optional:file:D:/codex/config-service/src/main/resources/config/',
        '--eureka.client.enabled=false',
        '--common.security.secrets.source-order[0]=environment',
        '--common.security.secrets.allow-config-values=false',
        '--common.security.secrets.fail-fast=true',
        '--common.security.secrets.jwt.active-key-id=ACTIVE',
        '--common.security.secrets.jwt.keys.ACTIVE.env=COMMON_SECURITY_JWT_HMAC_KEY_ACTIVE',
        '--common.security.secrets.jwt.keys.ACTIVE.value='
    )
    $authProcess = Start-OwnedProcess 'java' (@('-jar', $authJar, '--server.port=8090') + $commonArgs) `
        (Join-Path $repository 'auth-service') $authOut $authErr
    $esProcess = Start-OwnedProcess 'java' (@(
        '-jar', $esJar, '--server.port=9201',
        '--spring.profiles.active=datasource,es,knowledge-live',
        '--spring.elasticsearch.uris=http://127.0.0.1:9200',
        '--es.query.total-hits-threshold=10000',
        '--es.query.rebuild-source-allowed-hosts[0]=localhost',
        '--es.query.rebuild-max-batch-size=500'
    ) + $commonArgs) (Join-Path $repository 'es-query-service') $esOut $esErr
    $employeeProcess = Start-OwnedProcess 'java' (@('-jar', $employeeJar, '--server.port=9210') + $commonArgs) `
        (Join-Path $repository 'employee-service') $employeeOut $employeeErr
    $transactionProcess = Start-OwnedProcess 'java' (@('-jar', $transactionJar, '--server.port=8182') + $commonArgs) `
        (Join-Path $repository 'mq-procedure-service') $transactionOut $transactionErr

    Wait-OwnedReady 'http://127.0.0.1:8090/public/test' 8090 $authProcess @(200)
    Wait-OwnedReady 'http://127.0.0.1:9201/actuator/health' 9201 $esProcess @(200)
    Wait-OwnedReady 'http://127.0.0.1:9210/actuator/health' 9210 $employeeProcess @(200, 401, 403)
    Wait-OwnedReady 'http://127.0.0.1:8182/actuator/health' 8182 $transactionProcess @(200, 401, 403)

    $adminToken = Get-LoginToken 'admin'
    $unknownToken = New-UnknownRoleJwt $keyBytes
    $env:RUN_SYSTEM_E2E = '1'
    $env:SYSTEM_E2E_ADMIN_JWT = $adminToken
    $env:SYSTEM_E2E_UNKNOWN_ROLE_JWT = $unknownToken
    $env:SYSTEM_E2E_EMPLOYEE_BASE_URL = 'http://127.0.0.1:9210'
    $env:SYSTEM_E2E_TRANSACTION_BASE_URL = 'http://127.0.0.1:8182'
    $env:SYSTEM_E2E_KNOWLEDGE_BASE_URL = 'http://127.0.0.1:9201'
    $env:SYSTEM_E2E_EMBEDDING_BASE_URL = 'http://127.0.0.1:8908'
    $env:SYSTEM_E2E_RERANK_BASE_URL = 'http://127.0.0.1:8909'
    $env:SYSTEM_E2E_EVIDENCE_PATH = $evidence
    $env:SYSTEM_E2E_RUNTIME_LOG_PATH = $runtimeLog
    $env:SYSTEM_E2E_RUNTIME_STOP_PATH = $runtimeStop
    $env:AGENT_MODEL_PROVIDER = 'stub'

    $testExit = Invoke-CapturedProcess $maven @(
        '-f', 'agent-service/pom.xml',
        '-Dtest=AgentSystemE2ETest',
        '-Dsurefire.failIfNoSpecifiedTests=false',
        "-Dsurefire.reportsDirectory=$surefireReports",
        "-Dagent.runtime.python=$python",
        'test'
    ) $repository $mavenOut $mavenErr
    if ($testExit -ne 0) {
        throw 'system_e2e.integration_failed'
    }
    if (-not (Test-Path -LiteralPath $evidence)) {
        throw 'system_e2e.runtime_evidence_missing'
    }
} catch {
    $failureCode = Get-SafeFailureCode $_.Exception.Message
} finally {
    foreach ($process in @($transactionProcess, $employeeProcess, $esProcess, $authProcess)) {
        Stop-Owned $process
    }
    $ownedProcessesStopped = -not (@($transactionProcess, $employeeProcess, $esProcess, $authProcess) |
        Where-Object { $null -ne $_ -and -not $_.HasExited })
    $sensitive = @($secret, $adminToken, $unknownToken, $employeeIdentifier, $knowledgeQuestion, $transactionQuestion) |
        Where-Object { -not [string]::IsNullOrEmpty([string]$_) }
    $rawArtifacts = @($rawLogs)
    if (Test-Path -LiteralPath $surefireReports) {
        $rawArtifacts += @(Get-ChildItem -LiteralPath $surefireReports -Recurse -File)
    }
    foreach ($log in $rawArtifacts) {
        if (-not (Test-Path -LiteralPath $log)) {
            continue
        }
        if ((Get-Item -LiteralPath $log).Length -gt 33554432) {
            $failureCode = 'system_e2e.log_scan_failed'
            continue
        }
        $text = Get-Content -LiteralPath $log -Raw -Encoding UTF8
        foreach ($value in $sensitive) {
            if ($text.Contains([string]$value)) {
                $logLeakCount++
            }
        }
    }
    foreach ($log in $rawArtifacts) {
        if (Test-Path -LiteralPath $log) {
            Remove-Item -LiteralPath $log -Force
        }
    }
    if (Test-Path -LiteralPath $surefireReports) {
        Remove-Item -LiteralPath $surefireReports -Recurse -Force
    }
    if (Test-Path -LiteralPath $runtimeStop) {
        Remove-Item -LiteralPath $runtimeStop -Force
    }
    $rawLogsDeleted = -not ($rawArtifacts | Where-Object { Test-Path -LiteralPath $_ }) -and
        -not (Test-Path -LiteralPath $surefireReports)
}

if ($logLeakCount -gt 0) {
    $failureCode = 'system_e2e.log_leak'
}
if (-not $ownedProcessesStopped) {
    $failureCode = 'system_e2e.cleanup_failed'
}
if (-not $rawLogsDeleted) {
    $failureCode = 'system_e2e.raw_log_cleanup_failed'
}

if (Test-Path -LiteralPath $evidence) {
    $result = Get-Content -LiteralPath $evidence -Raw -Encoding UTF8 | ConvertFrom-Json
} else {
    $result = [pscustomobject][ordered]@{
        schemaVersion = 1
        workPackage = 'WP-SYSTEM-E2E-01'
        status = 'failed'
        failureCode = $failureCode
        providers = [pscustomobject][ordered]@{
            knowledge = 'real'; employee = 'real'; transaction = 'real'; model = 'stub'
        }
        cases = @()
        requestCounts = [pscustomobject][ordered]@{
            knowledgeSearch = 0; embedding = 0; rerank = 0; employee = 0; transaction = 0
            otherBusinessEndpoints = 0; localKnowledgeModel = 0; answerGeneration = 0; externalModelOutbound = 0
        }
        security = [pscustomobject][ordered]@{ logLeakCount = 0; sensitivePersistence = $false }
        cleanup = [pscustomobject][ordered]@{
            runtimeClosed = $false; ownedProcessesStopped = $false; rawLogsDeleted = $false
        }
    }
}
$passed = [string]::IsNullOrEmpty($failureCode)
$result.status = if ($passed) { 'passed' } else { 'failed' }
$result.failureCode = if ($passed) { $null } else { $failureCode }
$result.security.logLeakCount = $logLeakCount
$result.security.sensitivePersistence = $logLeakCount -gt 0
$result.cleanup.ownedProcessesStopped = $ownedProcessesStopped
$result.cleanup.rawLogsDeleted = $rawLogsDeleted
[IO.File]::WriteAllText($evidence, ($result | ConvertTo-Json -Depth 10 -Compress), [Text.UTF8Encoding]::new($false))

if ($passed) {
    Push-Location (Join-Path $repository 'agent-runtime')
    try {
        $env:PYTHONPATH = 'src;.'
        & $python -m tests.system_e2e.evidence_contract $evidence
        if ($LASTEXITCODE -ne 0) {
            throw 'system_e2e.evidence_validation_failed'
        }
    } finally {
        Pop-Location
    }
}
if (-not $passed) {
    throw $failureCode
}

[pscustomobject]@{
    status = 'passed'
    evidence = $evidence
    cases = $result.cases.Count
    externalModelOutbound = $result.requestCounts.externalModelOutbound
    logLeakCount = $result.security.logLeakCount
}
