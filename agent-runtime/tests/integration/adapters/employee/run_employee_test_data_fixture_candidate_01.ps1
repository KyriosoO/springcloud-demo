[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$ManifestSha256,
    [string]$RunId = 'employee-synthetic-fixture-v1-20260814-candidate-01',
    [string]$AuthorizationReference = 'P3_00:GATE-051',
    [string]$RepositoryRoot = (Split-Path -Parent (Split-Path -Parent (Split-Path -Parent (Split-Path -Parent (Split-Path -Parent $PSScriptRoot)))))
)

$ErrorActionPreference = 'Stop'
$expectedRunId = 'employee-synthetic-fixture-v1-20260814-candidate-01'
$expectedAuthorizationReference = 'P3_00:GATE-051'
$repository = [IO.Path]::GetFullPath($RepositoryRoot)
if ($repository -cne 'D:\codex') {
    throw 'employee.fixture_candidate_repository_invalid'
}

$evidenceDirectory = Join-Path $repository 'agent-runtime\tests\integration\adapters\employee\evidence'
$manifestPath = Join-Path $evidenceDirectory "$expectedRunId.manifest.json"
$authorizationPath = Join-Path $evidenceDirectory "$expectedRunId.authorization.json"
$lifecyclePath = Join-Path $evidenceDirectory "$expectedRunId.lifecycle.jsonl"
$resultPath = Join-Path $evidenceDirectory "$expectedRunId.result.json"

if ($RunId -cne $expectedRunId -or
        $AuthorizationReference -cne $expectedAuthorizationReference -or
        $ManifestSha256 -notmatch '^[0-9a-f]{64}$' -or
        -not (Test-Path -LiteralPath $manifestPath -PathType Leaf) -or
        -not (Test-Path -LiteralPath $authorizationPath -PathType Leaf) -or
        (Test-Path -LiteralPath $lifecyclePath) -or
        (Test-Path -LiteralPath $resultPath)) {
    throw 'employee.fixture_candidate_binding_invalid'
}

$actualManifestSha256 = (Get-FileHash -LiteralPath $manifestPath -Algorithm SHA256).Hash.ToLowerInvariant()
if ($actualManifestSha256 -cne $ManifestSha256) {
    throw 'employee.fixture_candidate_manifest_hash_invalid'
}

Push-Location (Join-Path $repository 'agent-runtime')
try {
    $env:PYTHONPATH = 'src;.'
    & py -3.12 -c (
        'from pathlib import Path; from tests.integration.adapters.employee.employee_test_data_fixture_candidate ' +
        'import validate_manifest; import sys; validate_manifest(Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]))'
    ) $manifestPath $authorizationPath $repository
    if ($LASTEXITCODE -ne 0) {
        throw 'employee.fixture_candidate_manifest_invalid'
    }
}
finally {
    Pop-Location
    Remove-Item Env:\PYTHONPATH -ErrorAction SilentlyContinue
}

if ([Environment]::GetEnvironmentVariable(
        'RUN_EMPLOYEE_TEST_DATA_FIXTURE_CANDIDATE_01', 'Process') -cne '1') {
    throw 'employee.fixture_candidate_live_not_authorized'
}

$tempBase = [IO.Path]::GetFullPath((Join-Path $repository 'agent-runtime\.codex-live'))
New-Item -ItemType Directory -Path $tempBase -Force | Out-Null
$runTemp = [IO.Path]::GetFullPath((Join-Path $tempBase "employee-fixture-$([Guid]::NewGuid().ToString('N'))"))
$expectedTempPrefix = $tempBase + [IO.Path]::DirectorySeparatorChar + 'employee-fixture-'
if (-not $runTemp.StartsWith($expectedTempPrefix, [StringComparison]::OrdinalIgnoreCase)) {
    throw 'employee.fixture_candidate_temp_path_invalid'
}
New-Item -ItemType Directory -Path $runTemp | Out-Null
$stagingPath = Join-Path $runTemp 'result.staging.json'
$mavenLog = Join-Path $runTemp 'maven.log'
$reports = Join-Path $runTemp 'reports'
$mavenExit = -1

function Remove-VerifiedRunTemp {
    if (-not (Test-Path -LiteralPath $runTemp)) {
        return
    }
    $resolved = [IO.Path]::GetFullPath($runTemp)
    if (-not $resolved.StartsWith($expectedTempPrefix, [StringComparison]::OrdinalIgnoreCase)) {
        throw 'employee.fixture_candidate_temp_delete_scope_invalid'
    }
    Remove-Item -LiteralPath $resolved -Recurse -Force
}

$env:RUN_EMPLOYEE_TEST_DATA_FIXTURE_CANDIDATE_01 = '1'
$env:EXECUTE_EMPLOYEE_TEST_DATA_FIXTURE_CANDIDATE_01 = '1'
$env:EMPLOYEE_FIXTURE_CANDIDATE_REPOSITORY = $repository
$env:EMPLOYEE_FIXTURE_CANDIDATE_LIFECYCLE = $lifecyclePath
$env:EMPLOYEE_FIXTURE_CANDIDATE_STAGING = $stagingPath
$env:EMPLOYEE_FIXTURE_CANDIDATE_MANIFEST_SHA256 = $ManifestSha256
Remove-Item Env:\LLM_API_KEY -ErrorAction SilentlyContinue
Remove-Item Env:\COMMON_SECURITY_JWT_HMAC_KEY_ACTIVE -ErrorAction SilentlyContinue
Remove-Item Env:\EMPLOYEE_LIVE_TEST_IDENTIFIER -ErrorAction SilentlyContinue
Remove-Item Env:\EMPLOYEE_EGRESS_LIVE_TEST_IDENTIFIER -ErrorAction SilentlyContinue

try {
    Push-Location $repository
    try {
        & mvn -f serviceCenter/pom.xml -pl :employee-service -am `
            '-Dtest=EmployeeSyntheticFixtureCandidateLiveIntegrationTest' `
            '-Dsurefire.failIfNoSpecifiedTests=false' `
            "-Dsurefire.reportsDirectory=$reports" test *> $mavenLog
        $mavenExit = $LASTEXITCODE
    }
    finally {
        Pop-Location
    }

    if (-not (Test-Path -LiteralPath $lifecyclePath -PathType Leaf) -or
            -not (Test-Path -LiteralPath $stagingPath -PathType Leaf)) {
        throw 'employee.fixture_candidate_terminal_evidence_missing'
    }

    $patterns = @(
        'synthetic-employee-[0-9a-f]{24}',
        'Synthetic Employee',
        'Synthetic Position',
        'Synthetic Work Base',
        '(?<!\d)[1-9]\d{16}[0-9Xx](?!\w)',
        'eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.',
        '(?i)authorization\s*[:=]\s*bearer',
        '(?i)LLM_API_KEY\s*[:=]',
        '(?i)COMMON_SECURITY_JWT_HMAC_KEY_[A-Z0-9_]+\s*[:=]'
    )
    $leakCount = 0
    foreach ($scanFile in @(Get-ChildItem -LiteralPath $runTemp -Recurse -File |
            Where-Object { $_.FullName -ne $stagingPath })) {
        foreach ($pattern in $patterns) {
            $leakCount += @(Select-String -LiteralPath $scanFile.FullName `
                -Pattern $pattern -AllMatches -ErrorAction SilentlyContinue).Count
        }
    }
    if (Test-Path -LiteralPath $mavenLog) {
        Remove-Item -LiteralPath $mavenLog -Force
    }
    if (Test-Path -LiteralPath $reports) {
        Remove-Item -LiteralPath $reports -Recurse -Force
    }
    if ((Test-Path -LiteralPath $mavenLog) -or (Test-Path -LiteralPath $reports)) {
        throw 'employee.fixture_candidate_raw_log_cleanup_failed'
    }

    Push-Location (Join-Path $repository 'agent-runtime')
    try {
        $env:PYTHONPATH = 'src;.'
        & py -3.12 -c (
            'from pathlib import Path; from tests.integration.adapters.employee.employee_test_data_fixture_candidate ' +
            'import finalize_staging_result; import sys; ' +
            'finalize_staging_result(Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]), ' +
            'log_leak_count=int(sys.argv[4]), host_exit_code=int(sys.argv[5]))'
        ) $stagingPath $lifecyclePath $resultPath $leakCount $mavenExit
        if ($LASTEXITCODE -ne 0) {
            throw 'employee.fixture_candidate_finalize_failed'
        }
    }
    finally {
        Pop-Location
        Remove-Item Env:\PYTHONPATH -ErrorAction SilentlyContinue
    }

    if ($mavenExit -ne 0) {
        throw 'employee.fixture_candidate_execution_failed'
    }
    if ($leakCount -ne 0) {
        throw 'employee.fixture_candidate_log_leak'
    }
    [pscustomobject]@{
        status = 'passed'
        runId = $expectedRunId
        databaseSelects = 3
        databaseInserts = 1
        databaseDeletes = 1
        employeeEndpointCalls = 0
        modelCalls = 0
        retryCount = 0
        resumeCount = 0
        lifecycle = $lifecyclePath
        evidence = $resultPath
    }
}
finally {
    Remove-Item Env:\RUN_EMPLOYEE_TEST_DATA_FIXTURE_CANDIDATE_01 -ErrorAction SilentlyContinue
    Remove-Item Env:\EXECUTE_EMPLOYEE_TEST_DATA_FIXTURE_CANDIDATE_01 -ErrorAction SilentlyContinue
    Remove-Item Env:\EMPLOYEE_FIXTURE_CANDIDATE_REPOSITORY -ErrorAction SilentlyContinue
    Remove-Item Env:\EMPLOYEE_FIXTURE_CANDIDATE_LIFECYCLE -ErrorAction SilentlyContinue
    Remove-Item Env:\EMPLOYEE_FIXTURE_CANDIDATE_STAGING -ErrorAction SilentlyContinue
    Remove-Item Env:\EMPLOYEE_FIXTURE_CANDIDATE_MANIFEST_SHA256 -ErrorAction SilentlyContinue
    Remove-Item Env:\PYTHONPATH -ErrorAction SilentlyContinue
    Remove-VerifiedRunTemp
}
