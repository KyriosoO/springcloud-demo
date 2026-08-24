[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$FrozenHead,
    [Parameter(Mandatory = $true)][string]$RunId,
    [Parameter(Mandatory = $true)][string]$ManifestSha256,
    [Parameter(Mandatory = $true)][string]$AuthorizationReference,
    [Parameter(Mandatory = $true)][int]$MaximumModelCalls,
    [string]$RepositoryRoot = (Split-Path -Parent (Split-Path -Parent $PSScriptRoot))
)

$ErrorActionPreference = 'Stop'
$expectedRunId = 'business-query-plan-live-v1-20260824-candidate-01'
$expectedAuthorizationReference = 'P3_00:GATE-065'
$expectedMaximumModelCalls = 6
$repository = [IO.Path]::GetFullPath($RepositoryRoot)
if ($repository -cne 'D:\codex') {
    throw 'business_query_plan_live.repository_invalid'
}
if (
    $FrozenHead -notmatch '^[0-9a-f]{40}$' -or
    $RunId -cne $expectedRunId -or
    $ManifestSha256 -notmatch '^[0-9a-f]{64}$' -or
    $AuthorizationReference -cne $expectedAuthorizationReference -or
    $MaximumModelCalls -ne $expectedMaximumModelCalls
) {
    throw 'business_query_plan_live.authorization_binding_invalid'
}

$runtimeRoot = Join-Path $repository 'agent-runtime'
$manifestPath = Join-Path $runtimeRoot 'tests\system_e2e\live\evidence\business-query-plan-live-v1-20260824-candidate-01.manifest.json'
$resultRoot = Join-Path $runtimeRoot "tests\system_e2e\live\results\$expectedRunId"
if (-not (Test-Path -LiteralPath $manifestPath)) {
    throw 'business_query_plan_live.manifest_missing'
}
if ((Get-FileHash -LiteralPath $manifestPath -Algorithm SHA256).Hash.ToLowerInvariant() -cne $ManifestSha256) {
    throw 'business_query_plan_live.manifest_hash_mismatch'
}
if ((git -C $repository rev-parse HEAD).Trim() -cne $FrozenHead) {
    throw 'business_query_plan_live.head_mismatch'
}
if (git -C $repository status --porcelain --untracked-files=all) {
    throw 'business_query_plan_live.worktree_dirty'
}
if (Test-Path -LiteralPath $resultRoot) {
    throw 'business_query_plan_live.authorization_consumed'
}

$requiredNames = @(
    'LLM_API_KEY',
    'BUSINESS_QUERY_PLAN_LIVE_EMPLOYEE_IDENTIFIER',
    'BUSINESS_QUERY_PLAN_LIVE_ADMIN_JWT',
    'BUSINESS_QUERY_PLAN_LIVE_DENIED_JWT',
    'BUSINESS_QUERY_PLAN_LIVE_EMPLOYEE_BASE_URL',
    'BUSINESS_QUERY_PLAN_LIVE_TRANSACTION_BASE_URL'
)
foreach ($name in $requiredNames) {
    if ([string]::IsNullOrWhiteSpace([Environment]::GetEnvironmentVariable($name, 'Process'))) {
        throw "business_query_plan_live.environment_missing:$name"
    }
}
if (
    [Environment]::GetEnvironmentVariable('BUSINESS_QUERY_PLAN_LIVE_EMPLOYEE_BASE_URL', 'Process') -cne 'http://127.0.0.1:9210' -or
    [Environment]::GetEnvironmentVariable('BUSINESS_QUERY_PLAN_LIVE_TRANSACTION_BASE_URL', 'Process') -cne 'http://127.0.0.1:8182'
) {
    throw 'business_query_plan_live.endpoint_invalid'
}

$python = (Get-Command python.exe -ErrorAction Stop).Source
$tempRoot = [IO.Path]::GetFullPath([IO.Path]::GetTempPath())
$runRoot = [IO.Path]::GetFullPath((Join-Path $tempRoot "business-query-plan-live-$([Guid]::NewGuid().ToString('N'))"))
if (
    -not $runRoot.StartsWith($tempRoot, [StringComparison]::OrdinalIgnoreCase) -or
    -not [IO.Path]::GetFileName($runRoot).StartsWith('business-query-plan-live-', [StringComparison]::Ordinal)
) {
    throw 'business_query_plan_live.temp_path_invalid'
}
New-Item -ItemType Directory -Path $runRoot | Out-Null
$stdoutPath = Join-Path $runRoot 'runner.out.log'
$stderrPath = Join-Path $runRoot 'runner.err.log'
$environmentNames = @(
    'PYTHONPATH',
    'AGENT_MODEL_PROVIDER',
    'AGENT_MODEL_MAX_CONCURRENCY',
    'BUSINESS_QUERY_PLAN_LIVE_ENABLE',
    'BUSINESS_QUERY_PLAN_LIVE_RUN_ID',
    'BUSINESS_QUERY_PLAN_LIVE_MANIFEST_PATH',
    'BUSINESS_QUERY_PLAN_LIVE_MANIFEST_SHA256',
    'BUSINESS_QUERY_PLAN_LIVE_AUTHORIZATION_REFERENCE',
    'BUSINESS_QUERY_PLAN_LIVE_FROZEN_HEAD',
    'BUSINESS_QUERY_PLAN_LIVE_RESULT_DIR'
)
$snapshot = @{}
foreach ($name in $environmentNames) {
    $snapshot[$name] = [Environment]::GetEnvironmentVariable($name, 'Process')
}

try {
    $env:PYTHONPATH = "$(Join-Path $runtimeRoot 'src');$runtimeRoot"
    $env:AGENT_MODEL_PROVIDER = 'deepseek'
    $env:AGENT_MODEL_MAX_CONCURRENCY = '1'
    $env:BUSINESS_QUERY_PLAN_LIVE_ENABLE = '1'
    $env:BUSINESS_QUERY_PLAN_LIVE_RUN_ID = $RunId
    $env:BUSINESS_QUERY_PLAN_LIVE_MANIFEST_PATH = $manifestPath
    $env:BUSINESS_QUERY_PLAN_LIVE_MANIFEST_SHA256 = $ManifestSha256
    $env:BUSINESS_QUERY_PLAN_LIVE_AUTHORIZATION_REFERENCE = $AuthorizationReference
    $env:BUSINESS_QUERY_PLAN_LIVE_FROZEN_HEAD = $FrozenHead
    $env:BUSINESS_QUERY_PLAN_LIVE_RESULT_DIR = $resultRoot

    $process = Start-Process -FilePath $python -ArgumentList @(
        '-m', 'tests.system_e2e.business_query_plan_live_runner'
    ) -WorkingDirectory $runtimeRoot -NoNewWindow -Wait -PassThru -RedirectStandardOutput $stdoutPath -RedirectStandardError $stderrPath
    $combined = @()
    if (Test-Path -LiteralPath $stdoutPath) { $combined += Get-Content -LiteralPath $stdoutPath -Raw -Encoding UTF8 }
    if (Test-Path -LiteralPath $stderrPath) { $combined += Get-Content -LiteralPath $stderrPath -Raw -Encoding UTF8 }
    $rawLogs = $combined -join "`n"
    foreach ($name in $requiredNames[0..3]) {
        $sensitive = [Environment]::GetEnvironmentVariable($name, 'Process')
        if (-not [string]::IsNullOrEmpty($sensitive) -and $rawLogs.Contains($sensitive, [StringComparison]::Ordinal)) {
            throw 'business_query_plan_live.log_leak'
        }
    }
    if ($process.ExitCode -ne 0) {
        throw 'business_query_plan_live.execution_failed'
    }
    Write-Output "status=completed"
    Write-Output "result=$resultRoot\result.json"
}
finally {
    foreach ($name in $environmentNames) {
        [Environment]::SetEnvironmentVariable($name, $snapshot[$name], 'Process')
    }
    if (Test-Path -LiteralPath $runRoot) {
        Remove-Item -LiteralPath $runRoot -Recurse -Force
    }
}
