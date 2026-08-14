param(
    [string]$RepositoryRoot = 'D:\codex'
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$repository = [IO.Path]::GetFullPath($RepositoryRoot)
$evidence = Join-Path $repository (
    'agent-runtime\tests\integration\adapters\employee\evidence\' +
    'employee-egress-input-qualification-diagnostic-v2-20260814-run-01.json'
)
$tempRoot = [IO.Path]::GetFullPath([IO.Path]::GetTempPath())
$runTemp = [IO.Path]::GetFullPath((Join-Path $tempRoot (
    'wp-emp-egress-input-qualify-diag-02-' + [Guid]::NewGuid().ToString('N')
)))
if (-not $runTemp.StartsWith($tempRoot, [StringComparison]::OrdinalIgnoreCase)) {
    throw 'employee.diagnostic_temp_scope_invalid'
}
$staging = Join-Path $runTemp 'counts.staging.json'
$mavenLog = Join-Path $runTemp 'maven.log'
$reports = Join-Path $runTemp 'surefire-reports'

function Remove-VerifiedTempTree {
    param([string]$Path)
    $resolved = [IO.Path]::GetFullPath($Path)
    $prefix = $runTemp + [IO.Path]::DirectorySeparatorChar
    if (-not $resolved.StartsWith($prefix, [StringComparison]::OrdinalIgnoreCase)) {
        throw 'employee.diagnostic_temp_delete_scope_invalid'
    }
    if (Test-Path -LiteralPath $resolved) {
        Remove-Item -LiteralPath $resolved -Recurse -Force
    }
}

if (Test-Path -LiteralPath $evidence) {
    throw 'employee.diagnostic_evidence_already_exists'
}
New-Item -ItemType Directory -Path $runTemp | Out-Null

$env:RUN_EMPLOYEE_EGRESS_INPUT_QUALIFY_DIAG_V2 = '1'
$env:EXECUTE_EMPLOYEE_EGRESS_INPUT_QUALIFY_DIAG_V2_QUERY = '1'
$env:EMPLOYEE_EGRESS_INPUT_QUALIFY_DIAG_V2_EVIDENCE = $staging
$env:EMPLOYEE_EGRESS_INPUT_QUALIFY_DIAG_V2_REPOSITORY = $repository
Remove-Item Env:\LLM_API_KEY -ErrorAction SilentlyContinue
Remove-Item Env:\COMMON_SECURITY_JWT_HMAC_KEY_ACTIVE -ErrorAction SilentlyContinue

try {
    Push-Location $repository
    try {
        & mvn -f serviceCenter/pom.xml -pl :employee-service -am `
            '-Dtest=EmployeeEgressInputQualificationDiagnosticV2LiveIntegrationTest' `
            '-Dsurefire.failIfNoSpecifiedTests=false' `
            "-Dsurefire.reportsDirectory=$reports" test *> $mavenLog
        if ($LASTEXITCODE -ne 0) {
            throw 'employee.diagnostic_java_failed'
        }
    }
    finally {
        Pop-Location
    }
    if (-not (Test-Path -LiteralPath $staging)) {
        throw 'employee.diagnostic_staging_missing'
    }

    $patterns = @(
        '(?<!\d)[1-9]\d{16}[0-9Xx](?!\w)',
        'eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.',
        '(?i)authorization\s*[:=]\s*bearer',
        '(?i)LLM_API_KEY\s*[:=]',
        '(?i)COMMON_SECURITY_JWT_HMAC_KEY_[A-Z0-9_]+\s*[:=]'
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
        throw 'employee.diagnostic_log_leak'
    }

    if (Test-Path -LiteralPath $mavenLog) {
        Remove-Item -LiteralPath $mavenLog -Force
    }
    Remove-VerifiedTempTree -Path $reports
    if ((Test-Path -LiteralPath $mavenLog) -or (Test-Path -LiteralPath $reports)) {
        throw 'employee.diagnostic_raw_log_cleanup_failed'
    }

    Push-Location (Join-Path $repository 'agent-runtime')
    try {
        $env:PYTHONPATH = 'src;.'
        & python -c (
            'from pathlib import Path; ' +
            'from tests.integration.adapters.employee.' +
            'egress_input_qualification_diagnostic_v2 import finalize_staging_evidence; ' +
            'import sys; finalize_staging_evidence(Path(sys.argv[1]), Path(sys.argv[2]))'
        ) $staging $evidence
        if ($LASTEXITCODE -ne 0) {
            throw 'employee.diagnostic_finalize_failed'
        }
    }
    finally {
        Pop-Location
        Remove-Item Env:\PYTHONPATH -ErrorAction SilentlyContinue
    }
    Remove-Item -LiteralPath $staging -Force

    $value = Get-Content -LiteralPath $evidence -Raw -Encoding utf8 | ConvertFrom-Json
    [pscustomobject]@{
        status = $value.status
        reason = $value.diagnosis.reason
        firstZeroStage = $value.diagnosis.firstZeroStage
        qualifiedInputAvailable = $value.diagnosis.qualifiedInputAvailable
        totalRows = $value.counts.totalRows
        idCardNoCondition = $value.counts.idCardNoCondition
        chineseNameCondition = $value.counts.chineseNameCondition
        positionCondition = $value.counts.positionCondition
        workBaseSiCondition = $value.counts.workBaseSiCondition
        cumulativeIdCardNo = $value.counts.cumulativeIdCardNo
        cumulativeChineseName = $value.counts.cumulativeChineseName
        cumulativePosition = $value.counts.cumulativePosition
        cumulativeWorkBaseSi = $value.counts.cumulativeWorkBaseSi
        aggregateQueries = $value.counts.aggregateQueries
        employeeDetailCalls = $value.counts.employeeDetailCalls
        modelCalls = $value.counts.modelCalls
        logLeakCount = $value.safety.logLeakCount
        evidence = $evidence
    }
}
finally {
    Remove-Item Env:\RUN_EMPLOYEE_EGRESS_INPUT_QUALIFY_DIAG_V2 -ErrorAction SilentlyContinue
    Remove-Item Env:\EXECUTE_EMPLOYEE_EGRESS_INPUT_QUALIFY_DIAG_V2_QUERY -ErrorAction SilentlyContinue
    Remove-Item Env:\EMPLOYEE_EGRESS_INPUT_QUALIFY_DIAG_V2_EVIDENCE -ErrorAction SilentlyContinue
    Remove-Item Env:\EMPLOYEE_EGRESS_INPUT_QUALIFY_DIAG_V2_REPOSITORY -ErrorAction SilentlyContinue
    if (Test-Path -LiteralPath $mavenLog) {
        Remove-Item -LiteralPath $mavenLog -Force
    }
    Remove-VerifiedTempTree -Path $reports
    if (Test-Path -LiteralPath $runTemp) {
        $remaining = @(Get-ChildItem -LiteralPath $runTemp -Force)
        if ($remaining.Count -eq 0) {
            Remove-Item -LiteralPath $runTemp -Force
        }
    }
}
