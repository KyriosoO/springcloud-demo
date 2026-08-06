[CmdletBinding()]
param(
    [string]$RepositoryRoot = (Split-Path -Parent (Split-Path -Parent $PSScriptRoot)),
    [string]$EvidenceDirectory = 'agent-runtime/tests/integration/adapters/employee/evidence'
)

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'employee-live-log-safety.ps1')

$repository = [IO.Path]::GetFullPath($RepositoryRoot)
if ($repository -ne 'D:\codex') {
    throw 'employee.gateway_live_repository_invalid'
}

$maxGatewayRequests = 1
$environmentNames = @(
    'COMMON_SECURITY_JWT_HMAC_KEY_ACTIVE',
    'RUN_EMPLOYEE_GATEWAY_LOG_LIVE',
    'EMPLOYEE_GATEWAY_LIVE_GATEWAY_JAR',
    'EMPLOYEE_GATEWAY_LIVE_GATEWAY_PORT',
    'EMPLOYEE_GATEWAY_LIVE_GATEWAY_OUT_PATH',
    'EMPLOYEE_GATEWAY_LIVE_GATEWAY_ERR_PATH',
    'EMPLOYEE_GATEWAY_LIVE_JAVA_METRICS_PATH',
    'EMPLOYEE_GATEWAY_LIVE_JWT',
    'EMPLOYEE_GATEWAY_LIVE_SENTINEL',
    'EMPLOYEE_GATEWAY_LIVE_CORRELATION_ID'
)
$environmentSnapshot = @{}
foreach ($name in $environmentNames) {
    $environmentSnapshot[$name] = [Environment]::GetEnvironmentVariable($name, 'Process')
}

$tempRoot = [IO.Path]::GetFullPath([IO.Path]::GetTempPath())
$runRoot = [IO.Path]::GetFullPath((Join-Path $tempRoot "wp-emp-gateway-log-$([Guid]::NewGuid().ToString('N'))"))
if (-not $runRoot.StartsWith($tempRoot, [StringComparison]::OrdinalIgnoreCase) -or
        -not [IO.Path]::GetFileName($runRoot).StartsWith('wp-emp-gateway-log-', [StringComparison]::Ordinal)) {
    throw 'employee.gateway_live_temp_path_invalid'
}
New-Item -ItemType Directory -Path $runRoot | Out-Null

$buildOut = Join-Path $runRoot 'gateway-build.out.log'
$buildErr = Join-Path $runRoot 'gateway-build.err.log'
$mavenOut = Join-Path $runRoot 'employee-test.out.log'
$mavenErr = Join-Path $runRoot 'employee-test.err.log'
$gatewayOut = Join-Path $runRoot 'gateway.out.log'
$gatewayErr = Join-Path $runRoot 'gateway.err.log'
$javaMetrics = Join-Path $runRoot 'java-metrics.json'
$logFiles = @($buildOut, $buildErr, $mavenOut, $mavenErr, $gatewayOut, $gatewayErr, $javaMetrics)
$surefireReportDirectory = [IO.Path]::GetFullPath((Join-Path $runRoot 'surefire-reports'))
$surefireReportFiles = @(
    (Join-Path $surefireReportDirectory 'TEST-com.dylan.employee.live.EmployeeGatewayLogSafetyLiveIntegrationTest.xml'),
    (Join-Path $surefireReportDirectory 'com.dylan.employee.live.EmployeeGatewayLogSafetyLiveIntegrationTest.txt')
)

$keySeed = [Security.Cryptography.RandomNumberGenerator]::GetBytes(48)
$secret = [Convert]::ToBase64String($keySeed)
$sentinel = "SYNTHETIC-EMPLOYEE-GATEWAY-$([Guid]::NewGuid().ToString('N'))"
$subject = "synthetic-gateway-user-$([Guid]::NewGuid().ToString('N'))"
$correlationId = "employee-gateway-log-$([Guid]::NewGuid().ToString('N'))"
$fullPath = "/employees/$sentinel"
$token = $null
$runRootDeleted = $false
$surefireReportsDeleted = $true
$mavenStarted = $false
$started = [DateTimeOffset]::UtcNow

function ConvertTo-Base64Url([byte[]]$Bytes) {
    return [Convert]::ToBase64String($Bytes).TrimEnd('=').Replace('+', '-').Replace('/', '_')
}

function New-GatewayTestJwt {
    $now = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds()
    $header = [ordered]@{ alg = 'HS256'; kid = 'ACTIVE' } | ConvertTo-Json -Compress
    $claims = [ordered]@{
        sub = $subject
        iat = $now
        exp = $now + 3600
        token_type = 'user'
        role = @('ADMIN')
    } | ConvertTo-Json -Compress
    $unsigned = "$(ConvertTo-Base64Url ([Text.Encoding]::UTF8.GetBytes($header))).$(ConvertTo-Base64Url ([Text.Encoding]::UTF8.GetBytes($claims)))"
    # common-security decodes the Base64 environment value before constructing
    # the HMAC key, so the JWT must be signed with the original random bytes.
    $hmac = [Security.Cryptography.HMACSHA256]::new($keySeed)
    try {
        $signature = ConvertTo-Base64Url ($hmac.ComputeHash([Text.Encoding]::ASCII.GetBytes($unsigned)))
    } finally {
        $hmac.Dispose()
    }
    return "$unsigned.$signature"
}

function Get-FreeTcpPort {
    $listener = [Net.Sockets.TcpListener]::new([Net.IPAddress]::Loopback, 0)
    try {
        $listener.Start()
        return ([Net.IPEndPoint]$listener.LocalEndpoint).Port
    } finally {
        $listener.Stop()
    }
}

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

function Get-SensitiveLogCategory {
    $scanFiles = @($logFiles)
    if (Test-Path -LiteralPath $runRoot) {
        $scanFiles += @(Get-ChildItem -LiteralPath $runRoot -File -Recurse | Select-Object -ExpandProperty FullName)
    }
    foreach ($path in @($scanFiles | Select-Object -Unique)) {
        if (-not (Test-Path -LiteralPath $path)) {
            continue
        }
        if ((Get-Item -LiteralPath $path).Length -gt 16777216) {
            return 'oversized'
        }
        $text = [string](Get-Content -LiteralPath $path -Raw -Encoding UTF8)
        if (Test-EmployeeLiveSensitiveText -Text $text -LiteralSensitiveValues @(
                $sentinel, [Uri]::EscapeDataString($sentinel), $fullPath
            ) -ExpectedPrincipals @()) {
            return 'sentinel'
        }
        if (Test-EmployeeLiveSensitiveText -Text $text -LiteralSensitiveValues @($token) -ExpectedPrincipals @()) {
            return 'jwt'
        }
        if (Test-EmployeeLiveSensitiveText -Text $text -LiteralSensitiveValues @(
                $secret, $subject
            ) -ExpectedPrincipals @()) {
            return 'secret-or-subject'
        }
    }
    return $null
}

function Get-SafeFailureCode {
    $text = ''
    foreach ($path in @($mavenOut, $mavenErr, $gatewayOut, $gatewayErr)) {
        if ((Test-Path -LiteralPath $path) -and (Get-Item -LiteralPath $path).Length -le 16777216) {
            $text += [string](Get-Content -LiteralPath $path -Raw -Encoding UTF8)
        }
    }
    $match = [Regex]::Match($text, 'employee\.gateway_live_[a-z0-9_]+')
    if ($match.Success) {
        return $match.Value
    }
    return 'employee.gateway_live_integration_failed'
}

function Remove-GeneratedSurefireReports {
    if (-not $mavenStarted) {
        $script:surefireReportsDeleted = $true
        return
    }
    $resolved = [IO.Path]::GetFullPath($surefireReportDirectory)
    if (-not $resolved.StartsWith($runRoot + [IO.Path]::DirectorySeparatorChar,
            [StringComparison]::OrdinalIgnoreCase)) {
        throw 'employee.gateway_live_surefire_path_invalid'
    }
    if (Test-Path -LiteralPath $resolved) {
        Remove-Item -LiteralPath $resolved -Recurse -Force
    }
    $script:surefireReportsDeleted = -not (Test-Path -LiteralPath $resolved)
}

function Remove-RunRoot {
    if (-not (Test-Path -LiteralPath $runRoot)) {
        $script:runRootDeleted = $true
        return
    }
    $resolved = [IO.Path]::GetFullPath($runRoot)
    if (-not $resolved.StartsWith($tempRoot, [StringComparison]::OrdinalIgnoreCase) -or
            -not [IO.Path]::GetFileName($resolved).StartsWith('wp-emp-gateway-log-', [StringComparison]::Ordinal)) {
        throw 'employee.gateway_live_temp_path_invalid'
    }
    Remove-Item -LiteralPath $resolved -Recurse -Force
    $script:runRootDeleted = -not (Test-Path -LiteralPath $resolved)
}

try {
    $maven = (Get-Command mvn.cmd -ErrorAction Stop).Source
    $python = (Get-Command python.exe -ErrorAction Stop).Source
    $gatewayPort = Get-FreeTcpPort
    $token = New-GatewayTestJwt

    $buildExit = Invoke-CapturedProcess $maven @(
        '-f', 'serviceCenter/pom.xml', '-pl', ':gateway-service', '-am', '-DskipTests', 'package'
    ) $repository $buildOut $buildErr
    if ($buildExit -ne 0) {
        throw 'employee.gateway_live_gateway_build_failed'
    }
    $gatewayJar = Join-Path $repository 'gateway-service\target\gateway-service-0.0.1-SNAPSHOT.jar'
    if (-not (Test-Path -LiteralPath $gatewayJar)) {
        throw 'employee.gateway_live_gateway_jar_missing'
    }

    $env:COMMON_SECURITY_JWT_HMAC_KEY_ACTIVE = $secret
    $env:RUN_EMPLOYEE_GATEWAY_LOG_LIVE = '1'
    $env:EMPLOYEE_GATEWAY_LIVE_GATEWAY_JAR = $gatewayJar
    $env:EMPLOYEE_GATEWAY_LIVE_GATEWAY_PORT = [string]$gatewayPort
    $env:EMPLOYEE_GATEWAY_LIVE_GATEWAY_OUT_PATH = $gatewayOut
    $env:EMPLOYEE_GATEWAY_LIVE_GATEWAY_ERR_PATH = $gatewayErr
    $env:EMPLOYEE_GATEWAY_LIVE_JAVA_METRICS_PATH = $javaMetrics
    $env:EMPLOYEE_GATEWAY_LIVE_JWT = $token
    $env:EMPLOYEE_GATEWAY_LIVE_SENTINEL = $sentinel
    $env:EMPLOYEE_GATEWAY_LIVE_CORRELATION_ID = $correlationId

    $mavenStarted = $true
    $surefireReportsDeleted = $false
    $testExit = Invoke-CapturedProcess $maven @(
        '-f', 'serviceCenter/pom.xml', '-pl', ':employee-service', '-am',
        '-Dtest=com.dylan.employee.live.EmployeeGatewayLogSafetyLiveIntegrationTest',
        '-Dsurefire.failIfNoSpecifiedTests=false',
        "-Dsurefire.reportsDirectory=$surefireReportDirectory", 'test'
    ) $repository $mavenOut $mavenErr

    $leakCategory = Get-SensitiveLogCategory
    if ($null -ne $leakCategory) {
        throw 'employee.gateway_live_log_leak'
    }
    if ($testExit -ne 0) {
        throw (Get-SafeFailureCode)
    }
    if (-not (Test-Path -LiteralPath $javaMetrics)) {
        throw 'employee.gateway_live_metrics_missing'
    }
    $metrics = Get-Content -LiteralPath $javaMetrics -Raw -Encoding UTF8 | ConvertFrom-Json
    if ($metrics.gateway -ne $maxGatewayRequests -or $metrics.servlet -ne 1 -or
            $metrics.serviceDetail -ne 1 -or $metrics.mapperSelectByIdCardNo -ne 1 -or
            $metrics.otherServiceMethods -ne 0 -or $metrics.responseStatus -ne 400) {
        throw 'employee.gateway_live_call_count_invalid'
    }

    Remove-GeneratedSurefireReports
    Remove-RunRoot
    if (-not $runRootDeleted -or -not $surefireReportsDeleted) {
        throw 'employee.gateway_live_raw_log_delete_failed'
    }

    $completed = [DateTimeOffset]::UtcNow
    $evidence = [ordered]@{
        schemaVersion = 1
        workPackage = 'WP-EMP-REAL-01'
        validation = 'VAL-EMP-005'
        status = 'passed'
        startedAtUtc = $started.ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ss.fffZ')
        completedAtUtc = $completed.ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ss.fffZ')
        durationMs = [Math]::Max(0, [int64]($completed - $started).TotalMilliseconds)
        requestCounts = [ordered]@{
            gateway = 1
            servlet = 1
            serviceDetail = 1
            mapperSelectByIdCardNo = 1
            otherServiceMethods = 0
        }
        responseStatus = 400
        logSafety = [ordered]@{
            logLeakCount = 0
            rawLogsDeleted = $true
            sentinelPersisted = $false
            jwtPersisted = $false
            hmacKeyPersisted = $false
            fullPathPersisted = $false
        }
        runtimeIsolation = [ordered]@{
            gatewayService = 'actual_jar_test_route'
            employeeService = 'spring_boot_test_servlet'
            permanentEmployeeRoute = $false
            realEmployeeIdentifierUsed = $false
            deepSeekCalled = $false
        }
    }
    $json = $evidence | ConvertTo-Json -Depth 8 -Compress
    foreach ($sensitive in @($sentinel, $token, $secret, $subject, $fullPath)) {
        if ($sensitive -and $json.Contains([string]$sensitive)) {
            throw 'employee.gateway_live_evidence_leak'
        }
    }

    $targetDirectory = [IO.Path]::GetFullPath((Join-Path $repository $EvidenceDirectory))
    $expectedDirectory = [IO.Path]::GetFullPath((Join-Path $repository 'agent-runtime\tests\integration\adapters\employee\evidence'))
    if ($targetDirectory -ne $expectedDirectory) {
        throw 'employee.gateway_live_evidence_directory_invalid'
    }
    New-Item -ItemType Directory -Path $targetDirectory -Force | Out-Null
    $stamp = $started.ToUniversalTime().ToString('yyyyMMddTHHmmssZ')
    $finalPath = Join-Path $targetDirectory "wp-emp-gateway-log-$stamp.json"
    $temporaryEvidence = "$finalPath.tmp"
    [IO.File]::WriteAllText($temporaryEvidence, $json, [Text.UTF8Encoding]::new($false))
    & $python (Join-Path $repository 'agent-runtime\tests\integration\adapters\employee\evidence_contract.py') $temporaryEvidence
    if ($LASTEXITCODE -ne 0) {
        Remove-Item -LiteralPath $temporaryEvidence -Force -ErrorAction SilentlyContinue
        throw 'employee.gateway_live_evidence_schema_invalid'
    }
    Move-Item -LiteralPath $temporaryEvidence -Destination $finalPath
    [pscustomobject]@{
        status = 'passed'
        gatewayRequests = 1
        servletRequests = 1
        logLeakCount = 0
        rawLogsDeleted = $true
        evidence = $finalPath
    }
} finally {
    $cleanupFailed = $false
    if (Test-Path -LiteralPath $runRoot) {
        try {
            Remove-RunRoot
        } catch {
            $cleanupFailed = $true
        }
    }
    if (-not $surefireReportsDeleted) {
        try {
            Remove-GeneratedSurefireReports
        } catch {
            $cleanupFailed = $true
        }
    }
    foreach ($name in $environmentNames) {
        $previous = $environmentSnapshot[$name]
        if ($null -eq $previous) {
            Remove-Item "Env:\$name" -ErrorAction SilentlyContinue
        } else {
            [Environment]::SetEnvironmentVariable($name, [string]$previous, 'Process')
        }
    }
    if ($null -ne $keySeed) {
        [Array]::Clear($keySeed, 0, $keySeed.Length)
    }
    $secret = $null
    $token = $null
    $sentinel = $null
    $subject = $null
    if ($cleanupFailed) {
        throw 'employee.gateway_live_cleanup_failed'
    }
}
