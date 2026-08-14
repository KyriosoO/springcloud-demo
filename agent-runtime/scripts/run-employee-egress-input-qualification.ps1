[CmdletBinding()]
param(
    [string]$RepositoryRoot = (Split-Path -Parent (Split-Path -Parent $PSScriptRoot)),
    [string]$EvidenceDirectory = 'agent-runtime/tests/integration/adapters/employee/evidence'
)

$ErrorActionPreference = 'Stop'
$repository = [IO.Path]::GetFullPath($RepositoryRoot)
if ($repository -cne 'D:\codex') {
    throw 'employee.egress_input_qualify_repository_invalid'
}

$runId = 'employee-egress-input-qualification-v1-20260814-candidate-01'
$runStatus = 'retired_failed_inconclusive'
if ($runStatus -ceq 'retired_failed_inconclusive') {
    throw 'employee.egress_input_qualify_run_retired'
}
$targetDirectory = [IO.Path]::GetFullPath((Join-Path $repository $EvidenceDirectory))
$expectedDirectory = [IO.Path]::GetFullPath((Join-Path $repository 'agent-runtime\tests\integration\adapters\employee\evidence'))
if ($targetDirectory -cne $expectedDirectory) {
    throw 'employee.egress_input_qualify_evidence_directory_invalid'
}
$evidencePath = Join-Path $targetDirectory "$runId.json"
if (Test-Path -LiteralPath $evidencePath) {
    throw 'employee.egress_input_qualify_evidence_exists'
}

$history = [ordered]@{
    'agent-runtime/tests/integration/adapters/employee/evidence/employee-egress-v1-20260813-candidate-01.manifest.json' = 'c3cdfacd32797474f68e11758ec094df97a95d56fb0efed9355ccfaa6a145c57'
    'agent-runtime/tests/integration/adapters/employee/evidence/employee-egress-v1-20260813-candidate-01.authorization.json' = '52b9075117f3e5f3ea84f1ea3c5da846c7b168f013fc4d8523d7ed52979f416c'
    'agent-runtime/tests/integration/adapters/employee/evidence/wp-emp-egress-env-diag-01-20260814T004517Z.json' = '2bc16cf63f3775d778925a5a5a66cfbae5138401e2f209e8288f4db076598a2c'
    'agent-runtime/tests/integration/adapters/employee/evidence/employee-egress-v1-20260813-candidate-01.pre-model-failure-20260814T005222Z.json' = '1a55b324fc912ee4e9133c2946183473347eb8e7f3337f8e33286bdf96f0b76f'
    'agent-runtime/tests/integration/adapters/employee/evidence/employee-egress-v2-20260814-candidate-02.manifest.json' = '28cd7b04b0700b43e5feed7bdef22e9da0494cd941e2e9f96b698a75b21b03b1'
    'agent-runtime/tests/integration/adapters/employee/evidence/employee-egress-v2-20260814-candidate-02.authorization.json' = '6fe6489fb5d32481909b88b860325dbbc35dec0c242d86f106327222e790c971'
    'agent-runtime/tests/integration/adapters/employee/evidence/employee-egress-v2-20260814-candidate-02.lifecycle.jsonl' = '15982e15d454795d7052215ad46221b6f85cc26726ca0267a597f6d6002ec679'
    'agent-runtime/tests/integration/adapters/employee/evidence/employee-egress-v2-20260814-candidate-02.result.json' = 'dd8a5bac1586da4e44cc6a583c07289a91012bc34892f848ffb4a0241ae7561d'
}
foreach ($entry in $history.GetEnumerator()) {
    $path = Join-Path $repository $entry.Key
    if (-not (Test-Path -LiteralPath $path)) {
        throw 'employee.egress_input_qualify_history_missing'
    }
    $actual = (Get-FileHash -Algorithm SHA256 -LiteralPath $path).Hash.ToLowerInvariant()
    if ($actual -cne $entry.Value) {
        throw 'employee.egress_input_qualify_history_drift'
    }
}

$environmentNames = @(
    'COMMON_SECURITY_JWT_HMAC_KEY_ACTIVE',
    'RUN_EMPLOYEE_EGRESS_INPUT_QUALIFY',
    'EMPLOYEE_EGRESS_QUALIFY_ADMIN_JWT',
    'EMPLOYEE_EGRESS_QUALIFY_REPOSITORY_ROOT',
    'EMPLOYEE_EGRESS_QUALIFY_PROBE_OUTPUT',
    'EMPLOYEE_EGRESS_QUALIFY_PYTHON_LOG',
    'EMPLOYEE_EGRESS_QUALIFY_PYTHON_JUNIT',
    'EMPLOYEE_EGRESS_QUALIFY_PYTHON_EXECUTABLE',
    'PYTHONPATH'
)
$environmentSnapshot = @{}
foreach ($name in $environmentNames) {
    $environmentSnapshot[$name] = [Environment]::GetEnvironmentVariable($name, 'Process')
}

$maintainerIdentifier = [Environment]::GetEnvironmentVariable('EMPLOYEE_EGRESS_QUALIFY_TEST_IDENTIFIER', 'Process')
$tempRoot = [IO.Path]::GetFullPath([IO.Path]::GetTempPath())
$runRoot = [IO.Path]::GetFullPath((Join-Path $tempRoot "wp-emp-egress-input-qualify-$([Guid]::NewGuid().ToString('N'))"))
if (-not $runRoot.StartsWith($tempRoot, [StringComparison]::OrdinalIgnoreCase) -or
        -not [IO.Path]::GetFileName($runRoot).StartsWith('wp-emp-egress-input-qualify-', [StringComparison]::Ordinal)) {
    throw 'employee.egress_input_qualify_temp_path_invalid'
}
New-Item -ItemType Directory -Path $runRoot | Out-Null

$authOut = Join-Path $runRoot 'auth.out.log'
$authErr = Join-Path $runRoot 'auth.err.log'
$buildOut = Join-Path $runRoot 'build.out.log'
$buildErr = Join-Path $runRoot 'build.err.log'
$mavenOut = Join-Path $runRoot 'maven.out.log'
$mavenErr = Join-Path $runRoot 'maven.err.log'
$pythonLog = Join-Path $runRoot 'python.log'
$pythonJunit = Join-Path $runRoot 'python-junit.xml'
$probeOutput = Join-Path $runRoot 'qualification-probe.json'
$logFiles = @($authOut, $authErr, $buildOut, $buildErr, $mavenOut, $mavenErr, $pythonLog, $pythonJunit)
$surefireDirectory = [IO.Path]::GetFullPath((Join-Path $repository 'employee-service\target\surefire-reports'))
$surefireFiles = @(
    (Join-Path $surefireDirectory 'TEST-com.dylan.employee.live.EmployeeEgressInputQualificationLiveIntegrationTest.xml'),
    (Join-Path $surefireDirectory 'com.dylan.employee.live.EmployeeEgressInputQualificationLiveIntegrationTest.txt')
)

$keyBytes = [Security.Cryptography.RandomNumberGenerator]::GetBytes(48)
$secret = [Convert]::ToBase64String($keyBytes)
$adminPassword = $null
$adminToken = $null
$authProcess = $null
$probe = $null
$rawLogsDeleted = $false

function Invoke-CapturedProcess(
    [string]$FilePath,
    [string[]]$ArgumentList,
    [string]$WorkingDirectory,
    [string]$StandardOutput,
    [string]$StandardError
) {
    $process = Start-Process -FilePath $FilePath -ArgumentList $ArgumentList `
        -WorkingDirectory $WorkingDirectory -WindowStyle Hidden -Wait -PassThru `
        -RedirectStandardOutput $StandardOutput -RedirectStandardError $StandardError
    return $process.ExitCode
}

function Get-FreeLoopbackPort {
    $listener = [Net.Sockets.TcpListener]::new([Net.IPAddress]::Loopback, 0)
    try {
        $listener.Start()
        return ([Net.IPEndPoint]$listener.LocalEndpoint).Port
    }
    finally {
        $listener.Stop()
    }
}

function Wait-AuthReady([int]$Port, [Diagnostics.Process]$Process) {
    for ($attempt = 0; $attempt -lt 90; $attempt++) {
        if ($Process.HasExited) {
            throw 'employee.egress_input_qualify_auth_process_exited'
        }
        try {
            $response = Invoke-WebRequest -Uri "http://127.0.0.1:$Port/public/test" -Method Get `
                -TimeoutSec 2 -SkipHttpErrorCheck
            if ($response.StatusCode -eq 200) {
                $listener = Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue |
                    Where-Object { $_.OwningProcess -eq $Process.Id }
                if ($listener) {
                    return
                }
                throw 'employee.egress_input_qualify_auth_pid_mismatch'
            }
        }
        catch {
            if ($_.Exception.Message -eq 'employee.egress_input_qualify_auth_pid_mismatch') {
                throw
            }
        }
        Start-Sleep -Milliseconds 500
    }
    throw 'employee.egress_input_qualify_auth_readiness_timeout'
}

function Get-AdminPassword {
    $path = Join-Path $repository 'auth-service\src\main\resources\auth-users.yml'
    $text = Get-Content -LiteralPath $path -Raw -Encoding UTF8
    $match = [regex]::Match($text, '(?ms)^\s{4}admin:\s*\r?\n\s+password:\s*([^\r\n]+)')
    if (-not $match.Success) {
        throw 'employee.egress_input_qualify_auth_fixture_missing'
    }
    $stored = $match.Groups[1].Value.Trim().Trim('"').Trim("'")
    if (-not $stored.StartsWith('{noop}')) {
        throw 'employee.egress_input_qualify_auth_fixture_not_local'
    }
    return $stored.Substring(6)
}

function Get-AdminToken([int]$Port, [string]$Password) {
    $session = [Microsoft.PowerShell.Commands.WebRequestSession]::new()
    $body = @{ userId = 'admin'; password = $Password } | ConvertTo-Json -Compress
    $response = Invoke-WebRequest -Uri "http://127.0.0.1:$Port/login" -Method Post `
        -ContentType 'application/json' -Body $body -WebSession $session -TimeoutSec 5 -SkipHttpErrorCheck
    if ($response.StatusCode -ne 200) {
        throw 'employee.egress_input_qualify_login_failed'
    }
    $cookie = $session.Cookies.GetCookies("http://127.0.0.1:$Port")['AUTH_TOKEN']
    if ($null -eq $cookie -or [string]::IsNullOrWhiteSpace($cookie.Value)) {
        throw 'employee.egress_input_qualify_token_missing'
    }
    return $cookie.Value
}

function Stop-OwnedAuth {
    if ($null -ne $script:authProcess -and -not $script:authProcess.HasExited) {
        $owned = Get-Process -Id $script:authProcess.Id -ErrorAction SilentlyContinue
        if ($null -ne $owned -and $owned.Id -eq $script:authProcess.Id) {
            Stop-Process -Id $script:authProcess.Id -Force
            $script:authProcess.WaitForExit(10000) | Out-Null
        }
    }
}

function Test-SensitiveLogs {
    $literals = @($secret, $adminPassword, $adminToken)
    if (-not [string]::IsNullOrWhiteSpace($maintainerIdentifier)) {
        $literals += $maintainerIdentifier
        $literals += [Uri]::EscapeDataString($maintainerIdentifier)
    }
    foreach ($path in ($logFiles + $surefireFiles)) {
        if (-not (Test-Path -LiteralPath $path)) {
            continue
        }
        if ((Get-Item -LiteralPath $path).Length -gt 8388608) {
            return $true
        }
        $text = [string](Get-Content -LiteralPath $path -Raw -Encoding UTF8)
        foreach ($literal in $literals) {
            if (-not [string]::IsNullOrEmpty([string]$literal) -and $text.Contains([string]$literal)) {
                return $true
            }
        }
    }
    return $false
}

function Remove-TemporaryArtifacts {
    foreach ($path in $surefireFiles) {
        if (Test-Path -LiteralPath $path) {
            $resolved = [IO.Path]::GetFullPath($path)
            if (-not $resolved.StartsWith($surefireDirectory + [IO.Path]::DirectorySeparatorChar,
                    [StringComparison]::OrdinalIgnoreCase)) {
                throw 'employee.egress_input_qualify_surefire_path_invalid'
            }
            Remove-Item -LiteralPath $resolved -Force
        }
    }
    $resolvedRoot = [IO.Path]::GetFullPath($runRoot)
    if (-not $resolvedRoot.StartsWith($tempRoot, [StringComparison]::OrdinalIgnoreCase) -or
            -not [IO.Path]::GetFileName($resolvedRoot).StartsWith('wp-emp-egress-input-qualify-', [StringComparison]::Ordinal)) {
        throw 'employee.egress_input_qualify_cleanup_path_invalid'
    }
    if (Test-Path -LiteralPath $resolvedRoot) {
        Remove-Item -LiteralPath $resolvedRoot -Recurse -Force
    }
    $script:rawLogsDeleted = -not (Test-Path -LiteralPath $resolvedRoot) -and
        -not ($surefireFiles | Where-Object { Test-Path -LiteralPath $_ })
}

try {
    $maven = (Get-Command mvn.cmd -ErrorAction Stop).Source
    $python = (Get-Command python.exe -ErrorAction Stop).Source
    $buildExit = Invoke-CapturedProcess $maven @(
        '-f', 'serviceCenter/pom.xml', '-pl', ':auth-service', '-am', '-DskipTests', 'package'
    ) $repository $buildOut $buildErr
    if ($buildExit -ne 0) {
        throw 'employee.egress_input_qualify_auth_build_failed'
    }

    Remove-Item Env:\LLM_API_KEY -ErrorAction SilentlyContinue
    $env:COMMON_SECURITY_JWT_HMAC_KEY_ACTIVE = $secret
    $authPort = Get-FreeLoopbackPort
    $commonArgs = @(
        "--server.port=$authPort",
        '--spring.cloud.config.enabled=false',
        '--spring.config.import=',
        '--eureka.client.enabled=false',
        '--common.security.secrets.source-order[0]=environment',
        '--common.security.secrets.allow-config-values=false',
        '--common.security.secrets.fail-fast=true',
        '--common.security.secrets.jwt.active-key-id=ACTIVE',
        '--common.security.secrets.jwt.keys.ACTIVE.env=COMMON_SECURITY_JWT_HMAC_KEY_ACTIVE',
        '--common.security.secrets.jwt.keys.ACTIVE.value='
    )
    $authJar = Join-Path $repository 'auth-service\target\auth-service-0.0.1-SNAPSHOT.jar'
    if (-not (Test-Path -LiteralPath $authJar)) {
        throw 'employee.egress_input_qualify_auth_jar_missing'
    }
    $authProcess = Start-Process -FilePath 'java' -ArgumentList (@('-jar', $authJar) + $commonArgs) `
        -WorkingDirectory (Join-Path $repository 'auth-service') -WindowStyle Hidden -PassThru `
        -RedirectStandardOutput $authOut -RedirectStandardError $authErr
    Wait-AuthReady $authPort $authProcess

    $adminPassword = Get-AdminPassword
    $adminToken = Get-AdminToken $authPort $adminPassword
    $env:RUN_EMPLOYEE_EGRESS_INPUT_QUALIFY = '1'
    $env:EMPLOYEE_EGRESS_QUALIFY_ADMIN_JWT = $adminToken
    $env:EMPLOYEE_EGRESS_QUALIFY_REPOSITORY_ROOT = $repository
    $env:EMPLOYEE_EGRESS_QUALIFY_PROBE_OUTPUT = $probeOutput
    $env:EMPLOYEE_EGRESS_QUALIFY_PYTHON_LOG = $pythonLog
    $env:EMPLOYEE_EGRESS_QUALIFY_PYTHON_JUNIT = $pythonJunit
    $env:EMPLOYEE_EGRESS_QUALIFY_PYTHON_EXECUTABLE = $python

    $testExit = Invoke-CapturedProcess $maven @(
        '-f', 'serviceCenter/pom.xml', '-pl', ':employee-service', '-am',
        '-Dtest=com.dylan.employee.live.EmployeeEgressInputQualificationLiveIntegrationTest',
        '-Dsurefire.failIfNoSpecifiedTests=false', 'test'
    ) $repository $mavenOut $mavenErr
    Stop-OwnedAuth
    if ($testExit -ne 0) {
        if (Test-SensitiveLogs) {
            throw 'employee.egress_input_qualify_log_leak'
        }
        throw 'employee.egress_input_qualify_integration_failed'
    }
    if (-not (Test-Path -LiteralPath $probeOutput)) {
        throw 'employee.egress_input_qualify_probe_missing'
    }
    $probe = Get-Content -LiteralPath $probeOutput -Raw -Encoding UTF8 | ConvertFrom-Json
    if ($probe.status -cne 'qualified' -or $probe.fieldPresence.position -ne $true -or
            $probe.fieldPresence.workBaseSi -ne $true -or $probe.egressReason -cne 'qualified' -or
            $probe.requestCounts.employeeDetail -ne 1 -or
            $probe.requestCounts.otherEmployeeEndpoints -ne 0 -or $probe.requestCounts.model -ne 0 -or
            $probe.requestCounts.databaseSelectionRows -notin @(0, 1)) {
        throw 'employee.egress_input_qualify_result_invalid'
    }
    if (Test-SensitiveLogs) {
        throw 'employee.egress_input_qualify_log_leak'
    }

    Remove-TemporaryArtifacts
    if (-not $rawLogsDeleted) {
        throw 'employee.egress_input_qualify_raw_log_delete_failed'
    }

    $evidence = [ordered]@{
        schemaVersion = 1
        workPackageId = 'WP-EMP-EGRESS-INPUT-QUALIFY-01'
        runId = $runId
        selectionMode = [string]$probe.selectionMode
        status = [string]$probe.status
        fieldPresence = [ordered]@{
            position = [bool]$probe.fieldPresence.position
            workBaseSi = [bool]$probe.fieldPresence.workBaseSi
        }
        egressReason = [string]$probe.egressReason
        requestCounts = [ordered]@{
            databaseSelectionRows = [int]$probe.requestCounts.databaseSelectionRows
            employeeDetail = [int]$probe.requestCounts.employeeDetail
            otherEmployeeEndpoints = [int]$probe.requestCounts.otherEmployeeEndpoints
            model = [int]$probe.requestCounts.model
        }
        safety = [ordered]@{
            identifierPersisted = $false
            jwtPersisted = $false
            fieldValuesPersisted = $false
            rawResponsePersisted = $false
            llmApiKeyRead = $false
            modelOutbound = $false
            logLeakCount = 0
            rawLogsDeleted = $true
        }
    }
    $json = $evidence | ConvertTo-Json -Depth 8 -Compress
    foreach ($literal in @($secret, $adminPassword, $adminToken, $maintainerIdentifier)) {
        if (-not [string]::IsNullOrEmpty([string]$literal) -and $json.Contains([string]$literal)) {
            throw 'employee.egress_input_qualify_evidence_leak'
        }
    }
    New-Item -ItemType Directory -Path $targetDirectory -Force | Out-Null
    $stream = [IO.File]::Open($evidencePath, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write, [IO.FileShare]::None)
    try {
        $bytes = [Text.Encoding]::UTF8.GetBytes($json + "`n")
        $stream.Write($bytes, 0, $bytes.Length)
        $stream.Flush($true)
    }
    finally {
        $stream.Dispose()
    }

    $env:PYTHONPATH = "$repository\agent-runtime\src;$repository\agent-runtime"
    $validation = & $python -c "import json; from pathlib import Path; from tests.integration.adapters.employee.egress_input_qualification import validate_input_qualification_evidence; validate_input_qualification_evidence(json.loads(Path(r'$evidencePath').read_text(encoding='utf-8')))" 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw 'employee.egress_input_qualify_evidence_schema_invalid'
    }
    [pscustomobject]@{
        status = 'qualified'
        employeeDetailRequests = 1
        modelCalls = 0
        logLeakCount = 0
        evidence = $evidencePath
    }
}
finally {
    Stop-OwnedAuth
    if (Test-Path -LiteralPath $runRoot) {
        try {
            Test-SensitiveLogs | Out-Null
            Remove-TemporaryArtifacts
        }
        catch {
        }
    }
    foreach ($name in $environmentNames) {
        [Environment]::SetEnvironmentVariable($name, $environmentSnapshot[$name], 'Process')
    }
    [Array]::Clear($keyBytes, 0, $keyBytes.Length)
    $secret = $null
    $adminPassword = $null
    $adminToken = $null
}
