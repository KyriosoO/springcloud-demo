[CmdletBinding()]
param(
    [string]$RepositoryRoot = (Split-Path -Parent (Split-Path -Parent $PSScriptRoot)),
    [string]$EvidenceDirectory = 'agent-runtime/tests/integration/adapters/employee/evidence'
)

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'employee-live-log-safety.ps1')
$repository = [IO.Path]::GetFullPath($RepositoryRoot)
if ($repository -ne 'D:\codex') {
    throw 'employee.live_repository_invalid'
}
$identifier = [Environment]::GetEnvironmentVariable('EMPLOYEE_LIVE_TEST_IDENTIFIER', 'Process')
if ([string]::IsNullOrWhiteSpace($identifier)) {
    throw 'employee.live_identifier_missing'
}
$identifier = $identifier.Trim().Normalize([Text.NormalizationForm]::FormC)
$forbiddenBidi = @(0x202A, 0x202B, 0x202C, 0x202D, 0x202E, 0x2066, 0x2067, 0x2068, 0x2069)
$hasForbiddenCharacter = $false
foreach ($character in $identifier.ToCharArray()) {
    if ([char]::IsWhiteSpace($character) -or [char]::IsControl($character) -or
            $forbiddenBidi -contains [int]$character) {
        $hasForbiddenCharacter = $true
        break
    }
}
if ($identifier.Length -lt 5 -or $identifier.Length -gt 64 -or
        [Text.Encoding]::UTF8.GetByteCount($identifier) -gt 192 -or
        $identifier.IndexOfAny([char[]]@('/', '\', '%', '?', '#')) -ge 0 -or
        $hasForbiddenCharacter) {
    throw 'employee.live_identifier_invalid'
}

$maxEmployeeRequests = 10
$requiredPorts = 8090
$occupied = Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue |
    Where-Object { $requiredPorts -contains $_.LocalPort }
if ($occupied) {
    throw 'employee.live_port_occupied'
}

$environmentNames = @(
    'COMMON_SECURITY_JWT_HMAC_KEY_ACTIVE',
    'RUN_EMPLOYEE_LIVE',
    'EMPLOYEE_LIVE_ADMIN_JWT',
    'EMPLOYEE_LIVE_DYLAN_JWT',
    'EMPLOYEE_LIVE_VIEWER_JWT',
    'EMPLOYEE_LIVE_UNKNOWN_ROLE_JWT',
    'EMPLOYEE_LIVE_MALFORMED_JWT',
    'EMPLOYEE_LIVE_SERVICE_JWT',
    'EMPLOYEE_LIVE_REPOSITORY_ROOT',
    'EMPLOYEE_LIVE_PROBE_EVIDENCE_PATH',
    'EMPLOYEE_LIVE_JAVA_METRICS_PATH',
    'EMPLOYEE_LIVE_PYTHON_LOG_PATH',
    'EMPLOYEE_LIVE_PYTHON_JUNIT_PATH',
    'EMPLOYEE_LIVE_PYTHON_EXECUTABLE'
)
$environmentSnapshot = @{}
foreach ($name in $environmentNames) {
    $environmentSnapshot[$name] = [Environment]::GetEnvironmentVariable($name, 'Process')
}

$tempRoot = [IO.Path]::GetFullPath([IO.Path]::GetTempPath())
$runRoot = [IO.Path]::GetFullPath((Join-Path $tempRoot "wp-emp-real-01-$([Guid]::NewGuid().ToString('N'))"))
if (-not $runRoot.StartsWith($tempRoot, [StringComparison]::OrdinalIgnoreCase) -or
        -not [IO.Path]::GetFileName($runRoot).StartsWith('wp-emp-real-01-', [StringComparison]::Ordinal)) {
    throw 'employee.live_temp_path_invalid'
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
$probeEvidence = Join-Path $runRoot 'probe-evidence.json'
$javaMetrics = Join-Path $runRoot 'java-metrics.json'
$logFiles = @($authOut, $authErr, $buildOut, $buildErr, $mavenOut, $mavenErr, $pythonLog, $pythonJunit)
$surefireReportDirectory = [IO.Path]::GetFullPath((Join-Path $repository 'employee-service\target\surefire-reports'))
$surefireReportFiles = @(
    (Join-Path $surefireReportDirectory 'TEST-com.dylan.employee.live.EmployeeRealActionLiveIntegrationTest.xml'),
    (Join-Path $surefireReportDirectory 'com.dylan.employee.live.EmployeeRealActionLiveIntegrationTest.txt')
)

$keyBytes = [Security.Cryptography.RandomNumberGenerator]::GetBytes(48)
$secret = [Convert]::ToBase64String($keyBytes)
$adminToken = $null
$dylanToken = $null
$viewerToken = $null
$unknownToken = $null
$serviceToken = $null
$malformedToken = "malformed-$([Guid]::NewGuid().ToString('N'))"
$adminPassword = $null
$dylanPassword = $null
$viewerPassword = $null
$authProcess = $null
$logLeakDetected = $false
$logLeakCategory = $null
$integrationFailureCode = $null
$runRootDeleted = $false
$employeeMavenStarted = $false
$surefireReportsDeleted = $true
$started = [DateTimeOffset]::UtcNow

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

function Wait-Ready([string]$Uri, [Diagnostics.Process]$Process) {
    for ($attempt = 0; $attempt -lt 90; $attempt++) {
        if ($Process.HasExited) {
            throw 'employee.live_auth_process_exited'
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
    throw 'employee.live_auth_readiness_timeout'
}

function Get-LocalPassword([string]$User) {
    $path = Join-Path $repository 'auth-service\src\main\resources\auth-users.yml'
    $text = Get-Content -LiteralPath $path -Raw -Encoding UTF8
    $match = [regex]::Match($text, "(?ms)^\s{4}${User}:\s*\r?\n\s+password:\s*([^\r\n]+)")
    if (-not $match.Success) {
        throw 'employee.live_auth_fixture_missing'
    }
    $stored = $match.Groups[1].Value.Trim().Trim('"').Trim("'")
    if (-not $stored.StartsWith('{noop}')) {
        throw 'employee.live_auth_fixture_not_local'
    }
    return $stored.Substring(6)
}

function Get-LoginToken([string]$User, [string]$Password) {
    $session = [Microsoft.PowerShell.Commands.WebRequestSession]::new()
    $body = @{ userId = $User; password = $Password } | ConvertTo-Json -Compress
    $response = Invoke-WebRequest -Uri 'http://127.0.0.1:8090/login' -Method Post `
        -ContentType 'application/json' -Body $body -WebSession $session -TimeoutSec 5 -SkipHttpErrorCheck
    if ($response.StatusCode -ne 200) {
        throw 'employee.live_login_failed'
    }
    $cookie = $session.Cookies.GetCookies('http://127.0.0.1:8090')['AUTH_TOKEN']
    if ($null -eq $cookie -or [string]::IsNullOrWhiteSpace($cookie.Value)) {
        throw 'employee.live_token_missing'
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

function Get-SensitiveLogCategory {
    $expectedPrincipals = @('admin', 'dylan', 'viewer_t')
    $scanFiles = @($logFiles)
    if ($employeeMavenStarted) {
        $scanFiles += $surefireReportFiles
    }
    foreach ($path in $scanFiles) {
        if (-not (Test-Path -LiteralPath $path)) {
            continue
        }
        if ((Get-Item -LiteralPath $path).Length -gt 8388608) {
            return 'oversized'
        }
        $text = [string](Get-Content -LiteralPath $path -Raw -Encoding UTF8)
        if (Test-EmployeeLiveSensitiveText -Text $text -LiteralSensitiveValues @(
                $identifier, [Uri]::EscapeDataString($identifier)
            ) -ExpectedPrincipals @()) {
            return 'identifier'
        }
        if (Test-EmployeeLiveSensitiveText -Text $text -LiteralSensitiveValues @(
                $adminToken, $dylanToken, $viewerToken, $unknownToken, $serviceToken, $malformedToken
            ) -ExpectedPrincipals @()) {
            return 'jwt'
        }
        if (Test-EmployeeLiveSensitiveText -Text $text -LiteralSensitiveValues @($secret) -ExpectedPrincipals @()) {
            return 'hmac'
        }
        if (Test-EmployeeLiveSensitiveText -Text $text -LiteralSensitiveValues @(
                $adminPassword, $dylanPassword, $viewerPassword
            ) -ExpectedPrincipals @()) {
            return 'credential'
        }
        $principalText = if ($path -eq $pythonJunit -or $path -eq $surefireReportFiles[0]) {
            Remove-EmployeeLiveJUnitHostMetadata -Text $text
        } else {
            $text
        }
        if (Test-EmployeeLiveSensitiveText -Text $principalText `
                -LiteralSensitiveValues @() -ExpectedPrincipals $expectedPrincipals) {
            return 'principal'
        }
    }
    return $null
}

function Test-SensitiveLogValue {
    $script:logLeakCategory = Get-SensitiveLogCategory
    return $null -ne $script:logLeakCategory
}

function Stop-IsolatedAuth {
    if ($null -ne $script:authProcess -and -not $script:authProcess.HasExited) {
        Stop-Process -Id $script:authProcess.Id -ErrorAction SilentlyContinue
        if (-not $script:authProcess.WaitForExit(5000)) {
            Stop-Process -Id $script:authProcess.Id -Force -ErrorAction SilentlyContinue
        }
    }
}

function Remove-RunRoot {
    if (-not (Test-Path -LiteralPath $runRoot)) {
        $script:runRootDeleted = $true
        return
    }
    $resolved = [IO.Path]::GetFullPath($runRoot)
    if (-not $resolved.StartsWith($tempRoot, [StringComparison]::OrdinalIgnoreCase) -or
            -not [IO.Path]::GetFileName($resolved).StartsWith('wp-emp-real-01-', [StringComparison]::Ordinal)) {
        throw 'employee.live_temp_path_invalid'
    }
    Remove-Item -LiteralPath $resolved -Recurse -Force
    $script:runRootDeleted = -not (Test-Path -LiteralPath $resolved)
}

function Remove-GeneratedSurefireReports {
    if (-not $employeeMavenStarted) {
        $script:surefireReportsDeleted = $true
        return
    }
    foreach ($path in $surefireReportFiles) {
        $resolved = [IO.Path]::GetFullPath($path)
        if (-not $resolved.StartsWith($surefireReportDirectory + [IO.Path]::DirectorySeparatorChar,
                [StringComparison]::OrdinalIgnoreCase)) {
            throw 'employee.live_surefire_path_invalid'
        }
        if (Test-Path -LiteralPath $resolved) {
            Remove-Item -LiteralPath $resolved -Force
        }
    }
    $script:surefireReportsDeleted = -not ($surefireReportFiles | Where-Object { Test-Path -LiteralPath $_ })
}

try {
    $maven = (Get-Command mvn.cmd -ErrorAction Stop).Source
    $python = (Get-Command python.exe -ErrorAction Stop).Source
    $buildExit = Invoke-CapturedProcess $maven @(
        '-f', 'serviceCenter/pom.xml', '-pl', ':auth-service', '-am', '-DskipTests', 'package'
    ) $repository $buildOut $buildErr
    if ($buildExit -ne 0) {
        throw 'employee.live_auth_build_failed'
    }

    $env:COMMON_SECURITY_JWT_HMAC_KEY_ACTIVE = $secret
    $commonArgs = @(
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
        throw 'employee.live_auth_jar_missing'
    }
    $authProcess = Start-Process -FilePath 'java' -ArgumentList (@('-jar', $authJar) + $commonArgs) `
        -WorkingDirectory (Join-Path $repository 'auth-service') -WindowStyle Hidden -PassThru `
        -RedirectStandardOutput $authOut -RedirectStandardError $authErr
    Wait-Ready 'http://127.0.0.1:8090/public/test' $authProcess

    $adminPassword = Get-LocalPassword 'admin'
    $dylanPassword = Get-LocalPassword 'dylan'
    $viewerPassword = Get-LocalPassword 'viewer_t'
    $adminToken = Get-LoginToken 'admin' $adminPassword
    $dylanToken = Get-LoginToken 'dylan' $dylanPassword
    $viewerToken = Get-LoginToken 'viewer_t' $viewerPassword
    $unknownToken = New-TestJwt 'employee-live-unknown' 'user' @('UNKNOWN')
    $serviceToken = New-TestJwt 'employee-live-service' 'service' @('ADMIN')

    $env:RUN_EMPLOYEE_LIVE = '1'
    $env:EMPLOYEE_LIVE_ADMIN_JWT = $adminToken
    $env:EMPLOYEE_LIVE_DYLAN_JWT = $dylanToken
    $env:EMPLOYEE_LIVE_VIEWER_JWT = $viewerToken
    $env:EMPLOYEE_LIVE_UNKNOWN_ROLE_JWT = $unknownToken
    $env:EMPLOYEE_LIVE_MALFORMED_JWT = $malformedToken
    $env:EMPLOYEE_LIVE_SERVICE_JWT = $serviceToken
    $env:EMPLOYEE_LIVE_REPOSITORY_ROOT = $repository
    $env:EMPLOYEE_LIVE_PROBE_EVIDENCE_PATH = $probeEvidence
    $env:EMPLOYEE_LIVE_JAVA_METRICS_PATH = $javaMetrics
    $env:EMPLOYEE_LIVE_PYTHON_LOG_PATH = $pythonLog
    $env:EMPLOYEE_LIVE_PYTHON_JUNIT_PATH = $pythonJunit
    $env:EMPLOYEE_LIVE_PYTHON_EXECUTABLE = $python

    $employeeMavenStarted = $true
    $surefireReportsDeleted = $false
    $testExit = Invoke-CapturedProcess $maven @(
        '-f', 'serviceCenter/pom.xml', '-pl', ':employee-service', '-am',
        '-Dtest=com.dylan.employee.live.EmployeeRealActionLiveIntegrationTest',
        '-Dsurefire.failIfNoSpecifiedTests=false', 'test'
    ) $repository $mavenOut $mavenErr
    Stop-IsolatedAuth
    if ($testExit -ne 0) {
        $pythonFailureText = ''
        foreach ($failurePath in @($pythonLog, $pythonJunit)) {
            if ((Test-Path -LiteralPath $failurePath) -and
                    (Get-Item -LiteralPath $failurePath).Length -le 8388608) {
                $pythonFailureText += [string](Get-Content -LiteralPath $failurePath -Raw -Encoding UTF8)
            }
        }
        $integrationFailureCode = Get-EmployeeLiveSafeFailureCode -Text $pythonFailureText
        throw $integrationFailureCode
    }
    if (-not (Test-Path -LiteralPath $probeEvidence) -or -not (Test-Path -LiteralPath $javaMetrics)) {
        throw 'employee.live_metrics_missing'
    }

    $probe = Get-Content -LiteralPath $probeEvidence -Raw -Encoding UTF8 | ConvertFrom-Json
    $metrics = Get-Content -LiteralPath $javaMetrics -Raw -Encoding UTF8 | ConvertFrom-Json
    if ($probe.requestCounts.employee -gt $maxEmployeeRequests -or
            $probe.requestCounts.employee -ne 7 -or $probe.requestCounts.adapter -ne 6 -or
            $metrics.serviceDetail -ne 3 -or $metrics.mapperSelectByIdCardNo -ne 3 -or
            $metrics.otherServiceMethods -ne 0) {
        throw 'employee.live_call_count_invalid'
    }
    $logLeakDetected = Test-SensitiveLogValue
    if ($logLeakDetected) {
        throw 'employee.live_log_leak'
    }

    $completed = [DateTimeOffset]::UtcNow
    $evidence = [ordered]@{
        schemaVersion = 1
        workPackage = 'WP-EMP-REAL-01'
        status = 'passed'
        startedAtUtc = $started.ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ss.fffZ')
        completedAtUtc = $completed.ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ss.fffZ')
        durationMs = [Math]::Max(0, [int64]($completed - $started).TotalMilliseconds)
        authorizationMatrix = [ordered]@{
            adminPrimary = [string]$probe.authorizationMatrix.adminPrimary
            adminSecondary = [string]$probe.authorizationMatrix.adminSecondary
            viewer = [string]$probe.authorizationMatrix.viewer
            unknownRole = [string]$probe.authorizationMatrix.unknownRole
            missingToken = [string]$probe.authorizationMatrix.missingToken
            malformedToken = [string]$probe.authorizationMatrix.malformedToken
            serviceToken = [string]$probe.authorizationMatrix.serviceToken
        }
        requestCounts = [ordered]@{
            employee = [int]$probe.requestCounts.employee
            adapter = [int]$probe.requestCounts.adapter
            serviceDetail = [int]$metrics.serviceDetail
            mapperSelectByIdCardNo = [int]$metrics.mapperSelectByIdCardNo
            otherServiceMethods = [int]$metrics.otherServiceMethods
            otherEmployeeEndpoints = [int]$probe.requestCounts.otherEmployeeEndpoints
            model = [int]$probe.requestCounts.model
        }
        responseVisibility = [string]$probe.responseVisibility
        logSafety = [ordered]@{
            logLeakCount = 0
            rawLogsDeleted = $true
            identifierPersisted = $false
            jwtPersisted = $false
            hmacKeyPersisted = $false
        }
        runtimeIsolation = [ordered]@{
            authService = 'isolated_local'
            employeeService = 'spring_boot_test'
            gatewayStarted = $false
            esCalled = $false
            workflowCalled = $false
            deepSeekCalled = $false
        }
    }
    $json = $evidence | ConvertTo-Json -Depth 8 -Compress
    foreach ($sensitive in @($identifier, $secret, $adminToken, $dylanToken, $viewerToken, $unknownToken, $serviceToken, $malformedToken)) {
        if ($sensitive -and $json.Contains([string]$sensitive)) {
            throw 'employee.live_evidence_leak'
        }
    }

    Remove-GeneratedSurefireReports
    Remove-RunRoot
    if (-not $runRootDeleted -or -not $surefireReportsDeleted) {
        throw 'employee.live_raw_log_delete_failed'
    }
    $targetDirectory = [IO.Path]::GetFullPath((Join-Path $repository $EvidenceDirectory))
    $expectedDirectory = [IO.Path]::GetFullPath((Join-Path $repository 'agent-runtime\tests\integration\adapters\employee\evidence'))
    if ($targetDirectory -ne $expectedDirectory) {
        throw 'employee.live_evidence_directory_invalid'
    }
    New-Item -ItemType Directory -Path $targetDirectory -Force | Out-Null
    $stamp = $started.ToUniversalTime().ToString('yyyyMMddTHHmmssZ')
    $finalPath = Join-Path $targetDirectory "wp-emp-real-01-$stamp.json"
    $temporaryEvidence = "$finalPath.tmp"
    [IO.File]::WriteAllText($temporaryEvidence, $json, [Text.UTF8Encoding]::new($false))
    & $python (Join-Path $repository 'agent-runtime\tests\integration\adapters\employee\evidence_contract.py') $temporaryEvidence
    if ($LASTEXITCODE -ne 0) {
        Remove-Item -LiteralPath $temporaryEvidence -Force -ErrorAction SilentlyContinue
        throw 'employee.live_evidence_schema_invalid'
    }
    Move-Item -LiteralPath $temporaryEvidence -Destination $finalPath
    [pscustomobject]@{ status = 'passed'; employeeRequests = 7; logLeakCount = 0; evidence = $finalPath }
} finally {
    $cleanupFailed = $false
    try {
        Stop-IsolatedAuth
    } catch {
        $cleanupFailed = $true
    }
    if (Test-Path -LiteralPath $runRoot) {
        try {
            $logLeakDetected = $logLeakDetected -or (Test-SensitiveLogValue)
        } catch {
            $logLeakDetected = $true
        }
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
    [Array]::Clear($keyBytes, 0, $keyBytes.Length)
    $secret = $null
    $identifier = $null
    $adminToken = $null
    $dylanToken = $null
    $viewerToken = $null
    $unknownToken = $null
    $serviceToken = $null
    $malformedToken = $null
    $adminPassword = $null
    $dylanPassword = $null
    $viewerPassword = $null
    foreach ($name in $environmentNames) {
        [Environment]::SetEnvironmentVariable($name, $environmentSnapshot[$name], 'Process')
    }
    if ($cleanupFailed -or -not $runRootDeleted -or -not $surefireReportsDeleted) {
        throw 'employee.live_cleanup_failed'
    }
    if ($logLeakDetected) {
        if ([string]::IsNullOrWhiteSpace($logLeakCategory)) {
            $logLeakCategory = 'unknown'
        }
        if ([string]::IsNullOrWhiteSpace($integrationFailureCode)) {
            throw "employee.live_log_leak:$logLeakCategory"
        }
        throw "employee.live_log_leak:$logLeakCategory`:$integrationFailureCode"
    }
}
