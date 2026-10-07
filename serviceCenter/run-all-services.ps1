#requires -Version 5.1

<#
.SYNOPSIS
Builds and starts every executable Spring service in dependency order.

.EXAMPLE
.\run-all-services.ps1

.EXAMPLE
.\run-all-services.ps1 -PlanOnly

.EXAMPLE
.\run-all-services.ps1 -RestartManaged

.EXAMPLE
.\run-all-services.ps1 -ReuseExisting -SkipBuild
#>

[CmdletBinding()]
param(
    [switch]$SkipBuild,
    [switch]$SkipInfrastructureCheck,
    [switch]$ReuseExisting,
    [switch]$RestartManaged,
    [switch]$PlanOnly,
    [ValidateRange(10, 600)]
    [int]$StartupTimeoutSeconds = 180
)

$ErrorActionPreference = 'Stop'
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$Maven = Join-Path $PSScriptRoot 'mvnw.cmd'
$StateRoot = Join-Path ([IO.Path]::GetTempPath()) 'codex-service-center'
$RunRoot = Join-Path $StateRoot ('run-' + (Get-Date -Format 'yyyyMMdd-HHmmss') + '-' + $PID)
$LogRoot = Join-Path $RunRoot 'logs'
$StatePath = Join-Path $RunRoot 'started-services.json'
$ActiveStatePath = Join-Path $StateRoot 'active-services.json'
$StopScript = Join-Path $PSScriptRoot 'stop-all-services.ps1'
# 数组顺序即启动顺序。API、contracts、common模块参与构建，但不是独立进程。
$Services = @()
$Services += ,([pscustomobject]@{ Name = 'eureka-service'; Kind = 'java'; Port = 8761; DependsOn = @(); ReadyUrl = 'http://127.0.0.1:8761/'; Args = @() })
$Services += ,([pscustomobject]@{ Name = 'config-service'; Kind = 'java'; Port = 9888; DependsOn = @('eureka-service'); ReadyUrl = $null; Args = @() })
$Services += ,([pscustomobject]@{ Name = 'auth-service'; Kind = 'java'; Port = 8090; DependsOn = @('config-service'); ReadyUrl = 'http://127.0.0.1:8090/public/test'; Args = @() })
$Services += ,([pscustomobject]@{ Name = 'es-query-service'; Kind = 'java'; Port = 9201; DependsOn = @('config-service'); ReadyUrl = $null; Args = @() })
$Services += ,([pscustomobject]@{ Name = 'workflow-service'; Kind = 'java'; Port = 9100; DependsOn = @('config-service'); ReadyUrl = $null; Args = @() })
$Services += ,([pscustomobject]@{ Name = 'employee-service'; Kind = 'java'; Port = 9210; DependsOn = @('es-query-service', 'workflow-service'); ReadyUrl = $null; Args = @() })
$Services += ,([pscustomobject]@{ Name = 'mq-procedure-service'; Kind = 'java'; Port = 8182; DependsOn = @('config-service'); ReadyUrl = $null; Args = @() })
$Services += ,([pscustomobject]@{ Name = 'mq-consumer-service'; Kind = 'java'; Port = 8183; DependsOn = @('config-service'); ReadyUrl = $null; Args = @() })
$Services += ,([pscustomobject]@{ Name = 'm-service-1'; Kind = 'java'; Port = 8180; DependsOn = @('config-service'); ReadyUrl = $null; Args = @() })
$Services += ,([pscustomobject]@{ Name = 'm-service-2'; Kind = 'java'; Port = 8081; DependsOn = @('config-service'); ReadyUrl = $null; Args = @() })
$Services += ,([pscustomobject]@{ Name = 'openfeign-service'; Kind = 'java'; Port = 9000; DependsOn = @('m-service-1', 'm-service-2'); ReadyUrl = $null; Args = @() })
$Services += ,([pscustomobject]@{ Name = 'gateway-service'; Kind = 'java'; Port = 8888; DependsOn = @('auth-service'); ReadyUrl = $null; Args = @() })

$Infrastructure = @()
$Infrastructure += ,([pscustomobject]@{ Name = 'MySQL'; Port = 3306 })
$Infrastructure += ,([pscustomobject]@{ Name = 'Redis'; Port = 6379 })
$Infrastructure += ,([pscustomobject]@{ Name = 'Kafka'; Port = 9092 })
$Infrastructure += ,([pscustomobject]@{ Name = 'RocketMQ'; Port = 9876 })
$Infrastructure += ,([pscustomobject]@{ Name = 'Elasticsearch'; Port = 9200 })
$Infrastructure += ,([pscustomobject]@{ Name = 'BGE embedding'; Port = 8908 })

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

if ($RestartManaged -and $ReuseExisting) {
    throw '-RestartManaged and -ReuseExisting cannot be used together'
}
if ($ReuseExisting -and -not $SkipBuild) {
    throw '-ReuseExisting requires -SkipBuild because running JAR files cannot be replaced safely'
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
            continue
        }

        $stdout = Join-Path $LogRoot "$($service.Name).out.log"
        $stderr = Join-Path $LogRoot "$($service.Name).err.log"
        $jar = Resolve-ServiceJar $service.Name
        $serviceEnvironment = if ($service.PSObject.Properties.Name -contains 'Environment') {
            [hashtable]$service.Environment
        } else {
            @{}
        }
        $process = Start-WithEnvironment 'java' (@('-jar', ('"{0}"' -f $jar)) + @($service.Args)) (Join-Path $RepoRoot $service.Name) $stdout $stderr $serviceEnvironment

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
Write-Host 'All repository Spring services are ready.'
Write-Host 'Gateway:    http://127.0.0.1:8888'
Write-Host "Logs:       $LogRoot"
Write-Host "PID state:  $StatePath"
Write-Host "Active state: $ActiveStatePath"
Write-Host 'Stop command: .\serviceCenter\stop-all-services.ps1'
