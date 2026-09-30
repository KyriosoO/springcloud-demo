[CmdletBinding(DefaultParameterSetName = 'Prepare')]
param(
    [Parameter(Mandatory = $true)][string]$RunDirectory,
    [Parameter(Mandatory = $true, ParameterSetName = 'Prepare')][switch]$PrepareOnly,
    [Parameter(Mandatory = $true, ParameterSetName = 'Bind')][switch]$BindSourceMap,
    [Parameter(Mandatory = $true, ParameterSetName = 'Compare')][switch]$ExecuteOnce,
    [Parameter(Mandatory = $true, ParameterSetName = 'Startup')][switch]$StartupPreflightOnly,
    [Parameter(Mandatory = $true, ParameterSetName = 'Reuse')][switch]$PrepareReuse,
    [Parameter(Mandatory = $true, ParameterSetName = 'Compare')]
    [Parameter(Mandatory = $true, ParameterSetName = 'Startup')][ValidateRange(1025, 65535)][int]$BaselinePort,
    [Parameter(Mandatory = $true, ParameterSetName = 'Compare')]
    [Parameter(Mandatory = $true, ParameterSetName = 'Startup')][ValidateRange(1025, 65535)][int]$CandidatePort,
    [Parameter(Mandatory = $true, ParameterSetName = 'Compare')]
    [Parameter(Mandatory = $true, ParameterSetName = 'Startup')][ValidateRange(1025, 65535)][int]$BaselineProxyPort,
    [Parameter(Mandatory = $true, ParameterSetName = 'Compare')]
    [Parameter(Mandatory = $true, ParameterSetName = 'Startup')][ValidateRange(1025, 65535)][int]$CandidateProxyPort
)

$ErrorActionPreference = 'Stop'
$repo = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..'))
$runtime = Join-Path $repo 'agent-runtime'
$pythonProject = if ($ExecuteOnce -or $StartupPreflightOnly -or $PrepareReuse) { 'agent-runtime' } else { 'knowledge-corpus-tools' }
$python = Join-Path $repo "$pythonProject\.venv\Scripts\python.exe"
$run = [IO.Path]::GetFullPath($RunDirectory)
if (-not (Test-Path -LiteralPath $python -PathType Leaf) -or
    ($PrepareReuse -and ((Test-Path -LiteralPath $run) -or
        -not (Test-Path -LiteralPath ([IO.Path]::GetDirectoryName($run)) -PathType Container))) -or
    (-not $PrepareReuse -and -not (Test-Path -LiteralPath $run -PathType Container))) {
    throw 'knowledge.b.launch_preflight_invalid'
}

$previousPath = [Environment]::GetEnvironmentVariable('PYTHONPATH', 'Process')
try {
    $env:PYTHONPATH = 'src'
    $arguments = @('-m', 'tests.evaluation.knowledge.rebuild_b_local_runner',
                   '--run-directory', $run)
    if ($PrepareReuse) {
        $arguments += '--prepare-reuse'
    }
    elseif ($PrepareOnly) {
        $arguments += '--prepare-only'
    }
    elseif ($BindSourceMap) {
        $arguments += '--bind-source-map'
    }
    else {
        $mode = if ($StartupPreflightOnly) { '--startup-preflight-only' } else { '--execute-once' }
        $arguments += @($mode, '--baseline-port', [string]$BaselinePort,
                        '--candidate-port', [string]$CandidatePort,
                        '--baseline-proxy-port', [string]$BaselineProxyPort,
                        '--candidate-proxy-port', [string]$CandidateProxyPort)
    }
    Push-Location -LiteralPath $runtime
    try {
        & $python @arguments
        if ($LASTEXITCODE -ne 0) {
            throw "knowledge.b.run_failed:$LASTEXITCODE"
        }
    }
    finally {
        Pop-Location
    }
}
finally {
    [Environment]::SetEnvironmentVariable('PYTHONPATH', $previousPath, 'Process')
}
