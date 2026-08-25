[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('Controlled', 'Uat')]
    [string]$Stage,

    [switch]$PreflightOnly,

    [switch]$DownstreamOnly
)

$ErrorActionPreference = 'Stop'
$repository = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..'))
if ($repository -ne 'D:\codex') {
    throw 'business_list_live.repository_invalid'
}

$runtime = Join-Path $repository 'agent-runtime'
$python = Join-Path $repository '.tmp\agent-runtime-venv\Scripts\python.exe'
$stageValue = $Stage.ToLowerInvariant()
$evidenceRoot = [IO.Path]::GetFullPath((Join-Path $runtime 'tests\system_e2e\live\results'))
$evidenceName = if ($stageValue -eq 'controlled') {
    'business-list-v2-controlled-run03.result.json'
} else {
    'business-list-v2-uat.result.json'
}
$evidence = Join-Path $evidenceRoot $evidenceName
if (-not (Test-Path -LiteralPath $python)) {
    throw 'business_list_live.python_missing'
}
if (Test-Path -LiteralPath $evidence) {
    throw 'business_list_live.evidence_exists'
}

$modelKey = if ($DownstreamOnly) {
    $null
} else {
    [Environment]::GetEnvironmentVariable('LLM_API_KEY', 'Process')
}
if (-not $DownstreamOnly -and [string]::IsNullOrWhiteSpace($modelKey)) {
    throw 'business_list_live.model_key_missing'
}

$ownedPorts = @(8090, 9201, 9210, 8182)
$listeners = @(Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue |
    Where-Object { $ownedPorts -contains $_.LocalPort })
if ($listeners.Count -ne 0) {
    throw 'business_list_live.owned_port_occupied'
}

function Test-TcpReady([int]$Port) {
    $socket = [Net.Sockets.TcpClient]::new()
    try {
        $connection = $socket.ConnectAsync('127.0.0.1', $Port)
        return $connection.Wait(2000) -and $socket.Connected
    } catch {
        return $false
    } finally {
        $socket.Dispose()
    }
}

foreach ($infrastructurePort in @(9200, 8908)) {
    if (-not (Test-TcpReady $infrastructurePort)) {
        throw 'business_list_live.infrastructure_unavailable'
    }
}

$jars = [ordered]@{
    auth = Join-Path $repository 'auth-service\target\auth-service-0.0.1-SNAPSHOT.jar'
    es = Join-Path $repository 'es-query-service\target\es-query-service-0.0.1-SNAPSHOT.jar'
    employee = Join-Path $repository 'employee-service\target\employee-service-0.0.1-SNAPSHOT.jar'
    transaction = Join-Path $repository 'mq-procedure-service\target\mq-procedure-service-0.0.1-SNAPSHOT.jar'
}
if (@($jars.Values | Where-Object { -not (Test-Path -LiteralPath $_) }).Count -ne 0) {
    throw 'business_list_live.service_jar_missing'
}

$runRoot = Join-Path $repository (".tmp\business-list-live\" + [Guid]::NewGuid().ToString('N'))
New-Item -Path $runRoot -ItemType Directory -Force | Out-Null
$serviceProcesses = [System.Collections.Generic.List[Diagnostics.Process]]::new()
$logPaths = [System.Collections.Generic.List[string]]::new()
$keyBytes = [Security.Cryptography.RandomNumberGenerator]::GetBytes(48)
$sharedSecret = [Convert]::ToBase64String($keyBytes)
$adminToken = $null
$viewerToken = $null
$deniedToken = $null
$employeeIdentifier = $null
$transactionType = $null
$failureCode = $null
$logsDeleted = $false

$managedEnvironmentNames = @(
    'LLM_API_KEY', 'COMMON_SECURITY_JWT_HMAC_KEY_ACTIVE',
    'AGENT_KNOWLEDGE_READ_ALIAS', 'AGENT_KNOWLEDGE_EXPECTED_INDEX_NAME',
    'AGENT_KNOWLEDGE_EXPECTED_INDEX_UUID', 'AGENT_KNOWLEDGE_MAPPING_VERSION',
    'AGENT_KNOWLEDGE_POLICY_SNAPSHOT_ID', 'AGENT_KNOWLEDGE_LAW_SNAPSHOT_ID',
    'RUN_BUSINESS_LIST_LIVE', 'AGENT_MODEL_PROVIDER', 'AGENT_MODEL_ACTION_TIMEOUT_MS',
    'BUSINESS_LIST_ADMIN_JWT', 'BUSINESS_LIST_VIEWER_JWT', 'BUSINESS_LIST_DENIED_JWT',
    'BUSINESS_LIST_EMPLOYEE_IDENTIFIER', 'BUSINESS_LIST_TRANSACTION_TYPE',
    'BUSINESS_LIST_DB_URL', 'BUSINESS_LIST_DB_USERNAME', 'BUSINESS_LIST_DB_PASSWORD',
    'PYTHONPATH'
)
$previousEnvironment = @{}
foreach ($name in $managedEnvironmentNames) {
    $previousEnvironment[$name] = [Environment]::GetEnvironmentVariable($name, 'Process')
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
    for ($attempt = 0; $attempt -lt 100; $attempt++) {
        $Process.Refresh()
        if ($Process.HasExited) {
            throw 'business_list_live.service_process_exited'
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
    throw 'business_list_live.service_readiness_failed'
}

function Get-FixturePassword([string]$User) {
    $path = Join-Path $repository 'auth-service\src\main\resources\auth-users.yml'
    $content = Get-Content -LiteralPath $path -Raw -Encoding UTF8
    $match = [regex]::Match($content, "(?ms)^\s{4}${User}:\s*\r?\n\s+password:\s*([^\r\n]+)")
    if (-not $match.Success) {
        throw 'business_list_live.auth_fixture_missing'
    }
    $stored = $match.Groups[1].Value.Trim().Trim('"').Trim("'")
    if (-not $stored.StartsWith('{noop}')) {
        throw 'business_list_live.auth_fixture_invalid'
    }
    return $stored.Substring(6)
}

function Get-OwnedLoginToken([string]$User) {
    $session = [Microsoft.PowerShell.Commands.WebRequestSession]::new()
    $body = @{ userId = $User; password = (Get-FixturePassword $User) } |
        ConvertTo-Json -Compress
    $response = Invoke-WebRequest -Uri 'http://127.0.0.1:8090/login' -Method Post `
        -ContentType 'application/json' -Body $body -WebSession $session `
        -TimeoutSec 5 -SkipHttpErrorCheck
    if ($response.StatusCode -ne 200) {
        throw 'business_list_live.auth_login_failed'
    }
    $cookie = $session.Cookies.GetCookies('http://127.0.0.1:8090')['AUTH_TOKEN']
    if ($null -eq $cookie -or [string]::IsNullOrWhiteSpace($cookie.Value)) {
        throw 'business_list_live.auth_token_missing'
    }
    return $cookie.Value
}

function ConvertTo-Base64Url([byte[]]$Bytes) {
    return [Convert]::ToBase64String($Bytes).TrimEnd('=').Replace('+', '-').Replace('/', '_')
}

function New-DeniedToken([byte[]]$Bytes) {
    $now = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds()
    $header = [ordered]@{ alg = 'HS256'; kid = 'ACTIVE' } | ConvertTo-Json -Compress
    $claims = [ordered]@{
        sub = 'business-list-unknown'; iat = $now; exp = $now + 1800
        token_type = 'user'; role = @('UNKNOWN')
    } | ConvertTo-Json -Compress
    $unsigned = "$(ConvertTo-Base64Url ([Text.Encoding]::UTF8.GetBytes($header))).$(ConvertTo-Base64Url ([Text.Encoding]::UTF8.GetBytes($claims)))"
    $signer = [Security.Cryptography.HMACSHA256]::new($Bytes)
    try {
        $signature = ConvertTo-Base64Url (
            $signer.ComputeHash([Text.Encoding]::ASCII.GetBytes($unsigned))
        )
    } finally {
        $signer.Dispose()
    }
    return "$unsigned.$signature"
}

function Get-ExistingTransactionType() {
    $settingsPath = Join-Path $repository 'config-service\src\main\resources\config\application-datasource.yml'
    $settings = Get-Content -LiteralPath $settingsPath -Raw -Encoding UTF8
    foreach ($entry in @(
        @{ key = 'url'; variable = 'BUSINESS_LIST_DB_URL' },
        @{ key = 'username'; variable = 'BUSINESS_LIST_DB_USERNAME' },
        @{ key = 'password'; variable = 'BUSINESS_LIST_DB_PASSWORD' }
    )) {
        $match = [regex]::Match($settings, "(?m)^\s+$($entry.key):\s*([^\r\n]+)")
        if (-not $match.Success) {
            throw 'business_list_live.database_configuration_missing'
        }
        [Environment]::SetEnvironmentVariable(
            $entry.variable, $match.Groups[1].Value.Trim().Trim('"').Trim("'"), 'Process'
        )
    }

    try {
        $dependency = @(Get-ChildItem -LiteralPath (Join-Path $env:USERPROFILE '.m2\repository\com\mysql\mysql-connector-j') `
            -Filter 'mysql-connector-j-*.jar' -File -Recurse | Sort-Object FullName -Descending)
        if ($dependency.Count -eq 0) {
            throw 'business_list_live.mysql_driver_missing'
        }
        $source = Join-Path $runtime 'tests\system_e2e\BusinessListTransactionTypeProbe.java'
        $value = & java -cp $dependency[0].FullName $source
        if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace([string]$value)) {
            throw 'business_list_live.transaction_type_probe_failed'
        }
        return [string]$value
    } finally {
        foreach ($variable in @('BUSINESS_LIST_DB_URL', 'BUSINESS_LIST_DB_USERNAME', 'BUSINESS_LIST_DB_PASSWORD')) {
            [Environment]::SetEnvironmentVariable($variable, $null, 'Process')
        }
    }
}

try {
    [Environment]::SetEnvironmentVariable('LLM_API_KEY', $null, 'Process')
    [Environment]::SetEnvironmentVariable('COMMON_SECURITY_JWT_HMAC_KEY_ACTIVE', $sharedSecret, 'Process')
    [Environment]::SetEnvironmentVariable('AGENT_KNOWLEDGE_READ_ALIAS', 'agent-doc-tax-policy-v2-read', 'Process')
    [Environment]::SetEnvironmentVariable('AGENT_KNOWLEDGE_EXPECTED_INDEX_NAME', 'agent-doc-tax-policy-v3-20260803-agent-read-v1', 'Process')
    [Environment]::SetEnvironmentVariable('AGENT_KNOWLEDGE_EXPECTED_INDEX_UUID', 'k97bn1gxROSfVm7zGfzbOg', 'Process')
    [Environment]::SetEnvironmentVariable('AGENT_KNOWLEDGE_MAPPING_VERSION', 'agent-knowledge-tax-v1', 'Process')
    [Environment]::SetEnvironmentVariable('AGENT_KNOWLEDGE_POLICY_SNAPSHOT_ID', '7c71202794927a9497fed9df7cc0db5a052a53f0f6c2afdb6c0a16089f1c96ed', 'Process')
    [Environment]::SetEnvironmentVariable('AGENT_KNOWLEDGE_LAW_SNAPSHOT_ID', '99ae962ae1c8e5026187c864eada38b3c3b82d6b017e6e8f076f116aba53fce2', 'Process')

    $commonArguments = @(
        '--spring.main.banner-mode=off', '--spring.cloud.config.enabled=false',
        '--spring.config.import=',
        '--spring.config.additional-location=optional:file:D:/codex/config-service/src/main/resources/config/',
        '--eureka.client.enabled=false', '--common.security.secrets.source-order[0]=environment',
        '--common.security.secrets.allow-config-values=false',
        '--common.security.secrets.fail-fast=true',
        '--common.security.secrets.jwt.active-key-id=ACTIVE',
        '--common.security.secrets.jwt.keys.ACTIVE.env=COMMON_SECURITY_JWT_HMAC_KEY_ACTIVE',
        '--common.security.secrets.jwt.keys.ACTIVE.value='
    )
    $auth = Start-OwnedService 'auth' (
        @('-jar', $jars.auth, '--server.port=8090') + $commonArguments
    ) (Join-Path $repository 'auth-service')
    $es = Start-OwnedService 'es' (@(
        '-jar', $jars.es, '--server.port=9201',
        '--spring.profiles.active=datasource,es,knowledge-live',
        '--spring.elasticsearch.uris=http://127.0.0.1:9200',
        '--es.query.total-hits-threshold=10000',
        '--es.query.rebuild-source-allowed-hosts[0]=localhost',
        '--es.query.rebuild-max-batch-size=500'
    ) + $commonArguments) (Join-Path $repository 'es-query-service')
    $employee = Start-OwnedService 'employee' (
        @(
            '-jar', $jars.employee, '--server.port=9210',
            '--spring.cloud.discovery.client.simple.instances.es-query-service[0].uri=http://127.0.0.1:9201'
        ) + $commonArguments
    ) (Join-Path $repository 'employee-service')
    $transaction = Start-OwnedService 'transaction' (
        @('-jar', $jars.transaction, '--server.port=8182') + $commonArguments
    ) (Join-Path $repository 'mq-procedure-service')

    Wait-OwnedService $auth 8090 'http://127.0.0.1:8090/public/test' @(200)
    Wait-OwnedService $es 9201 'http://127.0.0.1:9201/actuator/health' @(200)
    Wait-OwnedService $employee 9210 'http://127.0.0.1:9210/actuator/health' @(200, 401, 403)
    Wait-OwnedService $transaction 8182 'http://127.0.0.1:8182/actuator/health' @(200, 401, 403)

    if ($DownstreamOnly) {
        $adminToken = Get-OwnedLoginToken 'admin'
        $body = @{
            filters = @(@{ field = 'contactAddress'; operator = 'contains'; value = '上海' })
            from = 0
            size = 1
        } | ConvertTo-Json -Depth 5 -Compress
        $response = Invoke-WebRequest -Uri 'http://127.0.0.1:9210/employees/es/search' `
            -Method Post -ContentType 'application/json' -Body $body `
            -Headers @{ Authorization = "Bearer $adminToken" } `
            -TimeoutSec 15 -SkipHttpErrorCheck
        if ([int]$response.StatusCode -ne 200) {
            throw "business_list_live.domain_preflight_http_$([int]$response.StatusCode)"
        }
        $document = $response.Content | ConvertFrom-Json
        if ($null -eq $document.hits) {
            throw 'business_list_live.domain_preflight_response_invalid'
        }
    } elseif (-not $PreflightOnly) {
        $adminToken = Get-OwnedLoginToken 'admin'
        $viewerToken = Get-OwnedLoginToken 'viewer_t'
        $deniedToken = New-DeniedToken $keyBytes

        if ($stageValue -eq 'uat') {
            $request = @{ size = 1; _source = $false; query = @{ match = @{ contactAddress = '上海' } } } |
                ConvertTo-Json -Depth 5 -Compress
            $indexResponse = Invoke-RestMethod -Uri 'http://127.0.0.1:9200/employee/_search' `
                -Method Post -ContentType 'application/json' -Body $request -TimeoutSec 10
            $employeeIdentifier = [string]$indexResponse.hits.hits[0]._id
            if ([string]::IsNullOrWhiteSpace($employeeIdentifier)) {
                throw 'business_list_live.employee_identifier_missing'
            }
            $transactionType = Get-ExistingTransactionType
        }

        [Environment]::SetEnvironmentVariable('RUN_BUSINESS_LIST_LIVE', '1', 'Process')
        [Environment]::SetEnvironmentVariable('AGENT_MODEL_PROVIDER', 'deepseek', 'Process')
        [Environment]::SetEnvironmentVariable('AGENT_MODEL_ACTION_TIMEOUT_MS', '15000', 'Process')
        [Environment]::SetEnvironmentVariable('BUSINESS_LIST_ADMIN_JWT', $adminToken, 'Process')
        [Environment]::SetEnvironmentVariable('BUSINESS_LIST_VIEWER_JWT', $viewerToken, 'Process')
        [Environment]::SetEnvironmentVariable('BUSINESS_LIST_DENIED_JWT', $deniedToken, 'Process')
        [Environment]::SetEnvironmentVariable('BUSINESS_LIST_EMPLOYEE_IDENTIFIER', $employeeIdentifier, 'Process')
        [Environment]::SetEnvironmentVariable('BUSINESS_LIST_TRANSACTION_TYPE', $transactionType, 'Process')
        [Environment]::SetEnvironmentVariable('PYTHONPATH', 'src;.', 'Process')
        [Environment]::SetEnvironmentVariable('LLM_API_KEY', $modelKey, 'Process')

        Push-Location $runtime
        try {
            & $python -m tests.system_e2e.business_list_live --stage $stageValue --evidence $evidence
            if ($LASTEXITCODE -ne 0) {
                throw 'business_list_live.stage_failed'
            }
        } finally {
            Pop-Location
            [Environment]::SetEnvironmentVariable('LLM_API_KEY', $null, 'Process')
        }
    }
} catch {
    $message = [string]$_.Exception.Message
    if ($message -match '^business_list_live\.[a-z0-9_]+(?::[A-Z0-9-]+)?$') {
        $failureCode = $message
    } else {
        $failureCode = 'business_list_live.unexpected_failure'
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
                $failureCode = 'business_list_live.process_cleanup_failed'
            }
        }
    }

    $sensitiveValues = @($sharedSecret, $modelKey, $adminToken, $viewerToken, $deniedToken, $employeeIdentifier) |
        Where-Object { -not [string]::IsNullOrWhiteSpace($_) }
    foreach ($log in $logPaths) {
        if (Test-Path -LiteralPath $log) {
            $text = Get-Content -LiteralPath $log -Raw -Encoding UTF8
            foreach ($secretValue in $sensitiveValues) {
                if ($null -ne $text -and $text.Contains([string]$secretValue, [StringComparison]::Ordinal)) {
                    $failureCode = 'business_list_live.log_leak'
                    break
                }
            }
            Remove-Item -LiteralPath $log -Force
        }
    }
    if ((Test-Path -LiteralPath $runRoot) -and
            @(Get-ChildItem -LiteralPath $runRoot -Force).Count -eq 0) {
        Remove-Item -LiteralPath $runRoot -Force
        $logsDeleted = $true
    }

    foreach ($name in $managedEnvironmentNames) {
        [Environment]::SetEnvironmentVariable($name, $previousEnvironment[$name], 'Process')
    }
    [Array]::Clear($keyBytes, 0, $keyBytes.Length)
}

if ($null -ne $failureCode) {
    throw $failureCode
}
if (-not $logsDeleted) {
    throw 'business_list_live.log_cleanup_incomplete'
}

if ($DownstreamOnly) {
    [PSCustomObject]@{
        stage = $stageValue
        status = 'downstream_passed'
        modelCalls = 0
        employeeSearch = 1
    }
    return
}

if ($PreflightOnly) {
    [PSCustomObject]@{ stage = $stageValue; status = 'preflight_passed'; modelCalls = 0 }
    return
}

$result = Get-Content -LiteralPath $evidence -Raw -Encoding UTF8 | ConvertFrom-Json
[PSCustomObject]@{
    stage = $stageValue
    status = $result.status
    cases = @($result.cases).Count
    queryPlanCalls = $result.counts.modelQueryPlan
    employeeSearch = $result.counts.employeeSearch
    employeeSemantic = $result.counts.employeeSemantic
    transactionSearch = $result.counts.transactionSearch
    evidence = $evidence
}
