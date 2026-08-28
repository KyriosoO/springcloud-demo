[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$FrozenRepository,

    [Parameter(Mandatory = $true)]
    [string]$AuthorizationPath,

    [Parameter(Mandatory = $true)]
    [string]$ResultRoot,

    [string]$ArtifactRepository = 'D:\codex',

    [string]$ManifestRelativePath = 'tests\uat\employee_nl\evidence\employee-natural-language-v1-20260828-candidate-01.manifest.json',

    [string]$ExpectedRunId = 'employee-natural-language-v1-20260828-candidate-01',

    [int]$ExpectedMaximumModelCalls = 30,

    [int]$ExpectedMaximumEmployeeSearchCalls = 30,

    [string]$RunnerModule = 'tests.uat.employee_nl.runner'
)

$ErrorActionPreference = 'Stop'
$frozenRepositoryPath = [IO.Path]::GetFullPath($FrozenRepository)
$artifactRepositoryPath = [IO.Path]::GetFullPath($ArtifactRepository)
$authorizationFile = [IO.Path]::GetFullPath($AuthorizationPath)
$resultRootPath = [IO.Path]::GetFullPath($ResultRoot)
$runtime = Join-Path $frozenRepositoryPath 'agent-runtime'
$manifest = Join-Path $runtime $ManifestRelativePath
$launcherEvidence = Join-Path $resultRootPath 'launcher-evidence.json'
$expectedAuthorizationReference = 'P3_00:GATE-082'

foreach ($required in @($frozenRepositoryPath, $artifactRepositoryPath, $authorizationFile, $manifest)) {
    if (-not (Test-Path -LiteralPath $required)) {
        throw 'employee_nl_uat.required_asset_missing'
    }
}
if (Test-Path -LiteralPath $launcherEvidence) {
    throw 'employee_nl_uat.launcher_evidence_exists'
}
$head = (& git -C $frozenRepositoryPath rev-parse HEAD).Trim()
if ($LASTEXITCODE -ne 0 -or $head -notmatch '^[0-9a-f]{40}$') {
    throw 'employee_nl_uat.frozen_head_invalid'
}
$dirty = @(& git -C $frozenRepositoryPath status --porcelain --untracked-files=no)
if ($LASTEXITCODE -ne 0 -or $dirty.Count -ne 0) {
    throw 'employee_nl_uat.frozen_worktree_dirty'
}
$manifestSha256 = (Get-FileHash -LiteralPath $manifest -Algorithm SHA256).Hash.ToLowerInvariant()
$authorization = Get-Content -LiteralPath $authorizationFile -Raw -Encoding UTF8 | ConvertFrom-Json
if (
    $authorization.runId -cne $ExpectedRunId -or
    $authorization.authorizationReference -cne $expectedAuthorizationReference -or
    $authorization.frozenHead -cne $head -or
    $authorization.manifestSha256 -cne $manifestSha256 -or
    [int]$authorization.maximumModelCalls -ne $ExpectedMaximumModelCalls -or
    [int]$authorization.maximumEmployeeSearchCalls -ne $ExpectedMaximumEmployeeSearchCalls -or
    [bool]$authorization.liveExecutionAuthorized -ne $true
) {
    throw 'employee_nl_uat.authorization_binding_invalid'
}
$modelKey = [Environment]::GetEnvironmentVariable('LLM_API_KEY', 'Process')
if ([string]::IsNullOrWhiteSpace($modelKey)) {
    throw 'employee_nl_uat.model_key_missing'
}

function Test-TcpReady([int]$Port) {
    $socket = [Net.Sockets.TcpClient]::new()
    try {
        $connection = $socket.ConnectAsync('127.0.0.1', $Port)
        return $connection.Wait(1500) -and $socket.Connected
    } catch {
        return $false
    } finally {
        $socket.Dispose()
    }
}

foreach ($infrastructurePort in @(9200)) {
    if (-not (Test-TcpReady $infrastructurePort)) {
        throw 'employee_nl_uat.infrastructure_unavailable'
    }
}
foreach ($ownedPort in @(19201, 19210)) {
    if (Test-TcpReady $ownedPort) {
        throw 'employee_nl_uat.owned_port_occupied'
    }
}

$jars = [ordered]@{
    es = Join-Path $artifactRepositoryPath 'es-query-service\target\es-query-service-0.0.1-SNAPSHOT.jar'
    employee = Join-Path $artifactRepositoryPath 'employee-service\target\employee-service-0.0.1-SNAPSHOT.jar'
}
if (@($jars.Values | Where-Object { -not (Test-Path -LiteralPath $_) }).Count -ne 0) {
    throw 'employee_nl_uat.service_jar_missing'
}

$runRoot = Join-Path $artifactRepositoryPath ('.codex-live\employee-nl-uat\' + [Guid]::NewGuid().ToString('N'))
New-Item -Path $runRoot -ItemType Directory -Force | Out-Null
New-Item -Path $resultRootPath -ItemType Directory -Force | Out-Null
$serviceProcesses = [System.Collections.Generic.List[Diagnostics.Process]]::new()
$logPaths = [System.Collections.Generic.List[string]]::new()
$keyBytes = [Security.Cryptography.RandomNumberGenerator]::GetBytes(48)
$sharedSecret = [Convert]::ToBase64String($keyBytes)
$adminToken = $null
$deniedToken = $null
$failureCode = $null
$logsDeleted = $false

$managedEnvironmentNames = @(
    'LLM_API_KEY', 'COMMON_SECURITY_JWT_HMAC_KEY_ACTIVE', 'AGENT_MODEL_PROVIDER',
    'AGENT_MODEL_ACTION_TIMEOUT_MS', 'RUN_EMPLOYEE_NL_UAT',
    'EMPLOYEE_NL_UAT_ADMIN_JWT', 'EMPLOYEE_NL_UAT_DENIED_JWT', 'PYTHONPATH'
)
$previousEnvironment = @{}
foreach ($name in $managedEnvironmentNames) {
    $previousEnvironment[$name] = [Environment]::GetEnvironmentVariable($name, 'Process')
}

function ConvertTo-Base64Url([byte[]]$Bytes) {
    return [Convert]::ToBase64String($Bytes).TrimEnd('=').Replace('+', '-').Replace('/', '_')
}

function New-TestToken([byte[]]$Bytes, [string]$Subject, [string]$Role) {
    $now = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds()
    $header = [ordered]@{ alg = 'HS256'; kid = 'ACTIVE' } | ConvertTo-Json -Compress
    $claims = [ordered]@{
        sub = $Subject; iat = $now; exp = $now + 1800; token_type = 'user'; role = @($Role)
    } | ConvertTo-Json -Compress
    $unsigned = "$(ConvertTo-Base64Url ([Text.Encoding]::UTF8.GetBytes($header))).$(ConvertTo-Base64Url ([Text.Encoding]::UTF8.GetBytes($claims)))"
    $signer = [Security.Cryptography.HMACSHA256]::new($Bytes)
    try {
        $signature = ConvertTo-Base64Url ($signer.ComputeHash([Text.Encoding]::ASCII.GetBytes($unsigned)))
    } finally {
        $signer.Dispose()
    }
    return "$unsigned.$signature"
}

function Start-OwnedService([string]$Name, [string[]]$Arguments, [string]$Directory) {
    $standardOutput = Join-Path $runRoot "$Name.out.log"
    $standardError = Join-Path $runRoot "$Name.err.log"
    $logPaths.Add($standardOutput)
    $logPaths.Add($standardError)
    $process = Start-Process -FilePath 'java' -ArgumentList $Arguments `
        -WorkingDirectory $Directory -WindowStyle Hidden -PassThru `
        -RedirectStandardOutput $standardOutput -RedirectStandardError $standardError
    $serviceProcesses.Add($process)
    return $process
}

function Wait-OwnedService(
    [Diagnostics.Process]$Process, [int]$Port, [string]$Uri, [int[]]$Statuses
) {
    for ($attempt = 0; $attempt -lt 120; $attempt++) {
        $Process.Refresh()
        if ($Process.HasExited) {
            throw 'employee_nl_uat.service_process_exited'
        }
        $ownedListener = @(Get-NetTCPConnection -State Listen -LocalPort $Port `
            -ErrorAction SilentlyContinue | Where-Object { $_.OwningProcess -eq $Process.Id })
        if ($ownedListener.Count -ge 1) {
            try {
                $response = Invoke-WebRequest -Uri $Uri -Method Get -TimeoutSec 2 `
                    -SkipHttpErrorCheck
                if ($Statuses -contains [int]$response.StatusCode) {
                    return
                }
            } catch {
            }
        }
        Start-Sleep -Milliseconds 500
    }
    throw 'employee_nl_uat.service_readiness_failed'
}

try {
    [Environment]::SetEnvironmentVariable('LLM_API_KEY', $null, 'Process')
    [Environment]::SetEnvironmentVariable('COMMON_SECURITY_JWT_HMAC_KEY_ACTIVE', $sharedSecret, 'Process')
    $configLocation = 'optional:file:' + ($artifactRepositoryPath.Replace('\', '/')) + '/config-service/src/main/resources/config/'
    $commonArguments = @(
        '--spring.main.banner-mode=off', '--spring.cloud.config.enabled=false',
        '--spring.config.import=', "--spring.config.additional-location=$configLocation",
        '--eureka.client.enabled=false', '--common.security.secrets.source-order[0]=environment',
        '--common.security.secrets.allow-config-values=false', '--common.security.secrets.fail-fast=true',
        '--common.security.secrets.jwt.active-key-id=ACTIVE',
        '--common.security.secrets.jwt.keys.ACTIVE.env=COMMON_SECURITY_JWT_HMAC_KEY_ACTIVE',
        '--common.security.secrets.jwt.keys.ACTIVE.value='
    )
    $es = Start-OwnedService 'es-query' (@(
        '-jar', $jars.es, '--server.port=19201',
        '--spring.profiles.active=datasource,es',
        '--spring.elasticsearch.uris=http://127.0.0.1:9200',
        '--es.query.total-hits-threshold=10000'
    ) + $commonArguments) (Join-Path $artifactRepositoryPath 'es-query-service')
    $employee = Start-OwnedService 'employee' (@(
        '-jar', $jars.employee, '--server.port=19210',
        '--spring.cloud.discovery.client.simple.instances.es-query-service[0].uri=http://127.0.0.1:19201'
    ) + $commonArguments) (Join-Path $artifactRepositoryPath 'employee-service')
    Wait-OwnedService $es 19201 'http://127.0.0.1:19201/actuator/health' @(200, 401, 403)
    Wait-OwnedService $employee 19210 'http://127.0.0.1:19210/actuator/health' @(200, 401, 403)

    $adminToken = New-TestToken $keyBytes 'employee-nl-uat-admin' 'ADMIN'
    $deniedToken = New-TestToken $keyBytes 'employee-nl-uat-denied' 'UNKNOWN'
    [Environment]::SetEnvironmentVariable('RUN_EMPLOYEE_NL_UAT', '1', 'Process')
    [Environment]::SetEnvironmentVariable('AGENT_MODEL_PROVIDER', 'deepseek', 'Process')
    [Environment]::SetEnvironmentVariable('AGENT_MODEL_ACTION_TIMEOUT_MS', '15000', 'Process')
    [Environment]::SetEnvironmentVariable('EMPLOYEE_NL_UAT_ADMIN_JWT', $adminToken, 'Process')
    [Environment]::SetEnvironmentVariable('EMPLOYEE_NL_UAT_DENIED_JWT', $deniedToken, 'Process')
    [Environment]::SetEnvironmentVariable('PYTHONPATH', "$runtime\src;$runtime", 'Process')
    [Environment]::SetEnvironmentVariable('LLM_API_KEY', $modelKey, 'Process')
    Push-Location $runtime
    try {
        & python -m $RunnerModule `
            --repository $frozenRepositoryPath `
            --manifest $manifest `
            --authorization $authorizationFile `
            --result-root $resultRootPath
        if ($LASTEXITCODE -ne 0) {
            throw 'employee_nl_uat.runner_failed'
        }
    } finally {
        Pop-Location
        [Environment]::SetEnvironmentVariable('LLM_API_KEY', $null, 'Process')
    }
} catch {
    $message = [string]$_.Exception.Message
    if ($message -match '^employee_nl_uat\.[a-z0-9_]+(?::UAT-EMP-NL-[0-9]{3})?$') {
        $failureCode = $message
    } else {
        $failureCode = 'employee_nl_uat.unexpected_failure'
    }
} finally {
    foreach ($service in $serviceProcesses) {
        try {
            $service.Refresh()
            if (-not $service.HasExited) {
                Stop-Process -Id $service.Id -ErrorAction Stop
                if (-not $service.WaitForExit(5000)) {
                    Stop-Process -Id $service.Id -Force -ErrorAction Stop
                    [void]$service.WaitForExit(3000)
                }
            }
        } catch {
            if ($null -eq $failureCode) {
                $failureCode = 'employee_nl_uat.process_cleanup_failed'
            }
        }
    }
    $sensitiveValues = @($sharedSecret, $modelKey, $adminToken, $deniedToken) |
        Where-Object { -not [string]::IsNullOrWhiteSpace($_) }
    $logLeakCount = 0
    foreach ($log in $logPaths) {
        if (Test-Path -LiteralPath $log) {
            $text = Get-Content -LiteralPath $log -Raw -Encoding UTF8
            foreach ($secretValue in $sensitiveValues) {
                if ($null -ne $text -and $text.Contains([string]$secretValue, [StringComparison]::Ordinal)) {
                    $logLeakCount++
                }
            }
            Remove-Item -LiteralPath $log -Force
        }
    }
    if ((Test-Path -LiteralPath $runRoot) -and @(Get-ChildItem -LiteralPath $runRoot -Force).Count -eq 0) {
        Remove-Item -LiteralPath $runRoot -Force
        $logsDeleted = $true
    }
    foreach ($name in $managedEnvironmentNames) {
        [Environment]::SetEnvironmentVariable($name, $previousEnvironment[$name], 'Process')
    }
    [Array]::Clear($keyBytes, 0, $keyBytes.Length)

    $resultPath = Join-Path $resultRootPath 'result.json'
    if (Test-Path -LiteralPath $resultPath) {
        $result = Get-Content -LiteralPath $resultPath -Raw -Encoding UTF8 | ConvertFrom-Json
        $launcherStatus = if ($null -eq $failureCode -and $logLeakCount -eq 0 -and $logsDeleted) {
            'completed'
        } else {
            'failed'
        }
        $launcherRecord = [ordered]@{
            schemaVersion = 1
            status = $launcherStatus
            runId = $ExpectedRunId
            authorizationReference = $expectedAuthorizationReference
            frozenHead = $head
            manifestSha256 = $manifestSha256
            modelCalls = [int]$result.counts.modelCalls
            employeeSearchCalls = [int]$result.counts.employeeSearchCalls
            logLeakCount = $logLeakCount
            rawLogsRetained = -not $logsDeleted
            resultSha256 = (Get-FileHash -LiteralPath $resultPath -Algorithm SHA256).Hash.ToLowerInvariant()
        }
        $launcherRecord | ConvertTo-Json -Compress | Set-Content -LiteralPath $launcherEvidence -Encoding utf8NoBOM -NoNewline
    }
}

if ($null -ne $failureCode) {
    throw $failureCode
}
if (-not $logsDeleted) {
    throw 'employee_nl_uat.log_cleanup_incomplete'
}
if ($logLeakCount -ne 0) {
    throw 'employee_nl_uat.log_leak'
}

$finalResult = Get-Content -LiteralPath (Join-Path $resultRootPath 'result.json') -Raw -Encoding UTF8 | ConvertFrom-Json
[PSCustomObject]@{
    status = $finalResult.status
    cases = @($finalResult.cases).Count
    modelCalls = $finalResult.counts.modelCalls
    employeeSearchCalls = $finalResult.counts.employeeSearchCalls
    resultRoot = $resultRootPath
}
