[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$ManifestSha256,
    [string]$RunId = 'employee-egress-v2-20260814-candidate-02',
    [string]$AuthorizationReference = 'P3_00:GATE-024',
    [string]$RepositoryRoot = (Split-Path -Parent (Split-Path -Parent $PSScriptRoot))
)

$ErrorActionPreference = 'Stop'
$expectedRunId = 'employee-egress-v2-20260814-candidate-02'
$expectedAuthorizationReference = 'P3_00:GATE-024'
$maximumPaidAnswerCalls = 30
$repository = [IO.Path]::GetFullPath($RepositoryRoot)
if ($repository -ne 'D:\codex') {
    throw 'employee.egress_candidate_v2_repository_invalid'
}
$evidenceDirectory = Join-Path $repository 'agent-runtime\tests\integration\adapters\employee\evidence'
$manifestPath = Join-Path $evidenceDirectory "$expectedRunId.manifest.json"
$authorizationPath = Join-Path $evidenceDirectory "$expectedRunId.authorization.json"
$lifecyclePath = Join-Path $evidenceDirectory "$expectedRunId.lifecycle.jsonl"
$consumedPath = Join-Path $evidenceDirectory "$expectedRunId.authorization.consumed.json"
$evidencePath = Join-Path $evidenceDirectory "$expectedRunId.result.json"

if ($RunId -cne $expectedRunId -or $AuthorizationReference -cne $expectedAuthorizationReference -or
        $ManifestSha256 -notmatch '^[0-9a-f]{64}$' -or -not (Test-Path -LiteralPath $manifestPath) -or
        -not (Test-Path -LiteralPath $authorizationPath)) {
    throw 'employee.egress_candidate_v2_authorization_binding_invalid'
}
$actualManifestSha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $manifestPath).Hash.ToLowerInvariant()
$manifest = Get-Content -LiteralPath $manifestPath -Raw -Encoding UTF8 | ConvertFrom-Json
$authorization = Get-Content -LiteralPath $authorizationPath -Raw -Encoding UTF8 | ConvertFrom-Json
if ($actualManifestSha256 -cne $ManifestSha256 -or $manifest.runId -cne $expectedRunId -or
        $manifest.schemaVersion -ne 2 -or $manifest.status -cne 'prepared_unconsumed' -or
        $manifest.preparationWorkPackageId -cne 'WP-EMP-EGRESS-CANDIDATE-02-PREP' -or
        $manifest.preparationGateId -cne 'GATE-048' -or
        $manifest.workPackageId -cne 'WP-EMP-EGRESS-01' -or $manifest.gateId -cne 'GATE-024' -or
        $manifest.authorizationReference -cne $expectedAuthorizationReference -or
        $manifest.executionBoundary.employeeDetailRequests -ne 1 -or
        $manifest.executionBoundary.maximumPaidAnswerCalls -ne $maximumPaidAnswerCalls -or
        $manifest.executionBoundary.retryAllowed -ne $false -or
        $manifest.executionBoundary.resumeAllowed -ne $false -or
        @($manifest.fieldBoundary.modelVisibleFieldIds).Count -ne 2 -or
        $manifest.fieldBoundary.modelVisibleFieldIds[0] -cne 'position' -or
        $manifest.fieldBoundary.modelVisibleFieldIds[1] -cne 'work_base_si' -or
        $authorization.runId -cne $expectedRunId -or $authorization.schemaVersion -ne 2 -or
        $authorization.status -cne 'prepared_unconsumed' -or
        $authorization.preparationWorkPackageId -cne 'WP-EMP-EGRESS-CANDIDATE-02-PREP' -or
        $authorization.preparationGateId -cne 'GATE-048' -or
        $authorization.workPackageId -cne 'WP-EMP-EGRESS-01' -or
        $authorization.gateId -cne 'GATE-024' -or
        $authorization.manifestSha256 -cne $ManifestSha256 -or
        $authorization.authorizationReference -cne $expectedAuthorizationReference -or
        $authorization.singleUse -ne $true -or
        $authorization.maximumPaidAnswerCalls -ne $maximumPaidAnswerCalls -or
        $authorization.retryAllowed -ne $false -or $authorization.resumeAllowed -ne $false -or
        $authorization.liveExecutionAuthorized -ne $false -or
        (Test-Path -LiteralPath $lifecyclePath) -or (Test-Path -LiteralPath $consumedPath) -or
        (Test-Path -LiteralPath $evidencePath)) {
    throw 'employee.egress_candidate_v2_authorization_binding_invalid'
}
$repositoryPrefix = $repository + [IO.Path]::DirectorySeparatorChar
foreach ($asset in @($manifest.assetHashes) + @($manifest.authorizationEvidence) + @($manifest.candidate01History)) {
    $assetPath = [IO.Path]::GetFullPath((Join-Path $repository ([string]$asset.path)))
    if (-not $assetPath.StartsWith($repositoryPrefix, [StringComparison]::OrdinalIgnoreCase) -or
            -not (Test-Path -LiteralPath $assetPath) -or
            (Get-FileHash -Algorithm SHA256 -LiteralPath $assetPath).Hash.ToLowerInvariant() -cne [string]$asset.sha256) {
        throw 'employee.egress_candidate_v2_asset_hash_invalid'
    }
}

# Secrets are read only after every immutable candidate and history binding succeeds.
$apiKey = [Environment]::GetEnvironmentVariable('LLM_API_KEY', 'Process')
$identifier = [Environment]::GetEnvironmentVariable('EMPLOYEE_EGRESS_LIVE_TEST_IDENTIFIER', 'Process')
$userJwt = [Environment]::GetEnvironmentVariable('EMPLOYEE_EGRESS_LIVE_USER_JWT', 'Process')
$baseUrl = [Environment]::GetEnvironmentVariable('EMPLOYEE_EGRESS_LIVE_BASE_URL', 'Process')
if ([string]::IsNullOrWhiteSpace($apiKey) -or [string]::IsNullOrWhiteSpace($identifier) -or
        [string]::IsNullOrWhiteSpace($userJwt) -or [string]::IsNullOrWhiteSpace($baseUrl)) {
    throw 'employee.egress_candidate_v2_environment_missing'
}
if ($baseUrl -cne 'http://127.0.0.1:9210') {
    throw 'employee.egress_candidate_v2_endpoint_invalid'
}

$python = (Get-Command python.exe -ErrorAction Stop).Source
$tempRoot = [IO.Path]::GetFullPath([IO.Path]::GetTempPath())
$runRoot = [IO.Path]::GetFullPath((Join-Path $tempRoot "employee-egress-candidate-v2-$([Guid]::NewGuid().ToString('N'))"))
if (-not $runRoot.StartsWith($tempRoot, [StringComparison]::OrdinalIgnoreCase) -or
        -not [IO.Path]::GetFileName($runRoot).StartsWith('employee-egress-candidate-v2-', [StringComparison]::Ordinal)) {
    throw 'employee.egress_candidate_v2_temp_path_invalid'
}
New-Item -ItemType Directory -Path $runRoot | Out-Null
$stdoutPath = Join-Path $runRoot 'pytest.out.log'
$stderrPath = Join-Path $runRoot 'pytest.err.log'
$names = @(
    'RUN_EMPLOYEE_EGRESS_CANDIDATE_V2',
    'EMPLOYEE_EGRESS_V2_MANIFEST_SHA256',
    'EMPLOYEE_EGRESS_V2_LIFECYCLE_OUTPUT',
    'EMPLOYEE_EGRESS_V2_CONSUMED_OUTPUT',
    'EMPLOYEE_EGRESS_V2_EVIDENCE_OUTPUT'
)
$snapshot = @{}
foreach ($name in $names) {
    $snapshot[$name] = [Environment]::GetEnvironmentVariable($name, 'Process')
}

try {
    $env:RUN_EMPLOYEE_EGRESS_CANDIDATE_V2 = '1'
    $env:EMPLOYEE_EGRESS_V2_MANIFEST_SHA256 = $ManifestSha256
    $env:EMPLOYEE_EGRESS_V2_LIFECYCLE_OUTPUT = $lifecyclePath
    $env:EMPLOYEE_EGRESS_V2_CONSUMED_OUTPUT = $consumedPath
    $env:EMPLOYEE_EGRESS_V2_EVIDENCE_OUTPUT = $evidencePath
    $process = Start-Process -FilePath $python -ArgumentList @(
        '-m', 'pytest',
        'tests/integration/adapters/employee/test_real_employee_egress_candidate_v2.py',
        '-q', '--tb=no'
    ) -WorkingDirectory (Join-Path $repository 'agent-runtime') -WindowStyle Hidden -Wait -PassThru `
        -RedirectStandardOutput $stdoutPath -RedirectStandardError $stderrPath
    $combined = ''
    foreach ($path in @($stdoutPath, $stderrPath)) {
        if (-not (Test-Path -LiteralPath $path) -or (Get-Item -LiteralPath $path).Length -gt 8388608) {
            throw 'employee.egress_candidate_v2_log_scan_invalid'
        }
        $combined += [string](Get-Content -LiteralPath $path -Raw -Encoding UTF8)
    }
    if ($combined.Contains($apiKey, [StringComparison]::Ordinal) -or
            $combined.Contains($identifier, [StringComparison]::Ordinal) -or
            $combined.Contains($userJwt, [StringComparison]::Ordinal)) {
        throw 'employee.egress_candidate_v2_log_leak'
    }
    if ($process.ExitCode -ne 0 -or -not (Test-Path -LiteralPath $evidencePath)) {
        if (Test-Path -LiteralPath $consumedPath) {
            throw 'employee.egress_candidate_v2_execution_failed_consumed'
        }
        if (Test-Path -LiteralPath $lifecyclePath) {
            throw 'employee.egress_candidate_v2_execution_failed_unconsumed'
        }
        throw 'employee.egress_candidate_v2_initialization_failed'
    }
    $evidence = Get-Content -LiteralPath $evidencePath -Raw -Encoding UTF8 | ConvertFrom-Json
    if ($evidence.status -cne 'passed' -or $evidence.counts.employeeDetailRequests -ne 1 -or
            $evidence.counts.actualAnswerCalls -ne $maximumPaidAnswerCalls -or
            $evidence.counts.terminalAnswerRecords -ne $maximumPaidAnswerCalls -or
            $evidence.counts.validAnswers -lt 27 -or $evidence.counts.retryCount -ne 0 -or
            $evidence.counts.resumeCount -ne 0 -or $evidence.safety.forbiddenPayloadFieldCount -ne 0 -or
            $evidence.safety.forbiddenLiteralCount -ne 0 -or $evidence.safety.logLeakCount -ne 0) {
        throw 'employee.egress_candidate_v2_result_invalid'
    }
    [PSCustomObject]@{
        status = 'passed'
        runId = $expectedRunId
        employeeDetailRequests = 1
        paidAnswerCalls = $maximumPaidAnswerCalls
        lifecycle = $lifecyclePath
        evidence = $evidencePath
    }
}
finally {
    foreach ($name in $names) {
        $oldValue = $snapshot[$name]
        if ($null -eq $oldValue) {
            Remove-Item "Env:\$name" -ErrorAction SilentlyContinue
        } else {
            [Environment]::SetEnvironmentVariable($name, [string]$oldValue, 'Process')
        }
    }
    $apiKey = $null
    $identifier = $null
    $userJwt = $null
    if (Test-Path -LiteralPath $runRoot) {
        Remove-Item -LiteralPath $runRoot -Recurse -Force
    }
}
