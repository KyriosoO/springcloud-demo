[CmdletBinding()]
param(
    [string]$RepositoryRoot = (Split-Path -Parent (Split-Path -Parent $PSScriptRoot)),
    [string]$EvidenceDirectory = 'agent-runtime/tests/integration/adapters/transaction/evidence'
)

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'transaction-live-log-safety.ps1')

$repository = [IO.Path]::GetFullPath($RepositoryRoot)
if ($repository -ne 'D:\codex') {
    throw 'transaction.live_repository_invalid'
}

$maxTransactionRequests = 8
$maxGatewayRequests = 1
$environmentNames = @(
    'COMMON_SECURITY_JWT_HMAC_KEY_ACTIVE',
    'RUN_TRANSACTION_LIVE',
    'TRANSACTION_LIVE_ADMIN_JWT',
    'TRANSACTION_LIVE_DYLAN_JWT',
    'TRANSACTION_LIVE_VIEWER_JWT',
    'TRANSACTION_LIVE_UNKNOWN_ROLE_JWT',
    'TRANSACTION_LIVE_MALFORMED_JWT',
    'TRANSACTION_LIVE_SERVICE_JWT',
    'TRANSACTION_LIVE_REPOSITORY_ROOT',
    'TRANSACTION_LIVE_PROBE_EVIDENCE_PATH',
    'TRANSACTION_LIVE_JAVA_METRICS_PATH',
    'TRANSACTION_LIVE_PYTHON_LOG_PATH',
    'TRANSACTION_LIVE_PYTHON_JUNIT_PATH',
    'TRANSACTION_LIVE_PYTHON_EXECUTABLE',
    'TRANSACTION_LIVE_SENTINEL',
    'TRANSACTION_LIVE_GATEWAY_SENTINEL',
    'TRANSACTION_LIVE_CORRELATION_ID',
    'TRANSACTION_LIVE_GATEWAY_JAR',
    'TRANSACTION_LIVE_GATEWAY_PORT',
    'TRANSACTION_LIVE_GATEWAY_OUT_PATH',
    'TRANSACTION_LIVE_GATEWAY_ERR_PATH'
)
$environmentSnapshot = @{}
foreach ($name in $environmentNames) {
    $environmentSnapshot[$name] = [Environment]::GetEnvironmentVariable($name, 'Process')
}

$tempRoot = [IO.Path]::GetFullPath([IO.Path]::GetTempPath())
$runRoot = [IO.Path]::GetFullPath((Join-Path $tempRoot "wp-txn-real-01-$([Guid]::NewGuid().ToString('N'))"))
if (-not $runRoot.StartsWith($tempRoot, [StringComparison]::OrdinalIgnoreCase) -or
        -not [IO.Path]::GetFileName($runRoot).StartsWith('wp-txn-real-01-', [StringComparison]::Ordinal)) {
    throw 'transaction.live_temp_path_invalid'
}
New-Item -ItemType Directory -Path $runRoot | Out-Null

$buildOut = Join-Path $runRoot 'build.out.log'
$buildErr = Join-Path $runRoot 'build.err.log'
$authOut = Join-Path $runRoot 'auth.out.log'
$authErr = Join-Path $runRoot 'auth.err.log'
$mavenOut = Join-Path $runRoot 'transaction-test.out.log'
$mavenErr = Join-Path $runRoot 'transaction-test.err.log'
$pythonLog = Join-Path $runRoot 'python-probe.log'
$pythonJunit = Join-Path $runRoot 'python-junit.xml'
$gatewayOut = Join-Path $runRoot 'gateway.out.log'
$gatewayErr = Join-Path $runRoot 'gateway.err.log'
$probeEvidence = Join-Path $runRoot 'probe-evidence.json'
$javaMetrics = Join-Path $runRoot 'java-metrics.json'
$surefireReportDirectory = [IO.Path]::GetFullPath((Join-Path $runRoot 'surefire-reports'))
$logFiles = @(
    $buildOut, $buildErr, $authOut, $authErr, $mavenOut, $mavenErr,
    $pythonLog, $pythonJunit, $gatewayOut, $gatewayErr, $probeEvidence, $javaMetrics
)

$keyBytes = [Security.Cryptography.RandomNumberGenerator]::GetBytes(48)
$secret = [Convert]::ToBase64String($keyBytes)
$sentinel = "SYNTHETIC-TRANSACTION-DIRECT-$([Guid]::NewGuid().ToString('N'))"
$gatewaySentinel = "SYNTHETIC-TRANSACTION-GATEWAY-$([Guid]::NewGuid().ToString('N'))"
$correlationId = "transaction-live-$([Guid]::NewGuid().ToString('N'))"
$amountValues = @('0.01', '-9999999999999999.99', '9999999999999999.99')
$gatewayRequestBody = "{`"condition`":{`"transId`":`"$gatewaySentinel`",`"amount`":0.01},`"page`":1,`"size`":20,`"sorts`":[]}"
$malformedToken = 'malformed.transaction.token'
$authProcess = $null
$adminToken = $null
$dylanToken = $null
$viewerToken = $null
$unknownToken = $null
$serviceToken = $null
$adminPassword = $null
$dylanPassword = $null
$viewerPassword = $null
$runRootDeleted = $false
$surefireReportsDeleted = $true
$mavenStarted = $false
$logLeakDetected = $false
$logLeakCategory = $null
$integrationFailureCode = $null
$started = [DateTimeOffset]::UtcNow

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

function Wait-Ready([string]$Uri, [Diagnostics.Process]$Process) {
    for ($attempt = 0; $attempt -lt 120; $attempt++) {
        if ($Process.HasExited) {
            throw 'transaction.live_auth_process_exited'
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
    throw 'transaction.live_auth_readiness_timeout'
}

function Get-LocalPassword([string]$User) {
    $path = Join-Path $repository 'auth-service\src\main\resources\auth-users.yml'
    $text = Get-Content -LiteralPath $path -Raw -Encoding UTF8
    $match = [regex]::Match($text, "(?ms)^\s{4}${User}:\s*\r?\n\s+password:\s*([^\r\n]+)")
    if (-not $match.Success) {
        throw 'transaction.live_auth_fixture_missing'
    }
    $stored = $match.Groups[1].Value.Trim().Trim('"').Trim("'")
    if (-not $stored.StartsWith('{noop}')) {
        throw 'transaction.live_auth_fixture_not_local'
    }
    return $stored.Substring(6)
}

function Get-LoginToken([string]$BaseUrl, [string]$User, [string]$Password) {
    $session = [Microsoft.PowerShell.Commands.WebRequestSession]::new()
    $body = @{ userId = $User; password = $Password } | ConvertTo-Json -Compress
    $response = Invoke-WebRequest -Uri "$BaseUrl/login" -Method Post `
        -ContentType 'application/json' -Body $body -WebSession $session -TimeoutSec 5 -SkipHttpErrorCheck
    if ($response.StatusCode -ne 200) {
        throw 'transaction.live_login_failed'
    }
    $cookie = $session.Cookies.GetCookies($BaseUrl)['AUTH_TOKEN']
    if ($null -eq $cookie -or [string]::IsNullOrWhiteSpace($cookie.Value)) {
        throw 'transaction.live_token_missing'
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
        if (Test-TransactionLiveSensitiveText -Text $text -LiteralSensitiveValues @(
                $sentinel, [Uri]::EscapeDataString($sentinel),
                $gatewaySentinel, [Uri]::EscapeDataString($gatewaySentinel)
            ) -ExpectedPrincipals @()) {
            return 'transaction-value'
        }
        if (Test-TransactionLiveSensitiveText -Text $text -LiteralSensitiveValues $amountValues -ExpectedPrincipals @()) {
            return 'amount'
        }
        if (Test-TransactionLiveSensitiveText -Text $text -LiteralSensitiveValues @($gatewayRequestBody) -ExpectedPrincipals @()) {
            return 'body'
        }
        if (Test-TransactionLiveSensitiveText -Text $text -LiteralSensitiveValues @(
                $adminToken, $dylanToken, $viewerToken, $unknownToken, $serviceToken, $malformedToken
            ) -ExpectedPrincipals @()) {
            return 'jwt'
        }
        if (Test-TransactionLiveSensitiveText -Text $text -LiteralSensitiveValues @($secret) -ExpectedPrincipals @()) {
            return 'hmac'
        }
        if (Test-TransactionLiveSensitiveText -Text $text -LiteralSensitiveValues @(
                $adminPassword, $dylanPassword, $viewerPassword
            ) -ExpectedPrincipals @()) {
            return 'credential'
        }
        $principalText = if ($path -eq $pythonJunit -or $path.StartsWith($surefireReportDirectory)) {
            Remove-TransactionLiveJUnitHostMetadata -Text $text
        } else {
            $text
        }
        if (Test-TransactionLiveSensitiveText -Text $principalText -LiteralSensitiveValues @() `
                -ExpectedPrincipals @('admin', 'dylan', 'viewer_t')) {
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

function Remove-GeneratedSurefireReports {
    if (-not $mavenStarted) {
        $script:surefireReportsDeleted = $true
        return
    }
    $resolved = [IO.Path]::GetFullPath($surefireReportDirectory)
    if (-not $resolved.StartsWith($runRoot + [IO.Path]::DirectorySeparatorChar,
            [StringComparison]::OrdinalIgnoreCase)) {
        throw 'transaction.live_surefire_path_invalid'
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
            -not [IO.Path]::GetFileName($resolved).StartsWith('wp-txn-real-01-', [StringComparison]::Ordinal)) {
        throw 'transaction.live_temp_path_invalid'
    }
    Remove-Item -LiteralPath $resolved -Recurse -Force
    $script:runRootDeleted = -not (Test-Path -LiteralPath $resolved)
}

try {
    $maven = (Get-Command mvn.cmd -ErrorAction Stop).Source
    $python = (Get-Command python.exe -ErrorAction Stop).Source
    $authPort = Get-FreeTcpPort
    $gatewayPort = Get-FreeTcpPort

    $buildExit = Invoke-CapturedProcess $maven @(
        '-f', 'serviceCenter/pom.xml', '-pl', ':auth-service,:gateway-service', '-am', '-DskipTests', 'package'
    ) $repository $buildOut $buildErr
    if ($buildExit -ne 0) {
        throw 'transaction.live_auth_build_failed'
    }
    $authJar = Join-Path $repository 'auth-service\target\auth-service-0.0.1-SNAPSHOT.jar'
    $gatewayJar = Join-Path $repository 'gateway-service\target\gateway-service-0.0.1-SNAPSHOT.jar'
    if (-not (Test-Path -LiteralPath $authJar)) {
        throw 'transaction.live_auth_jar_missing'
    }
    if (-not (Test-Path -LiteralPath $gatewayJar)) {
        throw 'transaction.live_gateway_jar_missing'
    }

    $env:COMMON_SECURITY_JWT_HMAC_KEY_ACTIVE = $secret
    $commonArgs = @(
        "--server.port=$authPort",
        '--spring.main.banner-mode=off',
        '--spring.cloud.config.enabled=false',
        '--spring.config.import=',
        '--eureka.client.enabled=false',
        '--management.endpoints.enabled-by-default=false',
        '--common.security.secrets.source-order[0]=environment',
        '--common.security.secrets.allow-config-values=false',
        '--common.security.secrets.fail-fast=true',
        '--common.security.secrets.jwt.active-key-id=ACTIVE',
        '--common.security.secrets.jwt.keys.ACTIVE.env=COMMON_SECURITY_JWT_HMAC_KEY_ACTIVE',
        '--common.security.secrets.jwt.keys.ACTIVE.value='
    )
    $authProcess = Start-Process -FilePath 'java' -ArgumentList (@('-jar', $authJar) + $commonArgs) `
        -WorkingDirectory (Join-Path $repository 'auth-service') -WindowStyle Hidden -PassThru `
        -RedirectStandardOutput $authOut -RedirectStandardError $authErr
    $authBaseUrl = "http://127.0.0.1:$authPort"
    Wait-Ready "$authBaseUrl/public/test" $authProcess

    $adminPassword = Get-LocalPassword 'admin'
    $dylanPassword = Get-LocalPassword 'dylan'
    $viewerPassword = Get-LocalPassword 'viewer_t'
    $adminToken = Get-LoginToken $authBaseUrl 'admin' $adminPassword
    $dylanToken = Get-LoginToken $authBaseUrl 'dylan' $dylanPassword
    $viewerToken = Get-LoginToken $authBaseUrl 'viewer_t' $viewerPassword
    $unknownToken = New-TestJwt 'transaction-live-unknown' 'user' @('UNKNOWN')
    $serviceToken = New-TestJwt 'transaction-live-service' 'service' @('ADMIN')

    $env:RUN_TRANSACTION_LIVE = '1'
    $env:TRANSACTION_LIVE_ADMIN_JWT = $adminToken
    $env:TRANSACTION_LIVE_DYLAN_JWT = $dylanToken
    $env:TRANSACTION_LIVE_VIEWER_JWT = $viewerToken
    $env:TRANSACTION_LIVE_UNKNOWN_ROLE_JWT = $unknownToken
    $env:TRANSACTION_LIVE_MALFORMED_JWT = $malformedToken
    $env:TRANSACTION_LIVE_SERVICE_JWT = $serviceToken
    $env:TRANSACTION_LIVE_REPOSITORY_ROOT = $repository
    $env:TRANSACTION_LIVE_PROBE_EVIDENCE_PATH = $probeEvidence
    $env:TRANSACTION_LIVE_JAVA_METRICS_PATH = $javaMetrics
    $env:TRANSACTION_LIVE_PYTHON_LOG_PATH = $pythonLog
    $env:TRANSACTION_LIVE_PYTHON_JUNIT_PATH = $pythonJunit
    $env:TRANSACTION_LIVE_PYTHON_EXECUTABLE = $python
    $env:TRANSACTION_LIVE_SENTINEL = $sentinel
    $env:TRANSACTION_LIVE_GATEWAY_SENTINEL = $gatewaySentinel
    $env:TRANSACTION_LIVE_CORRELATION_ID = $correlationId
    $env:TRANSACTION_LIVE_GATEWAY_JAR = $gatewayJar
    $env:TRANSACTION_LIVE_GATEWAY_PORT = [string]$gatewayPort
    $env:TRANSACTION_LIVE_GATEWAY_OUT_PATH = $gatewayOut
    $env:TRANSACTION_LIVE_GATEWAY_ERR_PATH = $gatewayErr

    $mavenStarted = $true
    $surefireReportsDeleted = $false
    $testExit = Invoke-CapturedProcess $maven @(
        '-f', 'serviceCenter/pom.xml', '-pl', ':mq-procedure-service', '-am',
        '-Dtest=com.dylan.mqprocedureserver.live.TransactionRealActionLiveIntegrationTest',
        '-Dsurefire.failIfNoSpecifiedTests=false',
        "-Dsurefire.reportsDirectory=$surefireReportDirectory", 'test'
    ) $repository $mavenOut $mavenErr
    Stop-IsolatedAuth

    if ($testExit -ne 0) {
        $failureText = ''
        foreach ($path in @($mavenOut, $mavenErr, $pythonLog, $pythonJunit, $gatewayOut, $gatewayErr)) {
            if ((Test-Path -LiteralPath $path) -and (Get-Item -LiteralPath $path).Length -le 16777216) {
                $failureText += [string](Get-Content -LiteralPath $path -Raw -Encoding UTF8)
            }
        }
        $integrationFailureCode = Get-TransactionLiveSafeFailureCode -Text $failureText
        throw $integrationFailureCode
    }
    if (-not (Test-Path -LiteralPath $probeEvidence) -or -not (Test-Path -LiteralPath $javaMetrics)) {
        throw 'transaction.live_metrics_missing'
    }

    $probe = Get-Content -LiteralPath $probeEvidence -Raw -Encoding UTF8 | ConvertFrom-Json
    $metrics = Get-Content -LiteralPath $javaMetrics -Raw -Encoding UTF8 | ConvertFrom-Json
    $totalTransactionRequests = [int]$probe.requestCounts.transaction + [int]$metrics.gateway
    if ($totalTransactionRequests -ne $maxTransactionRequests -or
            $probe.requestCounts.transaction -ne 7 -or $probe.requestCounts.adapter -ne 6 -or
            $metrics.gateway -ne $maxGatewayRequests -or $metrics.gatewayResponseStatus -ne 200 -or
            $metrics.serviceSearch -ne 4 -or $metrics.mapperCountUpTo -ne 4 -or
            $metrics.mapperQuery -ne 0 -or $metrics.otherServiceMethods -ne 0 -or
            -not $probe.precisionMatrix.jsonNumberOnly -or -not $metrics.amountExact -or
            -not $metrics.amountGtExact -or -not $metrics.amountLtExact -or
            -not $metrics.gatewayAmountExact -or -not $metrics.mapperValuesUnmodified) {
        throw 'transaction.live_call_count_invalid'
    }

    $logLeakDetected = Test-SensitiveLogValue
    if ($logLeakDetected) {
        throw 'transaction.live_log_leak'
    }

    $completed = [DateTimeOffset]::UtcNow
    $evidence = [ordered]@{
        schemaVersion = 1
        workPackage = 'WP-TXN-REAL-01'
        validations = @('VAL-TXN-004', 'VAL-TXN-005')
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
        precisionMatrix = [ordered]@{
            amountExact = [bool]$metrics.amountExact
            amountGtExact = [bool]$metrics.amountGtExact
            amountLtExact = [bool]$metrics.amountLtExact
            gatewayAmountExact = [bool]$metrics.gatewayAmountExact
            jsonNumberOnly = [bool]$probe.precisionMatrix.jsonNumberOnly
            mapperValuesUnmodified = [bool]$metrics.mapperValuesUnmodified
        }
        requestCounts = [ordered]@{
            transaction = [int]$probe.requestCounts.transaction
            adapter = [int]$probe.requestCounts.adapter
            gateway = [int]$metrics.gateway
            serviceSearch = [int]$metrics.serviceSearch
            mapperCountUpTo = [int]$metrics.mapperCountUpTo
            mapperQuery = [int]$metrics.mapperQuery
            otherServiceMethods = [int]$metrics.otherServiceMethods
            otherTransactionEndpoints = [int]$probe.requestCounts.otherTransactionEndpoints
            model = [int]$probe.requestCounts.model
        }
        responseVisibility = 'provider_contract_and_empty_live_response'
        logSafety = [ordered]@{
            logLeakCount = 0
            rawLogsDeleted = $true
            transactionValuePersisted = $false
            jwtPersisted = $false
            hmacKeyPersisted = $false
            bodyPersisted = $false
            principalPersisted = $false
        }
        runtimeIsolation = [ordered]@{
            authService = 'isolated_local'
            transactionService = 'spring_boot_test_netty'
            gatewayService = 'actual_jar_formal_mq_route'
            databaseAccessed = $false
            permanentRouteUsed = $true
            deepSeekCalled = $false
        }
    }
    $json = $evidence | ConvertTo-Json -Depth 8 -Compress
    foreach ($sensitive in @(
            $sentinel, $gatewaySentinel, $secret, $adminToken, $dylanToken, $viewerToken,
            $unknownToken, $serviceToken, $malformedToken, $gatewayRequestBody
        ) + $amountValues) {
        if ($sensitive -and $json.Contains([string]$sensitive)) {
            throw 'transaction.live_evidence_leak'
        }
    }

    Remove-GeneratedSurefireReports
    Remove-RunRoot
    if (-not $runRootDeleted -or -not $surefireReportsDeleted) {
        throw 'transaction.live_raw_log_delete_failed'
    }
    $targetDirectory = [IO.Path]::GetFullPath((Join-Path $repository $EvidenceDirectory))
    $expectedDirectory = [IO.Path]::GetFullPath((Join-Path $repository 'agent-runtime\tests\integration\adapters\transaction\evidence'))
    if ($targetDirectory -ne $expectedDirectory) {
        throw 'transaction.live_evidence_directory_invalid'
    }
    New-Item -ItemType Directory -Path $targetDirectory -Force | Out-Null
    $stamp = $started.ToUniversalTime().ToString('yyyyMMddTHHmmssZ')
    $finalPath = Join-Path $targetDirectory "wp-txn-real-01-$stamp.json"
    $temporaryEvidence = "$finalPath.tmp"
    [IO.File]::WriteAllText($temporaryEvidence, $json, [Text.UTF8Encoding]::new($false))
    & $python (Join-Path $repository 'agent-runtime\tests\integration\adapters\transaction\evidence_contract.py') $temporaryEvidence
    if ($LASTEXITCODE -ne 0) {
        Remove-Item -LiteralPath $temporaryEvidence -Force -ErrorAction SilentlyContinue
        throw 'transaction.live_evidence_schema_invalid'
    }
    Move-Item -LiteralPath $temporaryEvidence -Destination $finalPath
    [pscustomobject]@{
        status = 'passed'
        transactionRequests = $maxTransactionRequests
        gatewayRequests = $maxGatewayRequests
        logLeakCount = 0
        rawLogsDeleted = $true
        evidence = $finalPath
    }
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
    $sentinel = $null
    $gatewaySentinel = $null
    $gatewayRequestBody = $null
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
        $previous = $environmentSnapshot[$name]
        if ($null -eq $previous) {
            Remove-Item "Env:\$name" -ErrorAction SilentlyContinue
        } else {
            [Environment]::SetEnvironmentVariable($name, [string]$previous, 'Process')
        }
    }
    if ($cleanupFailed -or -not $runRootDeleted -or -not $surefireReportsDeleted) {
        throw 'transaction.live_cleanup_failed'
    }
    if ($logLeakDetected) {
        if ([string]::IsNullOrWhiteSpace($logLeakCategory)) {
            $logLeakCategory = 'unknown'
        }
        if ([string]::IsNullOrWhiteSpace($integrationFailureCode)) {
            throw "transaction.live_log_leak:$logLeakCategory"
        }
        throw "transaction.live_log_leak:$logLeakCategory`:$integrationFailureCode"
    }
}
