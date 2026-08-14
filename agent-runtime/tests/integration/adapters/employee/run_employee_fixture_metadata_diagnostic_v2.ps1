[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$ManifestSha256,
    [string]$RunId = 'employee-fixture-metadata-diagnostic-v2-20260814-candidate-02',
    [string]$AuthorizationReference = 'P3_00:GATE-050',
    [string]$RepositoryRoot = (Split-Path -Parent (Split-Path -Parent (Split-Path -Parent (Split-Path -Parent (Split-Path -Parent $PSScriptRoot)))))
)

$ErrorActionPreference = 'Stop'
$expectedRunId = 'employee-fixture-metadata-diagnostic-v2-20260814-candidate-02'
$expectedAuthorizationReference = 'P3_00:GATE-050'
$repository = [IO.Path]::GetFullPath($RepositoryRoot)
if ($repository -cne 'D:\codex') {
    throw 'employee.fixture_metadata_v2_repository_invalid'
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
    throw 'employee.fixture_metadata_v2_binding_invalid'
}

$actualManifestSha256 = (Get-FileHash -LiteralPath $manifestPath -Algorithm SHA256).Hash.ToLowerInvariant()
if ($actualManifestSha256 -cne $ManifestSha256) {
    throw 'employee.fixture_metadata_v2_manifest_hash_invalid'
}
Push-Location (Join-Path $repository 'agent-runtime')
try {
    $env:PYTHONPATH = 'src;.'
    & python -c (
        'from pathlib import Path; from tests.integration.adapters.employee.fixture_metadata_diagnostic_v2 ' +
        'import validate_manifest; import sys; validate_manifest(Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]))'
    ) $manifestPath $authorizationPath $repository
    if ($LASTEXITCODE -ne 0) {
        throw 'employee.fixture_metadata_v2_manifest_invalid'
    }
}
finally {
    Pop-Location
    Remove-Item Env:\PYTHONPATH -ErrorAction SilentlyContinue
}

# The frozen prepared authorization remains false; a fresh process flag is required
# only after the maintainer binds this exact run/hash to a new GATE-050 authorization.
if ([Environment]::GetEnvironmentVariable('RUN_EMPLOYEE_FIXTURE_METADATA_DIAG_V2', 'Process') -cne '1') {
    throw 'employee.fixture_metadata_v2_live_not_authorized'
}

$tempBase = [IO.Path]::GetFullPath((Join-Path $repository 'agent-runtime\.codex-live'))
New-Item -ItemType Directory -Path $tempBase -Force | Out-Null
$runTemp = [IO.Path]::GetFullPath((Join-Path $tempBase "fixture-metadata-v2-$([Guid]::NewGuid().ToString('N'))"))
$expectedTempPrefix = $tempBase + [IO.Path]::DirectorySeparatorChar + 'fixture-metadata-v2-'
if (-not $runTemp.StartsWith($expectedTempPrefix, [StringComparison]::OrdinalIgnoreCase)) {
    throw 'employee.fixture_metadata_v2_temp_path_invalid'
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
        throw 'employee.fixture_metadata_v2_temp_delete_scope_invalid'
    }
    Remove-Item -LiteralPath $resolved -Recurse -Force
}

$env:RUN_EMPLOYEE_FIXTURE_METADATA_DIAG_V2 = '1'
$env:EXECUTE_EMPLOYEE_FIXTURE_METADATA_DIAG_V2_QUERIES = '1'
$env:EMPLOYEE_FIXTURE_METADATA_DIAG_V2_REPOSITORY = $repository
$env:EMPLOYEE_FIXTURE_METADATA_DIAG_V2_LIFECYCLE = $lifecyclePath
$env:EMPLOYEE_FIXTURE_METADATA_DIAG_V2_STAGING = $stagingPath
Remove-Item Env:\LLM_API_KEY -ErrorAction SilentlyContinue
Remove-Item Env:\COMMON_SECURITY_JWT_HMAC_KEY_ACTIVE -ErrorAction SilentlyContinue
Remove-Item Env:\EMPLOYEE_LIVE_TEST_IDENTIFIER -ErrorAction SilentlyContinue
Remove-Item Env:\EMPLOYEE_EGRESS_LIVE_TEST_IDENTIFIER -ErrorAction SilentlyContinue

try {
    Push-Location $repository
    try {
        & mvn -f serviceCenter/pom.xml -pl :employee-service -am `
            '-Dtest=EmployeeFixtureMetadataDiagnosticV2LiveIntegrationTest' `
            '-Dsurefire.failIfNoSpecifiedTests=false' `
            "-Dsurefire.reportsDirectory=$reports" test *> $mavenLog
        $mavenExit = $LASTEXITCODE
    }
    finally {
        Pop-Location
    }

    if (-not (Test-Path -LiteralPath $lifecyclePath -PathType Leaf) -or
            -not (Test-Path -LiteralPath $stagingPath -PathType Leaf)) {
        throw 'employee.fixture_metadata_v2_terminal_evidence_missing'
    }

    $patterns = @(
        '(?<!\d)[1-9]\d{16}[0-9Xx](?!\w)',
        'eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.',
        '(?i)authorization\s*[:=]\s*bearer',
        '(?i)LLM_API_KEY\s*[:=]',
        '(?i)COMMON_SECURITY_JWT_HMAC_KEY_[A-Z0-9_]+\s*[:=]',
        '(?i)EMPLOYEE_(?:EGRESS_)?LIVE_TEST_IDENTIFIER\s*[:=]'
    )
    $leakCount = 0
    foreach ($scanFile in @(Get-ChildItem -LiteralPath $runTemp -Recurse -File |
            Where-Object { $_.FullName -ne $stagingPath })) {
        foreach ($pattern in $patterns) {
            $leakCount += @(Select-String -LiteralPath $scanFile.FullName `
                -Pattern $pattern -AllMatches -ErrorAction SilentlyContinue).Count
        }
    }
    if ($leakCount -ne 0) {
        throw 'employee.fixture_metadata_v2_log_leak'
    }

    if (Test-Path -LiteralPath $mavenLog) {
        Remove-Item -LiteralPath $mavenLog -Force
    }
    if (Test-Path -LiteralPath $reports) {
        Remove-Item -LiteralPath $reports -Recurse -Force
    }
    if ((Test-Path -LiteralPath $mavenLog) -or (Test-Path -LiteralPath $reports)) {
        throw 'employee.fixture_metadata_v2_raw_log_cleanup_failed'
    }

    Push-Location (Join-Path $repository 'agent-runtime')
    try {
        $env:PYTHONPATH = 'src;.'
        & python -c (
            'from pathlib import Path; from tests.integration.adapters.employee.fixture_metadata_diagnostic_v2 ' +
            'import finalize_staging_result, validate_lifecycle; import sys; ' +
            'validate_lifecycle(Path(sys.argv[1])); finalize_staging_result(Path(sys.argv[2]), Path(sys.argv[3]))'
        ) $lifecyclePath $stagingPath $resultPath
        if ($LASTEXITCODE -ne 0) {
            throw 'employee.fixture_metadata_v2_finalize_failed'
        }
    }
    finally {
        Pop-Location
        Remove-Item Env:\PYTHONPATH -ErrorAction SilentlyContinue
    }

    if ($mavenExit -ne 0) {
        throw 'employee.fixture_metadata_v2_query_failed'
    }
    [pscustomobject]@{
        status = 'passed'
        runId = $expectedRunId
        executedQueries = 4
        retryCount = 0
        resumeCount = 0
        evidence = $resultPath
        lifecycle = $lifecyclePath
    }
}
finally {
    Remove-Item Env:\RUN_EMPLOYEE_FIXTURE_METADATA_DIAG_V2 -ErrorAction SilentlyContinue
    Remove-Item Env:\EXECUTE_EMPLOYEE_FIXTURE_METADATA_DIAG_V2_QUERIES -ErrorAction SilentlyContinue
    Remove-Item Env:\EMPLOYEE_FIXTURE_METADATA_DIAG_V2_REPOSITORY -ErrorAction SilentlyContinue
    Remove-Item Env:\EMPLOYEE_FIXTURE_METADATA_DIAG_V2_LIFECYCLE -ErrorAction SilentlyContinue
    Remove-Item Env:\EMPLOYEE_FIXTURE_METADATA_DIAG_V2_STAGING -ErrorAction SilentlyContinue
    Remove-Item Env:\PYTHONPATH -ErrorAction SilentlyContinue
    Remove-VerifiedRunTemp
}
