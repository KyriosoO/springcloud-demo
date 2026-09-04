#requires -Version 5.1

<#
.SYNOPSIS
Stops only Spring and Python service processes previously started by run-all-services.ps1.

.DESCRIPTION
The script validates the recorded repository, PID, process name, process start
time, and (for legacy state) listening port before stopping anything. Reused or
externally managed services and external infrastructure are never stopped.

.EXAMPLE
.\stop-all-services.ps1

.EXAMPLE
.\stop-all-services.ps1 -WhatIf

.EXAMPLE
.\stop-all-services.ps1 -StatePath C:\Temp\codex-services-previous\started-services.json
#>

[CmdletBinding(SupportsShouldProcess = $true)]
param(
    [string]$StatePath,
    [ValidateRange(1, 60)]
    [int]$StopTimeoutSeconds = 15
)

$ErrorActionPreference = 'Stop'
$requestedWhatIf = $WhatIfPreference
$WhatIfPreference = $false
try {
    Import-Module CimCmdlets -ErrorAction Stop
} finally {
    $WhatIfPreference = $requestedWhatIf
}
$ExpectedRepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$StateRoot = Join-Path ([IO.Path]::GetTempPath()) 'codex-service-center'
$ActiveStatePath = Join-Path $StateRoot 'active-services.json'
$ExpectedProcessNames = @{
    'eureka-service' = 'java'
    'config-service' = 'java'
    'auth-service' = 'java'
    'es-query-service' = 'java'
    'workflow-service' = 'java'
    'employee-service' = 'java'
    'mq-procedure-service' = 'java'
    'mq-consumer-service' = 'java'
    'm-service-1' = 'java'
    'm-service-2' = 'java'
    'openfeign-service' = 'java'
    'agent-runtime' = 'python'
    'agent-service' = 'java'
    'gateway-service' = 'java'
}

function Resolve-StateFile {
    if (-not [string]::IsNullOrWhiteSpace($StatePath)) {
        if (-not (Test-Path -LiteralPath $StatePath -PathType Leaf)) {
            throw "service state file not found: $StatePath"
        }
        return (Resolve-Path -LiteralPath $StatePath).Path
    }

    if (Test-Path -LiteralPath $ActiveStatePath -PathType Leaf) {
        return (Resolve-Path -LiteralPath $ActiveStatePath).Path
    }

    $candidates = @()
    if (Test-Path -LiteralPath $StateRoot -PathType Container) {
        $candidates += @(Get-ChildItem -LiteralPath $StateRoot -Directory -Filter 'run-*' -ErrorAction SilentlyContinue |
            ForEach-Object { Get-Item -LiteralPath (Join-Path $_.FullName 'started-services.json') -ErrorAction SilentlyContinue })
    }
    $candidates += @(Get-ChildItem -LiteralPath ([IO.Path]::GetTempPath()) -Directory -Filter 'codex-services-*' -ErrorAction SilentlyContinue |
        ForEach-Object { Get-Item -LiteralPath (Join-Path $_.FullName 'started-services.json') -ErrorAction SilentlyContinue })
    $latest = $candidates | Sort-Object LastWriteTimeUtc -Descending | Select-Object -First 1
    if ($null -eq $latest) {
        return $null
    }
    Write-Warning "active state was not found; using latest recorded state: $($latest.FullName)"
    return $latest.FullName
}

function Read-ServiceState {
    param([Parameter(Mandatory)] [string]$Path)
    $raw = Get-Content -LiteralPath $Path -Raw | ConvertFrom-Json
    $isEnvelope = $raw -is [pscustomobject] -and
        $raw.PSObject.Properties.Name -contains 'schemaVersion' -and
        $raw.PSObject.Properties.Name -contains 'services'
    if ($isEnvelope) {
        if ([int]$raw.schemaVersion -ne 1) {
            throw "unsupported service state schema: $($raw.schemaVersion)"
        }
        if (-not [string]::IsNullOrWhiteSpace([string]$raw.repoRoot) -and
            -not [string]::Equals([string]$raw.repoRoot, $ExpectedRepoRoot, [StringComparison]::OrdinalIgnoreCase)) {
            throw "service state belongs to another repository: $($raw.repoRoot)"
        }
        return [pscustomobject]@{
            legacy = $false
            runRoot = [string]$raw.runRoot
            services = @($raw.services)
        }
    }
    return [pscustomobject]@{
        legacy = $true
        runRoot = $null
        services = @($raw)
    }
}

function Test-ExpectedProcessName {
    param(
        [Parameter(Mandatory)] [string]$Actual,
        [Parameter(Mandatory)] [pscustomobject]$Entry
    )
    $serviceName = [string]$Entry.name
    if (-not $ExpectedProcessNames.ContainsKey($serviceName)) {
        return $false
    }
    $expected = [string]$ExpectedProcessNames[$serviceName]
    if (-not [string]::IsNullOrWhiteSpace([string]$Entry.processName) -and
        -not [string]::Equals([string]$Entry.processName, $expected, [StringComparison]::OrdinalIgnoreCase)) {
        return $false
    }
    return [string]::Equals($Actual, $expected, [StringComparison]::OrdinalIgnoreCase)
}

function Test-LegacyProcessIdentity {
    param(
        [Parameter(Mandatory)] [int]$ProcessId,
        [Parameter(Mandatory)] [pscustomobject]$Entry
    )
    $instance = Get-CimInstance Win32_Process -Filter "ProcessId = $ProcessId" -ErrorAction SilentlyContinue
    if ($null -eq $instance -or [string]::IsNullOrWhiteSpace([string]$instance.CommandLine)) {
        return $false
    }
    if ([string]$Entry.name -eq 'agent-runtime') {
        $runtimePython = Join-Path $ExpectedRepoRoot 'agent-runtime\.venv\Scripts\python.exe'
        return [string]::Equals(
            [string]$instance.ExecutablePath,
            $runtimePython,
            [StringComparison]::OrdinalIgnoreCase
        ) -and [string]$instance.CommandLine -match '(?i)(^|\s)-m\s+agent_runtime\.main(\s|$)'
    }
    $jarMarker = Join-Path $ExpectedRepoRoot "$($Entry.name)\target\$($Entry.name)-"
    return [string]$instance.CommandLine -match '(?i)(^|\s)-jar(\s|$)' -and
        [string]$instance.CommandLine -like "*$jarMarker*"
}

function Get-ProcessTreeIds {
    param([Parameter(Mandatory)] [int]$RootProcessId)
    $all = @(Get-CimInstance Win32_Process | Select-Object ProcessId, ParentProcessId)
    $ordered = [System.Collections.ArrayList]::new()
    [void]$ordered.Add($RootProcessId)
    for ($index = 0; $index -lt $ordered.Count; $index += 1) {
        $parentId = [int]$ordered[$index]
        foreach ($child in @($all | Where-Object { [int]$_.ParentProcessId -eq $parentId })) {
            if (-not $ordered.Contains([int]$child.ProcessId)) {
                [void]$ordered.Add([int]$child.ProcessId)
            }
        }
    }
    $result = @($ordered | ForEach-Object { [int]$_ })
    [Array]::Reverse($result)
    return $result
}

function Test-ExpectedStartTime {
    param(
        [Parameter(Mandatory)] [Diagnostics.Process]$Process,
        [Parameter(Mandatory)] [object]$Expected
    )
    if ($Expected -is [DateTimeOffset]) {
        $expectedTime = [DateTimeOffset]$Expected
    } elseif ($Expected -is [DateTime]) {
        # PowerShell 7 automatically converts ISO JSON timestamps to DateTime.
        # Preserve its Kind instead of stringifying it with the current culture,
        # which would discard the UTC marker and create an eight-hour mismatch.
        $expectedTime = [DateTimeOffset]([DateTime]$Expected)
    } else {
        $expectedTime = [DateTimeOffset]::Parse(
            [string]$Expected,
            [Globalization.CultureInfo]::InvariantCulture,
            [Globalization.DateTimeStyles]::RoundtripKind
        )
    }
    $actualTime = [DateTimeOffset]$Process.StartTime.ToUniversalTime()
    return [Math]::Abs(($actualTime - $expectedTime).TotalSeconds) -le 1
}

function Test-ActiveStateMatches {
    param(
        [Parameter(Mandatory)] [string]$ResolvedStatePath,
        [Parameter(Mandatory)] [pscustomobject]$State
    )
    if (-not (Test-Path -LiteralPath $ActiveStatePath -PathType Leaf)) {
        return $false
    }
    if ([string]::Equals(
        (Resolve-Path -LiteralPath $ActiveStatePath).Path,
        $ResolvedStatePath,
        [StringComparison]::OrdinalIgnoreCase
    )) {
        return $true
    }
    if ([string]::IsNullOrWhiteSpace([string]$State.runRoot)) {
        return $false
    }
    try {
        $active = Get-Content -LiteralPath $ActiveStatePath -Raw | ConvertFrom-Json
        return [string]::Equals(
            [string]$active.runRoot,
            [string]$State.runRoot,
            [StringComparison]::OrdinalIgnoreCase
        )
    } catch {
        return $false
    }
}

$resolvedStatePath = Resolve-StateFile
if ($null -eq $resolvedStatePath) {
    Write-Host 'No managed service state was found; nothing to stop.'
    return
}

$state = Read-ServiceState $resolvedStatePath
$targets = [System.Collections.ArrayList]::new()
$unmanagedCount = 0

foreach ($entry in @($state.services)) {
    if (-not [bool]$entry.managed -or $null -eq $entry.pid) {
        $unmanagedCount += 1
        continue
    }
    $process = Get-Process -Id ([int]$entry.pid) -ErrorAction SilentlyContinue
    if ($null -eq $process) {
        Write-Host "NOT RUNNING  $($entry.name) pid=$($entry.pid)"
        continue
    }
    if (-not (Test-ExpectedProcessName $process.ProcessName $entry)) {
        throw "refusing to stop PID $($entry.pid): process name mismatch for $($entry.name)"
    }
    if (-not [string]::IsNullOrWhiteSpace([string]$entry.processStartTimeUtc)) {
        if (-not (Test-ExpectedStartTime $process $entry.processStartTimeUtc)) {
            throw "refusing to stop PID $($entry.pid): process start time mismatch for $($entry.name)"
        }
    } elseif (-not (Test-LegacyProcessIdentity ([int]$entry.pid) $entry)) {
        throw "refusing to stop legacy PID $($entry.pid): command identity mismatch for $($entry.name)"
    }
    [void]$targets.Add([pscustomobject]@{ entry = $entry; process = $process })
}

$allApplied = $true
$stoppedCount = 0
for ($index = $targets.Count - 1; $index -ge 0; $index -= 1) {
    $target = $targets[$index]
    $entry = $target.entry
    $process = Get-Process -Id ([int]$entry.pid) -ErrorAction SilentlyContinue
    if ($null -eq $process) {
        continue
    }
    if ($PSCmdlet.ShouldProcess("$($entry.name) pid=$($entry.pid) port=$($entry.port)", 'Stop managed service')) {
        foreach ($processId in @(Get-ProcessTreeIds ([int]$entry.pid))) {
            if ($null -ne (Get-Process -Id $processId -ErrorAction SilentlyContinue)) {
                Stop-Process -Id $processId -ErrorAction Stop
            }
        }
        if (-not $process.WaitForExit($StopTimeoutSeconds * 1000)) {
            throw "managed service did not stop within $StopTimeoutSeconds seconds: $($entry.name) pid=$($entry.pid)"
        }
        $stoppedCount += 1
        Write-Host "STOPPED  $($entry.name) pid=$($entry.pid)"
    } else {
        $allApplied = $false
    }
}

if ($allApplied -and (Test-ActiveStateMatches $resolvedStatePath $state)) {
    Remove-Item -LiteralPath $ActiveStatePath -Force
}

Write-Host "Managed services stopped: $stoppedCount; unmanaged/reused services skipped: $unmanagedCount"
