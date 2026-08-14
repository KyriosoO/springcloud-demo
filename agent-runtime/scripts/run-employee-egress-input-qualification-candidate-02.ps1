[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$ManifestSha256,
    [string]$RunId = 'employee-egress-input-qualification-v2-20260814-candidate-02',
    [string]$AuthorizationReference = 'P3_00:GATE-049',
    [string]$RepositoryRoot = (Split-Path -Parent (Split-Path -Parent $PSScriptRoot))
)

$ErrorActionPreference = 'Stop'
$expectedRunId = 'employee-egress-input-qualification-v2-20260814-candidate-02'
$expectedAuthorizationReference = 'P3_00:GATE-049'
$repository = [IO.Path]::GetFullPath($RepositoryRoot)
if ($repository -cne 'D:\codex') {
    throw 'employee.egress_input_qualification_v2_repository_invalid'
}
$evidenceDirectory = Join-Path $repository 'agent-runtime\tests\integration\adapters\employee\evidence'
$manifestPath = Join-Path $evidenceDirectory "$expectedRunId.manifest.json"
$authorizationPath = Join-Path $evidenceDirectory "$expectedRunId.authorization.json"
$lifecyclePath = Join-Path $evidenceDirectory "$expectedRunId.lifecycle.jsonl"
$resultPath = Join-Path $evidenceDirectory "$expectedRunId.result.json"

if ($RunId -cne $expectedRunId -or $AuthorizationReference -cne $expectedAuthorizationReference -or
        $ManifestSha256 -notmatch '^[0-9a-f]{64}$' -or
        -not (Test-Path -LiteralPath $manifestPath) -or
        -not (Test-Path -LiteralPath $authorizationPath)) {
    throw 'employee.egress_input_qualification_v2_binding_invalid'
}
$actualManifestSha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $manifestPath).Hash.ToLowerInvariant()
$manifest = Get-Content -LiteralPath $manifestPath -Raw -Encoding UTF8 | ConvertFrom-Json
$authorization = Get-Content -LiteralPath $authorizationPath -Raw -Encoding UTF8 | ConvertFrom-Json
if ($actualManifestSha256 -cne $ManifestSha256 -or
        $manifest.schemaVersion -ne 2 -or $manifest.status -cne 'prepared_unconsumed' -or
        $manifest.preparationWorkPackageId -cne 'WP-EMP-EGRESS-INPUT-QUALIFY-02-PREP' -or
        $manifest.workPackageId -cne 'WP-EMP-EGRESS-INPUT-QUALIFY-02' -or
        $manifest.gateId -cne 'GATE-049' -or $manifest.runId -cne $expectedRunId -or
        $manifest.authorizationReference -cne $expectedAuthorizationReference -or
        $manifest.executionBoundary.databaseSelectionMaximumRows -ne 1 -or
        $manifest.executionBoundary.employeeDetailMaximumRequests -ne 1 -or
        $manifest.executionBoundary.modelMaximumCalls -ne 0 -or
        $manifest.executionBoundary.retryAllowed -ne $false -or
        $manifest.executionBoundary.resumeAllowed -ne $false -or
        $manifest.executionBoundary.liveExecutionAuthorized -ne $false -or
        $authorization.schemaVersion -ne 2 -or $authorization.status -cne 'prepared_unconsumed' -or
        $authorization.preparationWorkPackageId -cne 'WP-EMP-EGRESS-INPUT-QUALIFY-02-PREP' -or
        $authorization.workPackageId -cne 'WP-EMP-EGRESS-INPUT-QUALIFY-02' -or
        $authorization.gateId -cne 'GATE-049' -or $authorization.runId -cne $expectedRunId -or
        $authorization.manifestSha256 -cne $ManifestSha256 -or
        $authorization.authorizationReference -cne $expectedAuthorizationReference -or
        $authorization.databaseSelectionMaximumRows -ne 1 -or
        $authorization.employeeDetailMaximumRequests -ne 1 -or
        $authorization.modelMaximumCalls -ne 0 -or
        $authorization.retryAllowed -ne $false -or $authorization.resumeAllowed -ne $false -or
        $authorization.liveExecutionAuthorized -ne $false -or
        (Test-Path -LiteralPath $lifecyclePath) -or (Test-Path -LiteralPath $resultPath)) {
    throw 'employee.egress_input_qualification_v2_binding_invalid'
}

$repositoryPrefix = $repository + [IO.Path]::DirectorySeparatorChar
$boundAssets = @($manifest.assetHashes) + @($manifest.employeeEgressHistory) +
    @($manifest.retiredQualificationRun.assetHashes)
foreach ($asset in $boundAssets) {
    $assetPath = [IO.Path]::GetFullPath((Join-Path $repository ([string]$asset.path)))
    if (-not $assetPath.StartsWith($repositoryPrefix, [StringComparison]::OrdinalIgnoreCase) -or
            -not (Test-Path -LiteralPath $assetPath) -or
            (Get-FileHash -Algorithm SHA256 -LiteralPath $assetPath).Hash.ToLowerInvariant() -cne
                [string]$asset.sha256) {
        throw 'employee.egress_input_qualification_v2_asset_hash_invalid'
    }
}

# This candidate is frozen for a separately bound GATE-049 execution. Preparation never reaches here.
if ([Environment]::GetEnvironmentVariable('RUN_EMPLOYEE_EGRESS_INPUT_QUALIFY_V2', 'Process') -cne '1') {
    throw 'employee.egress_input_qualification_v2_live_not_authorized'
}

$adminJwt = [Environment]::GetEnvironmentVariable(
    'EMPLOYEE_EGRESS_INPUT_QUALIFY_V2_ADMIN_JWT',
    'Process'
)
$hmac = [Environment]::GetEnvironmentVariable('COMMON_SECURITY_JWT_HMAC_KEY_ACTIVE', 'Process')
if ([string]::IsNullOrWhiteSpace($adminJwt) -or [string]::IsNullOrWhiteSpace($hmac)) {
    throw 'employee.egress_input_qualification_v2_environment_missing'
}

$python = (Get-Command python.exe -ErrorAction Stop).Source
$maven = (Get-Command mvn.cmd -ErrorAction Stop).Source
$tempRoot = [IO.Path]::GetFullPath([IO.Path]::GetTempPath())
$runRoot = [IO.Path]::GetFullPath((Join-Path $tempRoot "employee-input-qualification-v2-$([Guid]::NewGuid().ToString('N'))"))
if (-not $runRoot.StartsWith($tempRoot, [StringComparison]::OrdinalIgnoreCase) -or
        -not [IO.Path]::GetFileName($runRoot).StartsWith(
            'employee-input-qualification-v2-',
            [StringComparison]::Ordinal
        )) {
    throw 'employee.egress_input_qualification_v2_temp_path_invalid'
}
New-Item -ItemType Directory -Path $runRoot | Out-Null
$mavenOut = Join-Path $runRoot 'maven.out.log'
$mavenErr = Join-Path $runRoot 'maven.err.log'
$pythonLog = Join-Path $runRoot 'python.log'
$stagedResultPath = Join-Path $runRoot 'qualification-result.json'
$environmentNames = @(
    'RUN_EMPLOYEE_EGRESS_INPUT_QUALIFY_V2',
    'EMPLOYEE_EGRESS_INPUT_QUALIFY_V2_REPOSITORY',
    'EMPLOYEE_EGRESS_INPUT_QUALIFY_V2_PYTHON',
    'EMPLOYEE_EGRESS_INPUT_QUALIFY_V2_PYTHON_LOG',
    'EMPLOYEE_EGRESS_INPUT_QUALIFY_V2_MANIFEST_SHA256',
    'EMPLOYEE_EGRESS_INPUT_QUALIFY_V2_LIFECYCLE',
    'EMPLOYEE_EGRESS_INPUT_QUALIFY_V2_RESULT'
)
$snapshot = @{}
foreach ($name in $environmentNames) {
    $snapshot[$name] = [Environment]::GetEnvironmentVariable($name, 'Process')
}

try {
    Remove-Item Env:\LLM_API_KEY -ErrorAction SilentlyContinue
    $env:RUN_EMPLOYEE_EGRESS_INPUT_QUALIFY_V2 = '1'
    $env:EMPLOYEE_EGRESS_INPUT_QUALIFY_V2_REPOSITORY = $repository
    $env:EMPLOYEE_EGRESS_INPUT_QUALIFY_V2_PYTHON = $python
    $env:EMPLOYEE_EGRESS_INPUT_QUALIFY_V2_PYTHON_LOG = $pythonLog
    $env:EMPLOYEE_EGRESS_INPUT_QUALIFY_V2_MANIFEST_SHA256 = $ManifestSha256
    $env:EMPLOYEE_EGRESS_INPUT_QUALIFY_V2_LIFECYCLE = $lifecyclePath
    $env:EMPLOYEE_EGRESS_INPUT_QUALIFY_V2_RESULT = $stagedResultPath

    $process = Start-Process -FilePath $maven -ArgumentList @(
        '-f', 'serviceCenter/pom.xml', '-pl', ':employee-service', '-am',
        '-Dtest=com.dylan.employee.live.EmployeeEgressInputQualificationV2LiveIntegrationTest',
        '-Dsurefire.failIfNoSpecifiedTests=false', 'test'
    ) -WorkingDirectory $repository -WindowStyle Hidden -Wait -PassThru `
        -RedirectStandardOutput $mavenOut -RedirectStandardError $mavenErr

    $combined = ''
    foreach ($path in @($mavenOut, $mavenErr, $pythonLog)) {
        if (Test-Path -LiteralPath $path) {
            if ((Get-Item -LiteralPath $path).Length -gt 8388608) {
                throw 'employee.egress_input_qualification_v2_log_scan_invalid'
            }
            $combined += [string](Get-Content -LiteralPath $path -Raw -Encoding UTF8)
        }
    }
    if ($combined.Contains($adminJwt, [StringComparison]::Ordinal) -or
            $combined.Contains($hmac, [StringComparison]::Ordinal)) {
        throw 'employee.egress_input_qualification_v2_log_leak'
    }
    foreach ($path in @($mavenOut, $mavenErr, $pythonLog)) {
        if (Test-Path -LiteralPath $path) {
            Remove-Item -LiteralPath $path -Force
        }
    }
    if (@(@($mavenOut, $mavenErr, $pythonLog) |
            Where-Object { Test-Path -LiteralPath $_ }).Count -ne 0) {
        throw 'employee.egress_input_qualification_v2_raw_log_delete_failed'
    }
    if (-not (Test-Path -LiteralPath $lifecyclePath)) {
        throw 'employee.egress_input_qualification_v2_lifecycle_missing'
    }
    $env:PYTHONPATH = "$repository\agent-runtime\src;$repository\agent-runtime"
    & $python -c "from pathlib import Path; from tests.integration.adapters.employee.egress_input_qualification_v2 import validate_lifecycle; validate_lifecycle(Path(r'$lifecyclePath'), manifest_sha256='$ManifestSha256')"
    if ($LASTEXITCODE -ne 0) {
        throw 'employee.egress_input_qualification_v2_lifecycle_invalid'
    }
    if (-not (Test-Path -LiteralPath $stagedResultPath)) {
        throw 'employee.egress_input_qualification_v2_integration_failed'
    }
    $result = Get-Content -LiteralPath $stagedResultPath -Raw -Encoding UTF8 | ConvertFrom-Json
    $result.safety.logScanCompleted = $true
    $result.safety.rawLogsDeleted = $true
    $result.safety.logLeakCount = 0
    $json = $result | ConvertTo-Json -Depth 10 -Compress
    if ($json.Contains($adminJwt, [StringComparison]::Ordinal) -or
            $json.Contains($hmac, [StringComparison]::Ordinal)) {
        throw 'employee.egress_input_qualification_v2_result_leak'
    }
    $stream = [IO.File]::Open(
        $resultPath,
        [IO.FileMode]::CreateNew,
        [IO.FileAccess]::Write,
        [IO.FileShare]::None
    )
    try {
        $bytes = [Text.Encoding]::UTF8.GetBytes($json + "`n")
        $stream.Write($bytes, 0, $bytes.Length)
        $stream.Flush($true)
    }
    finally {
        $stream.Dispose()
    }
    & $python -c "from pathlib import Path; from tests.integration.adapters.employee.egress_input_qualification_v2 import load_strict_json, validate_result; validate_result(load_strict_json(Path(r'$resultPath')), require_cleanup=True)"
    if ($LASTEXITCODE -ne 0) {
        throw 'employee.egress_input_qualification_v2_result_invalid'
    }
    if ($process.ExitCode -ne 0) {
        throw 'employee.egress_input_qualification_v2_integration_failed'
    }
    if ($result.status -cne 'qualified') {
        throw 'employee.egress_input_qualification_v2_not_qualified'
    }
}
finally {
    foreach ($name in $environmentNames) {
        [Environment]::SetEnvironmentVariable($name, $snapshot[$name], 'Process')
    }
    if (Test-Path -LiteralPath $runRoot) {
        Remove-Item -LiteralPath $runRoot -Recurse -Force
    }
    $adminJwt = $null
    $hmac = $null
}
