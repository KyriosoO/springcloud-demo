param(
    [string]$RepositoryRoot = 'D:\codex'
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$repository = [IO.Path]::GetFullPath($RepositoryRoot)
$evidence = Join-Path $repository (
    'agent-runtime\tests\integration\adapters\employee\evidence\' +
    'employee-fixture-metadata-diagnostic-v1-20260814-run-01.json'
)
$failureEvidence = Join-Path $repository (
    'agent-runtime\tests\integration\adapters\employee\evidence\' +
    'employee-fixture-metadata-diagnostic-v1-20260814-run-01.failure.json'
)
$sourceEvidence = Join-Path $repository (
    'agent-runtime\tests\integration\adapters\employee\evidence\' +
    'employee-work-base-data-diagnostic-v1-20260814-run-01.json'
)
$expectedSourceHash = 'b79f3601c3ead955e5cf747fa91cc000aad9773a1294c17277deeef05f92efe6'
$tempRoot = [IO.Path]::GetFullPath([IO.Path]::GetTempPath()).TrimEnd(
    [IO.Path]::DirectorySeparatorChar,
    [IO.Path]::AltDirectorySeparatorChar
)
$runTemp = [IO.Path]::GetFullPath((Join-Path $tempRoot (
    'wp-emp-fixture-metadata-diag-01-' + [Guid]::NewGuid().ToString('N')
)))
$expectedTempPrefix = $tempRoot + [IO.Path]::DirectorySeparatorChar + `
    'wp-emp-fixture-metadata-diag-01-'
if (-not $runTemp.StartsWith($expectedTempPrefix, [StringComparison]::OrdinalIgnoreCase)) {
    throw 'employee.fixture_metadata_diagnostic_temp_scope_invalid'
}
$staging = Join-Path $runTemp 'evidence.staging.json'
$mavenLog = Join-Path $runTemp 'maven.log'
$reports = Join-Path $runTemp 'surefire-reports'

function Remove-VerifiedRunTemp {
    if (-not (Test-Path -LiteralPath $runTemp)) {
        return
    }
    $resolved = [IO.Path]::GetFullPath($runTemp)
    if (-not $resolved.StartsWith($expectedTempPrefix, [StringComparison]::OrdinalIgnoreCase)) {
        throw 'employee.fixture_metadata_diagnostic_temp_delete_scope_invalid'
    }
    Remove-Item -LiteralPath $resolved -Recurse -Force
}

if (Test-Path -LiteralPath $evidence) {
    throw 'employee.fixture_metadata_diagnostic_evidence_already_exists'
}
if (Test-Path -LiteralPath $failureEvidence) {
    throw 'employee.fixture_metadata_diagnostic_failure_evidence_already_exists'
}
if (-not (Test-Path -LiteralPath $sourceEvidence -PathType Leaf)) {
    throw 'employee.fixture_metadata_diagnostic_source_missing'
}
$actualSourceHash = (Get-FileHash -LiteralPath $sourceEvidence -Algorithm SHA256).Hash.ToLowerInvariant()
if ($actualSourceHash -ne $expectedSourceHash) {
    throw 'employee.fixture_metadata_diagnostic_source_hash_mismatch'
}
New-Item -ItemType Directory -Path $runTemp | Out-Null

$env:RUN_EMPLOYEE_FIXTURE_METADATA_DIAG = '1'
$env:EXECUTE_EMPLOYEE_FIXTURE_METADATA_DIAG_QUERIES = '1'
$env:EMPLOYEE_FIXTURE_METADATA_DIAG_STAGING = $staging
$env:EMPLOYEE_FIXTURE_METADATA_DIAG_REPOSITORY = $repository
Remove-Item Env:\LLM_API_KEY -ErrorAction SilentlyContinue
Remove-Item Env:\COMMON_SECURITY_JWT_HMAC_KEY_ACTIVE -ErrorAction SilentlyContinue
Remove-Item Env:\EMPLOYEE_LIVE_TEST_IDENTIFIER -ErrorAction SilentlyContinue
Remove-Item Env:\EMPLOYEE_EGRESS_LIVE_TEST_IDENTIFIER -ErrorAction SilentlyContinue

try {
    Push-Location $repository
    try {
        & mvn -f serviceCenter/pom.xml -pl :employee-service -am `
            '-Dtest=EmployeeFixtureMetadataDiagnosticLiveIntegrationTest' `
            '-Dsurefire.failIfNoSpecifiedTests=false' `
            "-Dsurefire.reportsDirectory=$reports" test *> $mavenLog
        if ($LASTEXITCODE -ne 0) {
            throw 'employee.fixture_metadata_diagnostic_java_failed'
        }
    }
    finally {
        Pop-Location
    }
    if (-not (Test-Path -LiteralPath $staging -PathType Leaf)) {
        throw 'employee.fixture_metadata_diagnostic_staging_missing'
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
    $scanFiles = @(Get-ChildItem -LiteralPath $runTemp -Recurse -File |
        Where-Object { $_.FullName -ne $staging })
    foreach ($scanFile in $scanFiles) {
        foreach ($pattern in $patterns) {
            $leakCount += @(Select-String -LiteralPath $scanFile.FullName `
                -Pattern $pattern -AllMatches -ErrorAction SilentlyContinue).Count
        }
    }
    if ($leakCount -ne 0) {
        throw 'employee.fixture_metadata_diagnostic_log_leak'
    }

    if (Test-Path -LiteralPath $mavenLog) {
        Remove-Item -LiteralPath $mavenLog -Force
    }
    if (Test-Path -LiteralPath $reports) {
        Remove-Item -LiteralPath $reports -Recurse -Force
    }
    if ((Test-Path -LiteralPath $mavenLog) -or (Test-Path -LiteralPath $reports)) {
        throw 'employee.fixture_metadata_diagnostic_raw_log_cleanup_failed'
    }

    Push-Location (Join-Path $repository 'agent-runtime')
    try {
        $env:PYTHONPATH = 'src;.'
        & python -c (
            'from pathlib import Path; ' +
            'from tests.integration.adapters.employee.fixture_metadata_diagnostic ' +
            'import finalize_staging_evidence; import sys; ' +
            'finalize_staging_evidence(Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]))'
        ) $staging $evidence $repository
        if ($LASTEXITCODE -ne 0) {
            throw 'employee.fixture_metadata_diagnostic_finalize_failed'
        }
    }
    finally {
        Pop-Location
        Remove-Item Env:\PYTHONPATH -ErrorAction SilentlyContinue
    }

    $value = Get-Content -LiteralPath $evidence -Raw -Encoding utf8 | ConvertFrom-Json
    [pscustomobject]@{
        status = $value.status
        result = $value.assessment.result
        reason = $value.assessment.reason
        gateMayClose = $value.assessment.gateMayClose
        engine = $value.tableMetadata.engine
        columns = $value.counts.columnResultRows
        constraints = $value.counts.constraintResultRows
        checks = $value.counts.checkResultRows
        triggers = $value.counts.triggerResultRows
        executedQueries = $value.counts.executedQueries
        businessRowsRead = $value.safety.businessRowsRead
        databaseWrites = $value.safety.databaseWrites
        modelCalls = $value.counts.modelCalls
        logLeakCount = $value.safety.logLeakCount
        evidence = $evidence
    }
}
finally {
    Remove-Item Env:\RUN_EMPLOYEE_FIXTURE_METADATA_DIAG -ErrorAction SilentlyContinue
    Remove-Item Env:\EXECUTE_EMPLOYEE_FIXTURE_METADATA_DIAG_QUERIES -ErrorAction SilentlyContinue
    Remove-Item Env:\EMPLOYEE_FIXTURE_METADATA_DIAG_STAGING -ErrorAction SilentlyContinue
    Remove-Item Env:\EMPLOYEE_FIXTURE_METADATA_DIAG_REPOSITORY -ErrorAction SilentlyContinue
    Remove-Item Env:\PYTHONPATH -ErrorAction SilentlyContinue
    Remove-VerifiedRunTemp
}
