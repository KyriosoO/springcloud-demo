#requires -Version 5.1

<#
.SYNOPSIS
Builds and starts every executable Spring service plus agent-runtime in dependency order.

.EXAMPLE
.\run-all-services.ps1

.EXAMPLE
$env:LLM_API_KEY = '<process-only secret>'
.\run-all-services.ps1 -ModelProvider deepseek -EnableKnowledge -EnableAgentInspection

.EXAMPLE
.\run-all-services.ps1 -PlanOnly

.EXAMPLE
.\run-all-services.ps1 -RestartManaged -ModelProvider deepseek -EnableKnowledge -EnableAgentInspection

.EXAMPLE
.\run-all-services.ps1 -ReuseExisting -SkipBuild
#>

[CmdletBinding()]
param(
    [ValidateSet('stub', 'deepseek')]
    [string]$ModelProvider = $(if ($env:AGENT_MODEL_PROVIDER) { $env:AGENT_MODEL_PROVIDER } else { 'stub' }),
    [switch]$EnableKnowledge,
    [string]$KnowledgeDomains = 'tax.policy,tax.law',
    [string]$KnowledgeBindingPath = '',
    [switch]$EnableAgentInspection,
    [switch]$SkipBuild,
    [switch]$SkipInfrastructureCheck,
    [switch]$ReuseExisting,
    [switch]$RestartManaged,
    [switch]$PlanOnly,
    [ValidateRange(10, 600)]
    [int]$StartupTimeoutSeconds = 180,
    [ValidateRange(1024, 65535)]
    [int]$AgentServicePort = 8092
)

$ErrorActionPreference = 'Stop'
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$Maven = Join-Path $PSScriptRoot 'mvnw.cmd'
$RuntimeRoot = Join-Path $RepoRoot 'agent-runtime'
$RuntimePython = Join-Path $RuntimeRoot '.venv\Scripts\python.exe'
$RuntimeContractVersion = '1'
$StateRoot = Join-Path ([IO.Path]::GetTempPath()) 'codex-service-center'
$RunRoot = Join-Path $StateRoot ('run-' + (Get-Date -Format 'yyyyMMdd-HHmmss') + '-' + $PID)
$LogRoot = Join-Path $RunRoot 'logs'
$StatePath = Join-Path $RunRoot 'started-services.json'
$ActiveStatePath = Join-Path $StateRoot 'active-services.json'
$StopScript = Join-Path $PSScriptRoot 'stop-all-services.ps1'
$knowledgeEnvironment = @{}
$esQueryArgs = @()

if ($EnableKnowledge) {
    if ([string]::IsNullOrWhiteSpace($KnowledgeBindingPath)) {
        $KnowledgeBindingPath = if (-not [string]::IsNullOrWhiteSpace($env:SERVICE_CENTER_KNOWLEDGE_BINDING_PATH)) {
            $env:SERVICE_CENTER_KNOWLEDGE_BINDING_PATH
        } else {
            Join-Path $PSScriptRoot 'knowledge-runtime-binding.v1.json'
        }
    }
    $resolvedBindingPath = (Resolve-Path -LiteralPath $KnowledgeBindingPath -ErrorAction Stop).Path
    $binding = Get-Content -Raw -LiteralPath $resolvedBindingPath | ConvertFrom-Json
    $expectedBindingFields = @(
        'schemaVersion', 'readAlias', 'expectedIndexName', 'expectedIndexUuid',
        'mappingVersion', 'policySnapshotId', 'lawSnapshotId'
    )
    $actualBindingFields = @($binding.PSObject.Properties.Name)
    $fieldDifference = @(Compare-Object $expectedBindingFields $actualBindingFields)
    if ($fieldDifference.Count -ne 0 -or [int]$binding.schemaVersion -ne 1) {
        throw "invalid Knowledge binding schema: $resolvedBindingPath"
    }
    foreach ($field in @('readAlias', 'expectedIndexName', 'expectedIndexUuid', 'mappingVersion')) {
        if ([string]::IsNullOrWhiteSpace([string]$binding.$field) -or
            [string]$binding.$field -notmatch '^[A-Za-z0-9._-]+$') {
            throw "invalid Knowledge binding field: $field"
        }
    }
    foreach ($field in @('policySnapshotId', 'lawSnapshotId')) {
        if ([string]$binding.$field -notmatch '^[0-9a-f]{64}$') {
            throw "invalid Knowledge binding field: $field"
        }
    }
    $knowledgeEnvironment = @{
        AGENT_KNOWLEDGE_READ_ALIAS = [string]$binding.readAlias
        AGENT_KNOWLEDGE_EXPECTED_INDEX_NAME = [string]$binding.expectedIndexName
        AGENT_KNOWLEDGE_EXPECTED_INDEX_UUID = [string]$binding.expectedIndexUuid
        AGENT_KNOWLEDGE_MAPPING_VERSION = [string]$binding.mappingVersion
        AGENT_KNOWLEDGE_POLICY_SNAPSHOT_ID = [string]$binding.policySnapshotId
        AGENT_KNOWLEDGE_LAW_SNAPSHOT_ID = [string]$binding.lawSnapshotId
    }
    $esQueryArgs = @('--spring.profiles.active=datasource,es,knowledge-live')
}

# 数组顺序即启动顺序。API、contracts、common模块参与构建，但不是独立进程。
$Services = @()
$Services += ,([pscustomobject]@{ Name = 'eureka-service'; Kind = 'java'; Port = 8761; DependsOn = @(); ReadyUrl = 'http://127.0.0.1:8761/'; Args = @() })
$Services += ,([pscustomobject]@{ Name = 'config-service'; Kind = 'java'; Port = 9888; DependsOn = @('eureka-service'); ReadyUrl = $null; Args = @() })
$Services += ,([pscustomobject]@{ Name = 'auth-service'; Kind = 'java'; Port = 8090; DependsOn = @('config-service'); ReadyUrl = 'http://127.0.0.1:8090/public/test'; Args = @() })
$Services += ,([pscustomobject]@{ Name = 'es-query-service'; Kind = 'java'; Port = 9201; DependsOn = @('config-service'); ReadyUrl = $null; KnowledgeEndpoint = $EnableKnowledge.IsPresent; Environment = $knowledgeEnvironment; Args = $esQueryArgs })
$Services += ,([pscustomobject]@{ Name = 'workflow-service'; Kind = 'java'; Port = 9100; DependsOn = @('config-service'); ReadyUrl = $null; Args = @() })
$Services += ,([pscustomobject]@{ Name = 'employee-service'; Kind = 'java'; Port = 9210; DependsOn = @('es-query-service', 'workflow-service'); ReadyUrl = $null; Args = @() })
$Services += ,([pscustomobject]@{ Name = 'mq-procedure-service'; Kind = 'java'; Port = 8182; DependsOn = @('config-service'); ReadyUrl = $null; Args = @() })
$Services += ,([pscustomobject]@{ Name = 'mq-consumer-service'; Kind = 'java'; Port = 8183; DependsOn = @('config-service'); ReadyUrl = $null; Args = @() })
$Services += ,([pscustomobject]@{ Name = 'm-service-1'; Kind = 'java'; Port = 8180; DependsOn = @('config-service'); ReadyUrl = $null; Args = @() })
$Services += ,([pscustomobject]@{ Name = 'm-service-2'; Kind = 'java'; Port = 8081; DependsOn = @('config-service'); ReadyUrl = $null; Args = @() })
$Services += ,([pscustomobject]@{ Name = 'openfeign-service'; Kind = 'java'; Port = 9000; DependsOn = @('m-service-1', 'm-service-2'); ReadyUrl = $null; Args = @() })
$Services += ,([pscustomobject]@{ Name = 'agent-runtime'; Kind = 'python'; Port = 8091; DependsOn = @('employee-service', 'mq-procedure-service'); ReadyUrl = 'http://127.0.0.1:8091/internal/health/ready'; Args = @() })
$agentServiceArgs = @(
    # Pin both processes to the same supported internal contract. This also
    # prevents an inherited blank AGENT_RUNTIME_CONTRACT_VERSION from winning
    # through Spring relaxed binding.
    "--agent.runtime.contract-version=$RuntimeContractVersion",
    "--agent.inspection.enabled=$($EnableAgentInspection.IsPresent.ToString().ToLowerInvariant())"
)
if ($PSBoundParameters.ContainsKey('AgentServicePort')) {
    $agentServiceArgs = @("--server.port=$AgentServicePort") + $agentServiceArgs
}
$Services += ,([pscustomobject]@{ Name = 'agent-service'; Kind = 'java'; Port = $AgentServicePort; DependsOn = @('auth-service', 'agent-runtime'); ReadyUrl = "http://127.0.0.1:$AgentServicePort/actuator/health/readiness"; EurekaApp = 'AGENT-SERVICE'; Args = $agentServiceArgs })
$Services += ,([pscustomobject]@{ Name = 'gateway-service'; Kind = 'java'; Port = 8888; DependsOn = @('agent-service'); ReadyUrl = $null; Args = @() })

$Infrastructure = @()
$Infrastructure += ,([pscustomobject]@{ Name = 'MySQL'; Port = 3306 })
$Infrastructure += ,([pscustomobject]@{ Name = 'Redis'; Port = 6379 })
$Infrastructure += ,([pscustomobject]@{ Name = 'Kafka'; Port = 9092 })
$Infrastructure += ,([pscustomobject]@{ Name = 'RocketMQ'; Port = 9876 })
$Infrastructure += ,([pscustomobject]@{ Name = 'Elasticsearch'; Port = 9200 })
$Infrastructure += ,([pscustomobject]@{ Name = 'BGE embedding'; Port = 8908 })
if ($EnableKnowledge) {
    $Infrastructure += ,([pscustomobject]@{ Name = 'BGE rerank'; Port = 8909 })
}

function Test-TcpPort {
    param([Parameter(Mandatory)] [int]$Port)
    $client = [Net.Sockets.TcpClient]::new()
    try {
        $pending = $client.BeginConnect('127.0.0.1', $Port, $null, $null)
        if (-not $pending.AsyncWaitHandle.WaitOne(800, $false)) {
            return $false
        }
        $client.EndConnect($pending)
        return $true
    } catch {
        return $false
    } finally {
        $client.Dispose()
    }
}

function Wait-ServiceReady {
    param(
        [Parameter(Mandatory)] [pscustomobject]$Service,
        [Diagnostics.Process]$Process
    )
    $deadline = (Get-Date).AddSeconds($StartupTimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        if ($null -ne $Process -and $Process.HasExited) {
            throw "$($Service.Name) exited with code $($Process.ExitCode); inspect $LogRoot"
        }
        if (Test-TcpPort $Service.Port) {
            if ([string]::IsNullOrWhiteSpace([string]$Service.ReadyUrl)) {
                Write-Host "READY  $($Service.Name) port=$($Service.Port)"
                return
            }
            try {
                $response = Invoke-WebRequest -UseBasicParsing -Uri $Service.ReadyUrl -TimeoutSec 3
                if ($response.StatusCode -ge 200 -and $response.StatusCode -lt 300) {
                    Write-Host "READY  $($Service.Name)"
                    return
                }
            } catch {
                # 端口已监听但应用尚未ready。
                $null = $_
            }
        }
        Start-Sleep -Seconds 2
    }
    throw "$($Service.Name) did not become ready within $StartupTimeoutSeconds seconds; inspect $LogRoot"
}

function Wait-EurekaRegistration {
    param([Parameter(Mandatory)] [pscustomobject]$Service)

    if (-not ($Service.PSObject.Properties.Name -contains 'EurekaApp') -or
        [string]::IsNullOrWhiteSpace([string]$Service.EurekaApp)) {
        return
    }

    $deadline = (Get-Date).AddSeconds($StartupTimeoutSeconds)
    $uri = "http://127.0.0.1:8761/eureka/apps/$($Service.EurekaApp)"
    while ((Get-Date) -lt $deadline) {
        try {
            $application = Invoke-RestMethod -Uri $uri -Headers @{ Accept = 'application/json' } -TimeoutSec 3
            $instances = @($application.application.instance)
            $matching = $instances | Where-Object {
                $registeredPort = if ($_.port -is [pscustomobject] -and $_.port.PSObject.Properties.Name -contains '$') {
                    [int]$_.port.'$'
                } elseif ($_.port -is [pscustomobject] -and $_.port.PSObject.Properties.Name -contains '#text') {
                    [int]$_.port.'#text'
                } else {
                    [int]$_.port
                }
                $_.status -eq 'UP' -and $registeredPort -eq $Service.Port
            }
            if ($matching) {
                Write-Host "READY  $($Service.Name) registered=$($Service.EurekaApp) port=$($Service.Port)"
                return
            }
        } catch {
            # Eureka returns 404 until the first matching instance registers.
            $null = $_
        }
        Start-Sleep -Milliseconds 500
    }

    throw "$($Service.Name) did not register as $($Service.EurekaApp) on port $($Service.Port) within $StartupTimeoutSeconds seconds"
}

function Wait-KnowledgeEndpoint {
    param([Parameter(Mandatory)] [pscustomobject]$Service)

    if (-not ($Service.PSObject.Properties.Name -contains 'KnowledgeEndpoint') -or
        -not [bool]$Service.KnowledgeEndpoint) {
        return
    }

    $deadline = (Get-Date).AddSeconds($StartupTimeoutSeconds)
    $uri = "http://127.0.0.1:$($Service.Port)/es/knowledge/search"
    while ((Get-Date) -lt $deadline) {
        try {
            $response = Invoke-WebRequest -UseBasicParsing -Uri $uri -Method Post `
                    -ContentType 'application/json' -Body '{}' -TimeoutSec 3
            $status = [int]$response.StatusCode
        } catch {
            $status = if ($_.Exception.Response) { [int]$_.Exception.Response.StatusCode } else { 0 }
        }
        if ($status -in @(401, 403)) {
            Write-Host "READY  $($Service.Name) Knowledge endpoint enabled"
            return
        }
        Start-Sleep -Milliseconds 500
    }

    throw "$($Service.Name) Knowledge endpoint was not enabled within $StartupTimeoutSeconds seconds"
}

function Invoke-Checked {
    param(
        [Parameter(Mandatory)] [string]$FilePath,
        [Parameter(Mandatory)] [string[]]$Arguments,
        [Parameter(Mandatory)] [string]$WorkingDirectory
    )
    Push-Location $WorkingDirectory
    try {
        & $FilePath @Arguments
        if ($LASTEXITCODE -ne 0) {
            throw "command failed with exit code $($LASTEXITCODE): $FilePath"
        }
    } finally {
        Pop-Location
    }
}

function Resolve-ServiceJar {
    param([Parameter(Mandatory)] [string]$Module)
    $target = Join-Path (Join-Path $RepoRoot $Module) 'target'
    $jars = @(Get-ChildItem -LiteralPath $target -Filter "$Module-*.jar" -File -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -notmatch '(-sources|-javadoc)\.jar$' -and $_.Name -notlike '*.jar.original' } |
        Sort-Object LastWriteTimeUtc -Descending)
    if ($jars.Count -eq 0) {
        throw "executable jar not found for $Module; run without -SkipBuild"
    }
    return $jars[0].FullName
}

function Start-WithEnvironment {
    param(
        [Parameter(Mandatory)] [string]$FilePath,
        [Parameter(Mandatory)] [string[]]$Arguments,
        [Parameter(Mandatory)] [string]$WorkingDirectory,
        [Parameter(Mandatory)] [string]$StandardOutput,
        [Parameter(Mandatory)] [string]$StandardError,
        [hashtable]$Environment = @{}
    )
    $previous = @{}
    try {
        foreach ($key in $Environment.Keys) {
            $currentValue = [Environment]::GetEnvironmentVariable($key, 'Process')
            $previous[$key] = [pscustomobject]@{
                Exists = $null -ne $currentValue
                Value = $currentValue
            }
            [Environment]::SetEnvironmentVariable($key, [string]$Environment[$key], 'Process')
        }
        $start = @{
            FilePath = $FilePath
            ArgumentList = $Arguments
            WorkingDirectory = $WorkingDirectory
            RedirectStandardOutput = $StandardOutput
            RedirectStandardError = $StandardError
            WindowStyle = 'Hidden'
            PassThru = $true
        }
        return Start-Process @start
    } finally {
        foreach ($key in $Environment.Keys) {
            $prior = $previous[$key]
            if ($prior.Exists) {
                [Environment]::SetEnvironmentVariable($key, [string]$prior.Value, 'Process')
            } else {
                Remove-Item -LiteralPath ("Env:{0}" -f $key) -ErrorAction SilentlyContinue
            }
        }
    }
}

function Write-JsonAtomically {
    param(
        [Parameter(Mandatory)] [string]$Path,
        [Parameter(Mandatory)] [string]$Content
    )
    $temporaryPath = "$Path.$PID.tmp"
    Set-Content -LiteralPath $temporaryPath -Value $Content -Encoding UTF8
    Move-Item -LiteralPath $temporaryPath -Destination $Path -Force
}

function Write-LauncherState {
    param([Parameter(Mandatory)] [System.Collections.IEnumerable]$Entries)
    $snapshot = [ordered]@{
        schemaVersion = 1
        repoRoot = $RepoRoot
        runRoot = $RunRoot
        updatedAtUtc = [DateTimeOffset]::UtcNow.ToString('o')
        services = @($Entries | ForEach-Object { $_ })
    }
    $json = $snapshot | ConvertTo-Json -Depth 4
    Write-JsonAtomically $StatePath $json
    Write-JsonAtomically $ActiveStatePath $json
}

function Install-Projects {
    if (-not (Test-Path $Maven) -or $null -eq (Get-Command java -ErrorAction SilentlyContinue)) {
        throw 'Maven wrapper or Java was not found'
    }
    Write-Host 'BUILD  Maven reactor (tests skipped)'
    Invoke-Checked $Maven @('--batch-mode', '-f', (Join-Path $PSScriptRoot 'pom.xml'), '-DskipTests', 'install') $PSScriptRoot

    # agent-service当前不在旧聚合pom的modules内。
    Write-Host 'BUILD  agent-service'
    Invoke-Checked $Maven @('--batch-mode', '-f', (Join-Path $RepoRoot 'agent-service\pom.xml'), '-DskipTests', 'package') $RepoRoot

    if (-not (Test-Path $RuntimePython)) {
        $py = Get-Command py -ErrorAction SilentlyContinue
        if ($null -eq $py) {
            throw 'Python launcher "py" was not found; Python 3.12 is required'
        }
        Write-Host 'BUILD  agent-runtime Python 3.12 virtual environment'
        Invoke-Checked $py.Source @('-3.12', '-m', 'venv', (Join-Path $RuntimeRoot '.venv')) $RuntimeRoot
    }
    Write-Host 'BUILD  install current agent-runtime'
    Invoke-Checked $RuntimePython @('-m', 'pip', 'install', '--disable-pip-version-check', '-e', $RuntimeRoot) $RuntimeRoot
}

function Assert-Plan {
    $seenNames = @{}
    $seenPorts = @{}
    foreach ($service in $Services) {
        if ($seenNames.ContainsKey($service.Name) -or $seenPorts.ContainsKey([string]$service.Port)) {
            throw "duplicate service name or port: $($service.Name):$($service.Port)"
        }
        foreach ($dependency in $service.DependsOn) {
            if (-not $seenNames.ContainsKey($dependency)) {
                throw "dependency must be listed first: $($service.Name) -> $dependency"
            }
        }
        $seenNames[$service.Name] = $true
        $seenPorts[[string]$service.Port] = $true
    }
}

function Assert-ServicePortsFree {
    $used = @($Services | Where-Object { Test-TcpPort $_.Port })
    if ($used.Count -gt 0) {
        throw "service ports already in use: $(($used | ForEach-Object { "$($_.Name):$($_.Port)" }) -join ', ')"
    }
}

Assert-Plan

if ($PlanOnly) {
    $Services | ForEach-Object {
        [pscustomobject]@{
            Order = [array]::IndexOf($Services, $_) + 1
            Service = $_.Name
            Kind = $_.Kind
            Port = $_.Port
            DependsOn = $_.DependsOn -join ', '
        }
    } | Format-Table -AutoSize
    exit 0
}

if ($EnableKnowledge -and $ModelProvider -ne 'deepseek') {
    throw 'Knowledge requires -ModelProvider deepseek'
}
if ($RestartManaged -and $ReuseExisting) {
    throw '-RestartManaged and -ReuseExisting cannot be used together'
}
if ($ReuseExisting -and -not $SkipBuild) {
    throw '-ReuseExisting requires -SkipBuild because running JAR files cannot be replaced safely'
}
if ($ModelProvider -eq 'deepseek' -and [string]::IsNullOrWhiteSpace($env:LLM_API_KEY)) {
    throw 'LLM_API_KEY is required for deepseek mode and must only be set in the current process environment'
}
if (-not $SkipInfrastructureCheck) {
    $missing = @($Infrastructure | Where-Object { -not (Test-TcpPort $_.Port) })
    if ($missing.Count -gt 0) {
        throw "external infrastructure is not ready: $(($missing | ForEach-Object { "$($_.Name):$($_.Port)" }) -join ', ')"
    }
}

if (-not $RestartManaged -and -not $ReuseExisting) {
    Assert-ServicePortsFree
}

if ($RestartManaged) {
    if (-not (Test-Path $StopScript)) {
        throw "managed service stop script not found: $StopScript"
    }
    & $StopScript
    Assert-ServicePortsFree
}

if ($SkipBuild) {
    if (-not (Test-Path $RuntimePython)) {
        throw "agent-runtime virtual environment not found: $RuntimePython"
    }
    foreach ($service in $Services | Where-Object { $_.Kind -eq 'java' }) {
        [void](Resolve-ServiceJar $service.Name)
    }
} else {
    Install-Projects
}

New-Item -ItemType Directory -Force -Path $LogRoot | Out-Null
$started = [System.Collections.ArrayList]::new()
Write-LauncherState $started

try {
    foreach ($service in $Services) {
        if (Test-TcpPort $service.Port) {
            Write-Host "REUSE  $($service.Name) port=$($service.Port)"
            [void]$started.Add([pscustomobject]@{
                name = $service.Name
                port = $service.Port
                pid = $null
                managed = $false
                processName = $null
                processStartTimeUtc = $null
            })
            Write-LauncherState $started
            Wait-ServiceReady $service $null
            Wait-KnowledgeEndpoint $service
            Wait-EurekaRegistration $service
            continue
        }

        $stdout = Join-Path $LogRoot "$($service.Name).out.log"
        $stderr = Join-Path $LogRoot "$($service.Name).err.log"
        if ($service.Kind -eq 'java') {
            $jar = Resolve-ServiceJar $service.Name
            $serviceEnvironment = if ($service.PSObject.Properties.Name -contains 'Environment') {
                [hashtable]$service.Environment
            } else {
                @{}
            }
            $process = Start-WithEnvironment 'java' (@('-jar', ('"{0}"' -f $jar)) + @($service.Args)) (Join-Path $RepoRoot $service.Name) $stdout $stderr $serviceEnvironment
        } else {
            $runtimeEnvironment = @{
                AGENT_RUNTIME_HOST = '127.0.0.1'
                AGENT_RUNTIME_PORT = '8091'
                AGENT_RUNTIME_CONTRACT_VERSION = $RuntimeContractVersion
                AGENT_MODEL_PROVIDER = $ModelProvider
                AGENT_EMPLOYEE_BASE_URL = 'http://127.0.0.1:9210'
                AGENT_TRANSACTION_BASE_URL = 'http://127.0.0.1:8182'
                AGENT_KNOWLEDGE_ENABLED = $EnableKnowledge.IsPresent.ToString().ToLowerInvariant()
            }
            if ($EnableKnowledge) {
                $runtimeEnvironment.AGENT_KNOWLEDGE_ENABLED_DOMAINS = $KnowledgeDomains
                $runtimeEnvironment.AGENT_KNOWLEDGE_ES_BASE_URL = 'http://127.0.0.1:9201'
                $runtimeEnvironment.AGENT_KNOWLEDGE_EMBEDDING_BASE_URL = 'http://127.0.0.1:8908'
                $runtimeEnvironment.AGENT_KNOWLEDGE_RERANK_BASE_URL = 'http://127.0.0.1:8909'
            }
            $process = Start-WithEnvironment $RuntimePython @('-m', 'agent_runtime.main') $RuntimeRoot $stdout $stderr $runtimeEnvironment
        }

        $process.Refresh()
        [void]$started.Add([pscustomobject]@{
            name = $service.Name
            port = $service.Port
            pid = $process.Id
            managed = $true
            processName = $process.ProcessName
            processStartTimeUtc = $process.StartTime.ToUniversalTime().ToString('o')
        })
        Write-LauncherState $started
        Write-Host "START  $($service.Name) port=$($service.Port) pid=$($process.Id)"
        Wait-ServiceReady $service $process
        Wait-KnowledgeEndpoint $service
        Wait-EurekaRegistration $service
    }
} catch {
    $startupError = $_
    Write-Warning "startup failed; stopping processes managed by this run only"
    try {
        & $StopScript -StatePath $StatePath
    } catch {
        Write-Warning "managed cleanup failed: $($_.Exception.Message); inspect $StatePath"
    }
    throw $startupError
}

Write-Host ''
Write-Host 'All repository Spring services and agent-runtime are ready.'
Write-Host 'Gateway:    http://127.0.0.1:8888'
Write-Host 'Agent page: http://127.0.0.1:8888/agent.html'
Write-Host "Logs:       $LogRoot"
Write-Host "PID state:  $StatePath"
Write-Host "Active state: $ActiveStatePath"
Write-Host 'Stop command: .\serviceCenter\stop-all-services.ps1'
if ($ModelProvider -eq 'stub') {
    Write-Warning 'stub mode only supports HTTP smoke tests; use deepseek mode for real QueryPlan generation.'
}
