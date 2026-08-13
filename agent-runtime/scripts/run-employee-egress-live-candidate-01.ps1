[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$ManifestSha256,
    [string]$RunId = 'employee-egress-v1-20260813-candidate-01',
    [string]$AuthorizationReference = 'P3_00:GATE-024',
    [string]$RepositoryRoot = (Split-Path -Parent (Split-Path -Parent $PSScriptRoot))
)

$ErrorActionPreference = 'Stop'
$expectedRunId = 'employee-egress-v1-20260813-candidate-01'
$expectedAuthorizationReference = 'P3_00:GATE-024'
$maximumPaidAnswerCalls = 30
$repository = [IO.Path]::GetFullPath($RepositoryRoot)
if ($repository -ne 'D:\codex') {
    throw 'employee.egress_candidate_repository_invalid'
}
$manifestPath = Join-Path $repository 'agent-runtime\tests\integration\adapters\employee\evidence\employee-egress-v1-20260813-candidate-01.manifest.json'
$authorizationPath = Join-Path $repository 'agent-runtime\tests\integration\adapters\employee\evidence\employee-egress-v1-20260813-candidate-01.authorization.json'
$consumedPath = Join-Path $repository 'agent-runtime\tests\integration\adapters\employee\evidence\employee-egress-v1-20260813-candidate-01.authorization.consumed.json'
$evidencePath = Join-Path $repository 'agent-runtime\tests\integration\adapters\employee\evidence\employee-egress-v1-20260813-candidate-01.result.json'
$journalPath = Join-Path $repository 'agent-runtime\tests\integration\adapters\employee\evidence\employee-egress-v1-20260813-candidate-01.attempts.jsonl'

if ($RunId -cne $expectedRunId -or $AuthorizationReference -cne $expectedAuthorizationReference -or
        $ManifestSha256 -notmatch '^[0-9a-f]{64}$' -or -not (Test-Path -LiteralPath $manifestPath) -or
        -not (Test-Path -LiteralPath $authorizationPath)) {
    throw 'employee.egress_candidate_authorization_binding_invalid'
}
$actualManifestSha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $manifestPath).Hash.ToLowerInvariant()
$manifest = Get-Content -LiteralPath $manifestPath -Raw -Encoding UTF8 | ConvertFrom-Json
$authorization = Get-Content -LiteralPath $authorizationPath -Raw -Encoding UTF8 | ConvertFrom-Json
if ($actualManifestSha256 -cne $ManifestSha256 -or $manifest.runId -cne $expectedRunId -or
        $manifest.status -cne 'prepared_unconsumed' -or $manifest.workPackageId -cne 'WP-EMP-EGRESS-01' -or
        $manifest.gateId -cne 'GATE-024' -or
        $manifest.authorizationReference -cne $expectedAuthorizationReference -or
        $manifest.executionBoundary.maximumPaidAnswerCalls -ne $maximumPaidAnswerCalls -or
        @($manifest.fieldBoundary.modelVisibleFieldIds).Count -ne 2 -or
        $manifest.fieldBoundary.modelVisibleFieldIds[0] -cne 'position' -or
        $manifest.fieldBoundary.modelVisibleFieldIds[1] -cne 'work_base_si' -or
        $authorization.runId -cne $expectedRunId -or
        $authorization.status -cne 'prepared_unconsumed' -or
        $authorization.workPackageId -cne 'WP-EMP-EGRESS-01' -or
        $authorization.gateId -cne 'GATE-024' -or
        $authorization.manifestSha256 -cne $ManifestSha256 -or
        $authorization.authorizationReference -cne $expectedAuthorizationReference -or
        $authorization.singleUse -ne $true -or
        $authorization.maximumPaidAnswerCalls -ne $maximumPaidAnswerCalls -or
        $authorization.retryAllowed -ne $false -or $authorization.resumeAllowed -ne $false -or
        $authorization.liveExecutionAuthorized -ne $false -or
        (Test-Path -LiteralPath $consumedPath) -or (Test-Path -LiteralPath $evidencePath) -or
        (Test-Path -LiteralPath $journalPath)) {
    throw 'employee.egress_candidate_authorization_binding_invalid'
}
$repositoryPrefix = $repository + [IO.Path]::DirectorySeparatorChar
foreach ($asset in @($manifest.assetHashes) + @($manifest.authorizationEvidence)) {
    $assetPath = [IO.Path]::GetFullPath((Join-Path $repository ([string]$asset.path)))
    if (-not $assetPath.StartsWith($repositoryPrefix, [StringComparison]::OrdinalIgnoreCase) -or
            -not (Test-Path -LiteralPath $assetPath) -or
            (Get-FileHash -Algorithm SHA256 -LiteralPath $assetPath).Hash.ToLowerInvariant() -cne [string]$asset.sha256) {
        throw 'employee.egress_candidate_asset_hash_invalid'
    }
}

# Secret and domain inputs are intentionally read only after every immutable binding succeeds.
$apiKey = [Environment]::GetEnvironmentVariable('LLM_API_KEY', 'Process')
$identifier = [Environment]::GetEnvironmentVariable('EMPLOYEE_EGRESS_LIVE_TEST_IDENTIFIER', 'Process')
$userJwt = [Environment]::GetEnvironmentVariable('EMPLOYEE_EGRESS_LIVE_USER_JWT', 'Process')
$baseUrl = [Environment]::GetEnvironmentVariable('EMPLOYEE_EGRESS_LIVE_BASE_URL', 'Process')
if ([string]::IsNullOrWhiteSpace($apiKey) -or [string]::IsNullOrWhiteSpace($identifier) -or
        [string]::IsNullOrWhiteSpace($userJwt) -or [string]::IsNullOrWhiteSpace($baseUrl)) {
    throw 'employee.egress_candidate_environment_missing'
}
if ($baseUrl -cne 'http://127.0.0.1:9210') {
    throw 'employee.egress_candidate_endpoint_invalid'
}

$python = (Get-Command python.exe -ErrorAction Stop).Source
$tempRoot = [IO.Path]::GetFullPath([IO.Path]::GetTempPath())
$runRoot = [IO.Path]::GetFullPath((Join-Path $tempRoot "employee-egress-candidate-$([Guid]::NewGuid().ToString('N'))"))
if (-not $runRoot.StartsWith($tempRoot, [StringComparison]::OrdinalIgnoreCase) -or
        -not [IO.Path]::GetFileName($runRoot).StartsWith('employee-egress-candidate-', [StringComparison]::Ordinal)) {
    throw 'employee.egress_candidate_temp_path_invalid'
}
New-Item -ItemType Directory -Path $runRoot | Out-Null
$stdoutPath = Join-Path $runRoot 'pytest.out.log'
$stderrPath = Join-Path $runRoot 'pytest.err.log'
$names = @(
    'RUN_EMPLOYEE_EGRESS_CANDIDATE',
    'EMPLOYEE_EGRESS_MANIFEST_SHA256',
    'EMPLOYEE_EGRESS_CONSUMED_OUTPUT',
    'EMPLOYEE_EGRESS_EVIDENCE_OUTPUT',
    'EMPLOYEE_EGRESS_ATTEMPT_JOURNAL_OUTPUT'
)
$snapshot = @{}
foreach ($name in $names) {
    $snapshot[$name] = [Environment]::GetEnvironmentVariable($name, 'Process')
}

try {
    $env:RUN_EMPLOYEE_EGRESS_CANDIDATE = '1'
    $env:EMPLOYEE_EGRESS_MANIFEST_SHA256 = $ManifestSha256
    $env:EMPLOYEE_EGRESS_CONSUMED_OUTPUT = $consumedPath
    $env:EMPLOYEE_EGRESS_EVIDENCE_OUTPUT = $evidencePath
    $env:EMPLOYEE_EGRESS_ATTEMPT_JOURNAL_OUTPUT = $journalPath
    $process = Start-Process -FilePath $python -ArgumentList @(
        '-m', 'pytest',
        'tests/integration/adapters/employee/test_real_employee_egress_candidate.py',
        '-q', '--tb=no'
    ) -WorkingDirectory (Join-Path $repository 'agent-runtime') -WindowStyle Hidden -Wait -PassThru `
        -RedirectStandardOutput $stdoutPath -RedirectStandardError $stderrPath
    $combined = ''
    foreach ($path in @($stdoutPath, $stderrPath)) {
        if ((Test-Path -LiteralPath $path) -and (Get-Item -LiteralPath $path).Length -le 8388608) {
            $combined += [string](Get-Content -LiteralPath $path -Raw -Encoding UTF8)
        }
    }
    if ($combined.Contains($apiKey, [StringComparison]::Ordinal) -or
            $combined.Contains($identifier, [StringComparison]::Ordinal) -or
            $combined.Contains($userJwt, [StringComparison]::Ordinal)) {
        throw 'employee.egress_candidate_log_leak'
    }
    if ($process.ExitCode -ne 0 -or -not (Test-Path -LiteralPath $evidencePath)) {
        throw 'employee.egress_candidate_execution_failed'
    }
    $evidence = Get-Content -LiteralPath $evidencePath -Raw -Encoding UTF8 | ConvertFrom-Json
    if ($evidence.status -ne 'passed' -or $evidence.counts.employeeDetailRequests -ne 1 -or
            $evidence.counts.actualAnswerCalls -ne $maximumPaidAnswerCalls -or
            $evidence.counts.terminalAnswerRecords -ne $maximumPaidAnswerCalls -or
            $evidence.counts.validAnswers -lt 27 -or $evidence.counts.retryCount -ne 0 -or
            $evidence.counts.resumeCount -ne 0 -or $evidence.safety.logLeakCount -ne 0) {
        throw 'employee.egress_candidate_result_invalid'
    }
    [PSCustomObject]@{
        status = 'passed'
        runId = $expectedRunId
        employeeDetailRequests = 1
        paidAnswerCalls = $maximumPaidAnswerCalls
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
