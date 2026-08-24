[CmdletBinding()]
param(
    [ValidateSet('Access', 'Employee', 'Transaction', 'Closure')]
    [string]$Stage,
    [string]$RepositoryRoot = (Split-Path -Parent (Split-Path -Parent $PSScriptRoot))
)

$ErrorActionPreference = 'Stop'
$repository = [IO.Path]::GetFullPath($RepositoryRoot)
if ($repository -ne 'D:\codex') { throw 'structured_uat.repository_invalid' }
$python = Join-Path $repository '.tmp\agent-runtime-venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) { throw 'structured_uat.python_missing' }
$gitHead = [string](& git -C $repository rev-parse HEAD 2>$null)
if ($LASTEXITCODE -ne 0 -or $gitHead -notmatch '^[0-9a-f]{40}$') { throw 'structured_uat.git_head_invalid' }
$stageName = $Stage.ToLowerInvariant()
$evidenceRoot = Join-Path $repository 'agent-runtime\tests\uat\evidence'
$evidencePath = Join-Path $evidenceRoot "structured-query-uat-$stageName-v1.result.json"

function Invoke-EvidenceBuilder([string]$Name, [string]$RuntimeEvidence = '') {
    $oldPythonPath = [Environment]::GetEnvironmentVariable('PYTHONPATH', 'Process')
    try {
        $env:PYTHONPATH = 'src;.'
        $arguments = @('-m', 'tests.uat.evidence_contract', '--stage', $Name, '--git-head', $gitHead, '--output', $evidencePath)
        if (-not [string]::IsNullOrWhiteSpace($RuntimeEvidence)) {
            $arguments += @('--runtime-evidence', $RuntimeEvidence)
        }
        & $python @arguments
        if ($LASTEXITCODE -ne 0) { throw 'structured_uat.evidence_invalid' }
    } finally {
        if ($null -eq $oldPythonPath) { Remove-Item Env:\PYTHONPATH -ErrorAction SilentlyContinue }
        else { $env:PYTHONPATH = $oldPythonPath }
    }
}

if ($Stage -eq 'Closure') {
    $stageEvidence = [ordered]@{
        access = Join-Path $evidenceRoot 'structured-query-uat-access-v1.result.json'
        employee = Join-Path $evidenceRoot 'structured-query-uat-employee-v1.result.json'
        transaction = Join-Path $evidenceRoot 'structured-query-uat-transaction-v1.result.json'
    }
    if ($stageEvidence.Values | Where-Object { -not (Test-Path -LiteralPath $_) }) {
        throw 'structured_uat.stage_evidence_missing'
    }
    & mvn.cmd -f (Join-Path $repository 'agent-service\pom.xml') test
    if ($LASTEXITCODE -ne 0) { throw 'structured_uat.closure_java_failed' }
    Push-Location (Join-Path $repository 'agent-runtime')
    try {
        & $python -m pytest `
            tests/unit/core/test_action_latch.py `
            tests/unit/core/test_execution.py `
            tests/unit/graph/test_hybrid_action_resolution.py `
            tests/integration/graph/test_business_local_resolvers.py `
            tests/integration/business/test_business_resolver_composition.py `
            tests/integration/adapters/employee/test_fake_server.py `
            tests/integration/adapters/transaction/test_fake_server.py `
            tests/uat -q
        if ($LASTEXITCODE -ne 0) { throw 'structured_uat.closure_python_failed' }
        & $python -m mypy --strict `
            src/agent_runtime/core `
            src/agent_runtime/graph `
            src/agent_runtime/adapters/employee `
            src/agent_runtime/adapters/transaction `
            tests/uat/evidence_contract.py
        if ($LASTEXITCODE -ne 0) { throw 'structured_uat.closure_mypy_failed' }
        & $python -m compileall -q `
            src/agent_runtime/core `
            src/agent_runtime/graph `
            src/agent_runtime/adapters/employee `
            src/agent_runtime/adapters/transaction `
            tests/uat
        if ($LASTEXITCODE -ne 0) { throw 'structured_uat.closure_compileall_failed' }
        $oldPythonPath = [Environment]::GetEnvironmentVariable('PYTHONPATH', 'Process')
        try {
            $env:PYTHONPATH = 'src;.'
            & $python -m tests.uat.evidence_contract `
                --stage closure --git-head $gitHead `
                --access-evidence $stageEvidence.access `
                --employee-evidence $stageEvidence.employee `
                --transaction-evidence $stageEvidence.transaction `
                --output $evidencePath
            if ($LASTEXITCODE -ne 0) { throw 'structured_uat.closure_evidence_invalid' }
        } finally {
            if ($null -eq $oldPythonPath) { Remove-Item Env:\PYTHONPATH -ErrorAction SilentlyContinue }
            else { $env:PYTHONPATH = $oldPythonPath }
        }
    } finally {
        Pop-Location
    }
    $value = Get-Content -LiteralPath $evidencePath -Raw -Encoding UTF8 | ConvertFrom-Json
    [pscustomobject]@{
        status = 'passed'; phase = 'structured_query'; cases = @($value.cases).Count
        employeeRequests = [int]$value.requestCounts.employee
        transactionRequests = [int]$value.requestCounts.transaction
        externalModelOutbound = [int]$value.requestCounts.externalModelOutbound
        fullUatGateClosed = [bool]$value.scope.fullUatGateClosed
        evidence = $evidencePath
    }
    exit 0
}

if ($Stage -eq 'Access') {
    & mvn.cmd -f (Join-Path $repository 'agent-service\pom.xml') `
        '-Dtest=AgentSecurityContractTest,AgentAccessE2ETest' `
        '-Dsurefire.failIfNoSpecifiedTests=false' test
    if ($LASTEXITCODE -ne 0) { throw 'structured_uat.access_java_failed' }
    Push-Location (Join-Path $repository 'agent-runtime')
    try {
        & $python -m pytest `
            tests/unit/core/test_action_latch.py `
            tests/unit/core/test_execution.py `
            tests/unit/model/test_credentials.py `
            tests/uat/test_uat_assets.py `
            tests/uat/test_uat_preflight_script.py `
            tests/uat/test_uat_evidence_contract.py -q
        if ($LASTEXITCODE -ne 0) { throw 'structured_uat.access_python_failed' }
        Invoke-EvidenceBuilder 'access'
    } finally {
        Pop-Location
    }
    [pscustomobject]@{ status = 'passed'; stage = 'access'; cases = 4; evidence = $evidencePath }
    exit 0
}

function Test-PortFree([int]$Port) {
    return -not [bool](Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue)
}

function Start-OwnedProcess(
    [string]$FilePath,
    [string[]]$ArgumentList,
    [string]$WorkingDirectory,
    [string]$StandardOutput,
    [string]$StandardError
) {
    return Start-Process -FilePath $FilePath -ArgumentList $ArgumentList -WorkingDirectory $WorkingDirectory `
        -WindowStyle Hidden -PassThru -RedirectStandardOutput $StandardOutput -RedirectStandardError $StandardError
}

function Wait-OwnedReady(
    [string]$Uri,
    [int]$Port,
    [Diagnostics.Process]$Process,
    [int[]]$AllowedStatus
) {
    for ($attempt = 0; $attempt -lt 120; $attempt++) {
        if ($Process.HasExited) { throw 'structured_uat.service_process_exited' }
        $listener = Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue |
            Where-Object { $_.OwningProcess -eq $Process.Id }
        if ($listener) {
            try {
                $response = Invoke-WebRequest -Uri $Uri -Method Get -TimeoutSec 2 -SkipHttpErrorCheck
                if ($AllowedStatus -contains [int]$response.StatusCode) { return }
            } catch { }
        }
        Start-Sleep -Milliseconds 500
    }
    throw 'structured_uat.service_readiness_timeout'
}

function Stop-Owned([Diagnostics.Process]$Process) {
    if ($null -eq $Process) { return }
    try {
        $Process.Refresh()
        if (-not $Process.HasExited) {
            Stop-Process -Id $Process.Id -ErrorAction SilentlyContinue
            if (-not $Process.WaitForExit(5000)) {
                Stop-Process -Id $Process.Id -Force -ErrorAction SilentlyContinue
                [void]$Process.WaitForExit(3000)
            }
        }
    } catch { }
}

function Get-LocalPassword([string]$User) {
    $path = Join-Path $repository 'auth-service\src\main\resources\auth-users.yml'
    $text = Get-Content -LiteralPath $path -Raw -Encoding UTF8
    $match = [regex]::Match($text, "(?ms)^\s{4}${User}:\s*\r?\n\s+password:\s*([^\r\n]+)")
    if (-not $match.Success) { throw 'structured_uat.auth_fixture_missing' }
    $stored = $match.Groups[1].Value.Trim().Trim('"').Trim("'")
    if (-not $stored.StartsWith('{noop}')) { throw 'structured_uat.auth_fixture_invalid' }
    return $stored.Substring(6)
}

function Get-LoginToken([string]$User) {
    $session = [Microsoft.PowerShell.Commands.WebRequestSession]::new()
    $body = @{ userId = $User; password = (Get-LocalPassword $User) } | ConvertTo-Json -Compress
    $response = Invoke-WebRequest -Uri 'http://127.0.0.1:8090/login' -Method Post `
        -ContentType 'application/json' -Body $body -WebSession $session -TimeoutSec 5 -SkipHttpErrorCheck
    if ($response.StatusCode -ne 200) { throw 'structured_uat.auth_login_failed' }
    $cookie = $session.Cookies.GetCookies('http://127.0.0.1:8090')['AUTH_TOKEN']
    if ($null -eq $cookie -or [string]::IsNullOrWhiteSpace($cookie.Value)) {
        throw 'structured_uat.auth_token_missing'
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
        sub = 'structured-uat-unknown'; iat = $now; exp = $now + 3600
        token_type = 'user'; role = @('UNKNOWN')
    } | ConvertTo-Json -Compress
    $unsigned = "$(ConvertTo-Base64Url ([Text.Encoding]::UTF8.GetBytes($header))).$(ConvertTo-Base64Url ([Text.Encoding]::UTF8.GetBytes($claims)))"
    $hmac = [Security.Cryptography.HMACSHA256]::new($KeyBytes)
    try { $signature = ConvertTo-Base64Url ($hmac.ComputeHash([Text.Encoding]::ASCII.GetBytes($unsigned))) }
    finally { $hmac.Dispose() }
    return "$unsigned.$signature"
}

function Get-DatasourceScalar([string]$Name) {
    $path = Join-Path $repository 'config-service\src\main\resources\config\application-datasource.yml'
    $text = Get-Content -LiteralPath $path -Raw -Encoding UTF8
    $escaped = [regex]::Escape($Name)
    $match = [regex]::Match($text, "(?m)^\s{4}${escaped}:\s*([^\r\n]+)\s*$")
    if (-not $match.Success) { throw 'structured_uat.datasource_config_invalid' }
    return $match.Groups[1].Value.Trim().Trim('"').Trim("'")
}

function Get-TransactionType([string]$RunRoot) {
    $connector = Get-ChildItem -Path (Join-Path $env:USERPROFILE '.m2\repository\com\mysql\mysql-connector-j') `
        -Recurse -Filter 'mysql-connector-j-*.jar' -File -ErrorAction Stop |
        Where-Object { $_.Name -notmatch '(sources|javadoc)' } |
        Sort-Object FullName -Descending | Select-Object -First 1
    if ($null -eq $connector) { throw 'structured_uat.database_driver_missing' }
    $source = Join-Path $RunRoot 'TransactionTypeSelector.java'
    $errorLog = Join-Path $RunRoot 'selector.err.log'
    $program = @'
import java.sql.Connection;
import java.sql.DriverManager;
import java.sql.PreparedStatement;
import java.sql.ResultSet;

public final class TransactionTypeSelector {
    private static final String SQL = "SELECT TRANS_TYPE FROM t_transaction WHERE TRANS_TYPE IS NOT NULL AND CHAR_LENGTH(TRIM(TRANS_TYPE)) BETWEEN 1 AND 64 ORDER BY TRANS_ID LIMIT 1";
    public static void main(String[] args) throws Exception {
        try (Connection connection = DriverManager.getConnection(required("STRUCTURED_UAT_DB_URL"), required("STRUCTURED_UAT_DB_USER"), required("STRUCTURED_UAT_DB_PASSWORD"));
             PreparedStatement statement = connection.prepareStatement(SQL);
             ResultSet rows = statement.executeQuery()) {
            if (!rows.next()) throw new IllegalStateException("transaction.type_not_found");
            String value = rows.getString(1);
            if (value == null || !value.equals(value.trim()) || value.length() < 1 || value.length() > 64 || forbidden(value)) {
                throw new IllegalStateException("transaction.type_invalid");
            }
            System.out.print(value);
        }
    }
    private static String required(String name) {
        String value = System.getenv(name);
        if (value == null || value.isBlank()) throw new IllegalStateException("transaction.selector_environment_missing");
        return value;
    }
    private static boolean forbidden(String value) {
        for (int index = 0; index < value.length(); index++) {
            char item = value.charAt(index);
            if (Character.isISOControl(item) || item == '\u202A' || item == '\u202B' || item == '\u202C' ||
                    item == '\u202D' || item == '\u202E' || item == '\u2066' || item == '\u2067' ||
                    item == '\u2068' || item == '\u2069') return true;
        }
        return false;
    }
}
'@
    [IO.File]::WriteAllText($source, $program, [Text.UTF8Encoding]::new($false))
    & javac.exe -encoding UTF-8 -cp $connector.FullName -d $RunRoot $source 2>$errorLog
    if ($LASTEXITCODE -ne 0) { throw 'structured_uat.selector_compile_failed' }
    $env:STRUCTURED_UAT_DB_URL = Get-DatasourceScalar 'url'
    $env:STRUCTURED_UAT_DB_USER = Get-DatasourceScalar 'username'
    $env:STRUCTURED_UAT_DB_PASSWORD = Get-DatasourceScalar 'password'
    try {
        $value = [string](& java.exe -cp "$RunRoot;$($connector.FullName)" TransactionTypeSelector 2>$errorLog)
        if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($value)) {
            throw 'structured_uat.transaction_type_unavailable'
        }
        return $value
    } finally {
        Remove-Item Env:\STRUCTURED_UAT_DB_URL,Env:\STRUCTURED_UAT_DB_USER,Env:\STRUCTURED_UAT_DB_PASSWORD -ErrorAction SilentlyContinue
    }
}

$employeeIdentifier = [Environment]::GetEnvironmentVariable('SYSTEM_E2E_EMPLOYEE_IDENTIFIER', 'Process')
if ($Stage -eq 'Employee' -and [string]::IsNullOrWhiteSpace($employeeIdentifier)) {
    throw 'structured_uat.employee_identifier_missing'
}
foreach ($port in @(8090, $(if ($Stage -eq 'Employee') { 9210 } else { 8182 }))) {
    if (-not (Test-PortFree $port)) { throw 'structured_uat.owned_port_occupied' }
}

$runRoot = Join-Path $repository ".tmp\structured-uat\$stageName-$([DateTime]::UtcNow.ToString('yyyyMMddTHHmmssfffZ'))"
New-Item -ItemType Directory -Path $runRoot -Force | Out-Null
$runtimeEvidence = Join-Path $runRoot 'runtime-evidence.json'
$runtimeLog = Join-Path $runRoot 'runtime.log'
$runtimeStop = Join-Path $runRoot 'runtime.stop'
$mavenOut = Join-Path $runRoot 'maven.out.log'
$mavenErr = Join-Path $runRoot 'maven.err.log'
$buildOut = Join-Path $runRoot 'build.out.log'
$buildErr = Join-Path $runRoot 'build.err.log'
$authOut = Join-Path $runRoot 'auth.out.log'
$authErr = Join-Path $runRoot 'auth.err.log'
$domainOut = Join-Path $runRoot 'domain.out.log'
$domainErr = Join-Path $runRoot 'domain.err.log'
$surefireReports = Join-Path $runRoot 'surefire-reports'
$rawLogs = @($runtimeLog, $mavenOut, $mavenErr, $buildOut, $buildErr, $authOut, $authErr, $domainOut, $domainErr)
$keyBytes = [Security.Cryptography.RandomNumberGenerator]::GetBytes(48)
$secret = [Convert]::ToBase64String($keyBytes)
$authProcess = $null
$domainProcess = $null
$adminToken = $null
$viewerToken = $null
$unknownToken = $null
$transactionType = $null
$failure = $null
$logsDeleted = $false
$processesStopped = $false
$names = @(
    'COMMON_SECURITY_JWT_HMAC_KEY_ACTIVE','RUN_STRUCTURED_QUERY_UAT',
    'STRUCTURED_UAT_ADMIN_JWT','STRUCTURED_UAT_VIEWER_JWT','STRUCTURED_UAT_UNKNOWN_ROLE_JWT',
    'STRUCTURED_UAT_RUNTIME_LOG_PATH','SYSTEM_E2E_RUNTIME_STOP_PATH','SYSTEM_E2E_EVIDENCE_PATH',
    'SYSTEM_E2E_KNOWLEDGE_BASE_URL','SYSTEM_E2E_EMBEDDING_BASE_URL','SYSTEM_E2E_RERANK_BASE_URL',
    'SYSTEM_E2E_EMPLOYEE_BASE_URL','SYSTEM_E2E_TRANSACTION_BASE_URL','AGENT_MODEL_PROVIDER','UAT_TRANSACTION_TYPE'
)
$snapshot = @{}
foreach ($name in $names) { $snapshot[$name] = [Environment]::GetEnvironmentVariable($name, 'Process') }

try {
    $modules = if ($Stage -eq 'Employee') { ':auth-service,:employee-service' } else { ':auth-service,:mq-procedure-service' }
    $build = Start-Process -FilePath (Get-Command mvn.cmd -ErrorAction Stop).Source -ArgumentList @(
        '-f','serviceCenter/pom.xml','-pl',$modules,'-am','-DskipTests','package'
    ) -WorkingDirectory $repository -WindowStyle Hidden -PassThru -Wait `
        -RedirectStandardOutput $buildOut -RedirectStandardError $buildErr
    if ($build.ExitCode -ne 0) { throw 'structured_uat.service_build_failed' }

    if ($Stage -eq 'Transaction') { $transactionType = Get-TransactionType $runRoot }
    $authJar = Join-Path $repository 'auth-service\target\auth-service-0.0.1-SNAPSHOT.jar'
    $domainJar = if ($Stage -eq 'Employee') {
        Join-Path $repository 'employee-service\target\employee-service-0.0.1-SNAPSHOT.jar'
    } else {
        Join-Path $repository 'mq-procedure-service\target\mq-procedure-service-0.0.1-SNAPSHOT.jar'
    }
    if (-not (Test-Path -LiteralPath $authJar) -or -not (Test-Path -LiteralPath $domainJar)) {
        throw 'structured_uat.service_jar_missing'
    }

    $env:COMMON_SECURITY_JWT_HMAC_KEY_ACTIVE = $secret
    $commonArgs = @(
        '--spring.main.banner-mode=off','--spring.cloud.config.enabled=false','--spring.config.import=',
        '--spring.config.additional-location=optional:file:D:/codex/config-service/src/main/resources/config/',
        '--eureka.client.enabled=false','--common.security.secrets.source-order[0]=environment',
        '--common.security.secrets.allow-config-values=false','--common.security.secrets.fail-fast=true',
        '--common.security.secrets.jwt.active-key-id=ACTIVE',
        '--common.security.secrets.jwt.keys.ACTIVE.env=COMMON_SECURITY_JWT_HMAC_KEY_ACTIVE',
        '--common.security.secrets.jwt.keys.ACTIVE.value='
    )
    $authProcess = Start-OwnedProcess 'java' (@('-jar',$authJar,'--server.port=8090') + $commonArgs) `
        (Join-Path $repository 'auth-service') $authOut $authErr
    $domainPort = if ($Stage -eq 'Employee') { 9210 } else { 8182 }
    $domainProcess = Start-OwnedProcess 'java' (@('-jar',$domainJar,"--server.port=$domainPort") + $commonArgs) `
        (Join-Path $repository $(if ($Stage -eq 'Employee') { 'employee-service' } else { 'mq-procedure-service' })) $domainOut $domainErr
    Wait-OwnedReady 'http://127.0.0.1:8090/public/test' 8090 $authProcess @(200)
    Wait-OwnedReady "http://127.0.0.1:$domainPort/actuator/health" $domainPort $domainProcess @(200,401,403)

    $adminToken = Get-LoginToken 'admin'
    $viewerToken = Get-LoginToken 'viewer_t'
    $unknownToken = New-UnknownRoleJwt $keyBytes
    $env:RUN_STRUCTURED_QUERY_UAT = '1'
    $env:STRUCTURED_UAT_ADMIN_JWT = $adminToken
    $env:STRUCTURED_UAT_VIEWER_JWT = $viewerToken
    $env:STRUCTURED_UAT_UNKNOWN_ROLE_JWT = $unknownToken
    $env:STRUCTURED_UAT_RUNTIME_LOG_PATH = $runtimeLog
    $env:SYSTEM_E2E_RUNTIME_STOP_PATH = $runtimeStop
    $env:SYSTEM_E2E_EVIDENCE_PATH = $runtimeEvidence
    $env:SYSTEM_E2E_KNOWLEDGE_BASE_URL = 'http://127.0.0.1:1'
    $env:SYSTEM_E2E_EMBEDDING_BASE_URL = 'http://127.0.0.1:1'
    $env:SYSTEM_E2E_RERANK_BASE_URL = 'http://127.0.0.1:1'
    $env:SYSTEM_E2E_EMPLOYEE_BASE_URL = if ($Stage -eq 'Employee') { 'http://127.0.0.1:9210' } else { 'http://127.0.0.1:1' }
    $env:SYSTEM_E2E_TRANSACTION_BASE_URL = if ($Stage -eq 'Transaction') { 'http://127.0.0.1:8182' } else { 'http://127.0.0.1:1' }
    $env:AGENT_MODEL_PROVIDER = 'stub'
    if ($Stage -eq 'Transaction') { $env:UAT_TRANSACTION_TYPE = $transactionType }

    $method = if ($Stage -eq 'Employee') { 'verifiesEmployeeUat' } else { 'verifiesTransactionUat' }
    $test = Start-Process -FilePath (Get-Command mvn.cmd -ErrorAction Stop).Source -ArgumentList @(
        '-f','agent-service/pom.xml',"-Dtest=AgentStructuredQueryUATTest#$method",'-Dsurefire.failIfNoSpecifiedTests=false',
        "-Dsurefire.reportsDirectory=$surefireReports","-Dagent.runtime.python=$python",'test'
    ) -WorkingDirectory $repository -WindowStyle Hidden -PassThru -Wait `
        -RedirectStandardOutput $mavenOut -RedirectStandardError $mavenErr
    if ($test.ExitCode -ne 0) { throw 'structured_uat.integration_failed' }
    if (-not (Test-Path -LiteralPath $runtimeEvidence)) { throw 'structured_uat.runtime_evidence_missing' }
} catch {
    $failure = $_.Exception
} finally {
    Stop-Owned $domainProcess
    Stop-Owned $authProcess
    $processesStopped = -not (@($domainProcess,$authProcess) | Where-Object { $null -ne $_ -and -not $_.HasExited })
    $artifacts = @($rawLogs)
    if (Test-Path -LiteralPath $surefireReports) { $artifacts += @(Get-ChildItem -LiteralPath $surefireReports -Recurse -File) }
    $sensitive = @($secret,$adminToken,$viewerToken,$unknownToken,$employeeIdentifier,$transactionType) |
        Where-Object { -not [string]::IsNullOrEmpty([string]$_) }
    foreach ($artifact in $artifacts) {
        if (-not (Test-Path -LiteralPath $artifact)) { continue }
        if ((Get-Item -LiteralPath $artifact).Length -gt 33554432) {
            if ($null -eq $failure) { $failure = [Exception]::new('structured_uat.log_scan_failed') }
            continue
        }
        $text = Get-Content -LiteralPath $artifact -Raw -Encoding UTF8
        foreach ($value in $sensitive) {
            if ($text.Contains([string]$value, [StringComparison]::Ordinal)) {
                if ($null -eq $failure) { $failure = [Exception]::new('structured_uat.log_leak') }
            }
        }
    }
    foreach ($artifact in $artifacts) {
        if (Test-Path -LiteralPath $artifact) { Remove-Item -LiteralPath $artifact -Force }
    }
    if (Test-Path -LiteralPath $surefireReports) { Remove-Item -LiteralPath $surefireReports -Recurse -Force }
    if (Test-Path -LiteralPath $runtimeStop) { Remove-Item -LiteralPath $runtimeStop -Force }
    $logsDeleted = -not ($artifacts | Where-Object { Test-Path -LiteralPath $_ }) -and -not (Test-Path -LiteralPath $surefireReports)
    foreach ($name in $names) {
        $old = $snapshot[$name]
        if ($null -eq $old) { Remove-Item "Env:\$name" -ErrorAction SilentlyContinue }
        else { [Environment]::SetEnvironmentVariable($name, [string]$old, 'Process') }
    }
}

try {
    if ($null -ne $failure) { throw $failure }
    if (-not $processesStopped) { throw 'structured_uat.cleanup_failed' }
    if (-not $logsDeleted) { throw 'structured_uat.raw_log_cleanup_failed' }
    Push-Location (Join-Path $repository 'agent-runtime')
    try { Invoke-EvidenceBuilder $stageName $runtimeEvidence }
    finally { Pop-Location }
    $value = Get-Content -LiteralPath $evidencePath -Raw -Encoding UTF8 | ConvertFrom-Json
    [pscustomobject]@{
        status = 'passed'; stage = $stageName; cases = @($value.cases).Count
        domainRequests = [int]$value.requestCounts.$stageName
        externalModelOutbound = [int]$value.requestCounts.externalModelOutbound
        logLeakCount = [int]$value.security.logLeakCount
        evidence = $evidencePath
    }
} finally {
    $secret = $null; $adminToken = $null; $viewerToken = $null; $unknownToken = $null
    $employeeIdentifier = $null; $transactionType = $null
    if (Test-Path -LiteralPath $runRoot) { Remove-Item -LiteralPath $runRoot -Recurse -Force }
}
