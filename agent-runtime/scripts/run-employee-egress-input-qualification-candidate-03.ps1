[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$runId = 'employee-egress-input-qualification-v3-20260814-candidate-03'
$gateId = 'GATE-049'
$authorizationReference = 'P3_00:GATE-049'
$expectedManifestSha256 = [Environment]::GetEnvironmentVariable(
    'EMPLOYEE_EGRESS_INPUT_QUALIFY_V3_EXPECTED_MANIFEST_SHA256',
    'Process'
)
$repository = 'D:\codex'
$evidenceDirectory = Join-Path $repository 'agent-runtime\tests\integration\adapters\employee\evidence'
$manifestPath = Join-Path $evidenceDirectory "$runId.manifest.json"
$authorizationPath = Join-Path $evidenceDirectory "$runId.authorization.json"
$lifecyclePath = Join-Path $evidenceDirectory "$runId.lifecycle.jsonl"
$resultPath = Join-Path $evidenceDirectory "$runId.result.json"
$pendingPath = Join-Path $evidenceDirectory "$runId.pending.json"
$stagingPath = Join-Path $evidenceDirectory "$runId.qualification-staging.json"
$taskDir = Join-Path $repository 'agent-runtime\.codex-live\employee-qualification-v3'
$mavenLog = Join-Path $taskDir 'maven.log'
$pythonLog = Join-Path $taskDir 'python.log'
$python = (Get-Command python.exe -ErrorAction Stop).Source

if ($env:EMPLOYEE_EGRESS_INPUT_QUALIFY_V3_LIVE_AUTHORIZED -ne '1') {
    throw 'employee.qualification_v3_live_not_authorized'
}
if ($expectedManifestSha256 -notmatch '^[0-9a-f]{64}$') {
    throw 'employee.qualification_v3_manifest_binding_missing'
}
foreach ($requiredName in @(
    'EMPLOYEE_EGRESS_INPUT_QUALIFY_V3_ADMIN_JWT',
    'COMMON_SECURITY_JWT_HMAC_KEY_ACTIVE'
)) {
    $value = [Environment]::GetEnvironmentVariable($requiredName, 'Process')
    if ([string]::IsNullOrWhiteSpace($value)) {
        throw "employee.qualification_v3_env_missing:$requiredName"
    }
}
foreach ($path in @($manifestPath, $authorizationPath)) {
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        throw 'employee.qualification_v3_binding_missing'
    }
}
foreach ($path in @($lifecyclePath, $resultPath, $pendingPath, $stagingPath)) {
    if (Test-Path -LiteralPath $path) {
        throw 'employee.qualification_v3_output_exists'
    }
}

$actualManifestSha256 = (Get-FileHash -LiteralPath $manifestPath -Algorithm SHA256).Hash.ToLowerInvariant()
if ($actualManifestSha256 -ne $expectedManifestSha256) {
    throw 'employee.qualification_v3_manifest_mismatch'
}
$authorization = Get-Content -LiteralPath $authorizationPath -Raw | ConvertFrom-Json
if ($authorization.runId -ne $runId -or
    $authorization.gateId -ne $gateId -or
    $authorization.authorizationReference -ne $authorizationReference -or
    $authorization.manifestSha256 -ne $expectedManifestSha256 -or
    $authorization.liveExecutionAuthorized -ne $false) {
    throw 'employee.qualification_v3_authorization_mismatch'
}
Remove-Item Env:\LLM_API_KEY -ErrorAction SilentlyContinue
$env:PYTHONPATH = (Join-Path $repository 'agent-runtime\src') + ';' + (Join-Path $repository 'agent-runtime')
$env:EMPLOYEE_QUALIFICATION_V3_PREFLIGHT_MANIFEST_SHA = $expectedManifestSha256
& $python -c @'
from pathlib import Path
import os
from tests.integration.adapters.employee.egress_input_qualification_v3 import (
    load_strict_json,
    validate_authorization,
    validate_manifest,
    verify_history,
)
root = Path(r"D:\codex")
run = "employee-egress-input-qualification-v3-20260814-candidate-03"
evidence = root / "agent-runtime/tests/integration/adapters/employee/evidence"
manifest_sha = os.environ["EMPLOYEE_QUALIFICATION_V3_PREFLIGHT_MANIFEST_SHA"]
verify_history(root)
validate_manifest(load_strict_json(evidence / f"{run}.manifest.json"), repository_root=root)
validate_authorization(
    load_strict_json(evidence / f"{run}.authorization.json"),
    manifest_sha256=manifest_sha,
)
'@
Remove-Item Env:\PYTHONPATH -ErrorAction SilentlyContinue
Remove-Item Env:\EMPLOYEE_QUALIFICATION_V3_PREFLIGHT_MANIFEST_SHA -ErrorAction SilentlyContinue
if ($LASTEXITCODE -ne 0) {
    throw 'employee.qualification_v3_preflight_failed'
}

New-Item -ItemType Directory -Path $taskDir -Force | Out-Null
$hostExitCode = 1
$logLeakCount = 0
try {
    $env:RUN_EMPLOYEE_EGRESS_INPUT_QUALIFY_V3 = '1'
    $env:EMPLOYEE_EGRESS_INPUT_QUALIFY_V3_MANIFEST_SHA256 = $expectedManifestSha256
    $env:EMPLOYEE_EGRESS_INPUT_QUALIFY_V3_LIFECYCLE = $lifecyclePath
    $env:EMPLOYEE_EGRESS_INPUT_QUALIFY_V3_RESULT = $resultPath
    $env:EMPLOYEE_EGRESS_INPUT_QUALIFY_V3_PENDING = $pendingPath
    $env:EMPLOYEE_EGRESS_INPUT_QUALIFY_V3_STAGING = $stagingPath
    $env:EMPLOYEE_EGRESS_INPUT_QUALIFY_V3_PYTHON_LOG = $pythonLog
    $env:EMPLOYEE_EGRESS_INPUT_QUALIFY_V3_PYTHON = $python
    $env:EMPLOYEE_EGRESS_INPUT_QUALIFY_V3_REPOSITORY = $repository

    & mvn -f (Join-Path $repository 'serviceCenter\pom.xml') `
        -pl ':employee-service' -am `
        '-Dtest=EmployeeEgressInputQualificationV3LiveIntegrationTest' `
        '-Dsurefire.failIfNoSpecifiedTests=false' test `
        *> $mavenLog
    $hostExitCode = $LASTEXITCODE

    $sensitiveValues = @(
        'synthetic-employee-',
        [Environment]::GetEnvironmentVariable('EMPLOYEE_EGRESS_INPUT_QUALIFY_V3_ADMIN_JWT', 'Process'),
        [Environment]::GetEnvironmentVariable('COMMON_SECURITY_JWT_HMAC_KEY_ACTIVE', 'Process')
    ) | Where-Object { -not [string]::IsNullOrWhiteSpace($_) }
    foreach ($logPath in @($mavenLog, $pythonLog)) {
        if (Test-Path -LiteralPath $logPath -PathType Leaf) {
            foreach ($sensitive in $sensitiveValues) {
                if (Select-String -LiteralPath $logPath -SimpleMatch -Quiet -Pattern $sensitive) {
                    $logLeakCount++
                }
            }
        }
    }
}
finally {
    foreach ($logPath in @($mavenLog, $pythonLog)) {
        Remove-Item -LiteralPath $logPath -Force -ErrorAction SilentlyContinue
    }
    foreach ($name in @(
        'RUN_EMPLOYEE_EGRESS_INPUT_QUALIFY_V3',
        'EMPLOYEE_EGRESS_INPUT_QUALIFY_V3_MANIFEST_SHA256',
        'EMPLOYEE_EGRESS_INPUT_QUALIFY_V3_LIFECYCLE',
        'EMPLOYEE_EGRESS_INPUT_QUALIFY_V3_RESULT',
        'EMPLOYEE_EGRESS_INPUT_QUALIFY_V3_PENDING',
        'EMPLOYEE_EGRESS_INPUT_QUALIFY_V3_STAGING',
        'EMPLOYEE_EGRESS_INPUT_QUALIFY_V3_PYTHON_LOG',
        'EMPLOYEE_EGRESS_INPUT_QUALIFY_V3_PYTHON',
        'EMPLOYEE_EGRESS_INPUT_QUALIFY_V3_REPOSITORY'
    )) {
        Remove-Item "Env:\$name" -ErrorAction SilentlyContinue
    }
}

try {
    if (-not (Test-Path -LiteralPath $pendingPath -PathType Leaf) -or
        -not (Test-Path -LiteralPath $lifecyclePath -PathType Leaf)) {
        throw 'employee.qualification_v3_pending_missing'
    }
    $env:PYTHONPATH = (Join-Path $repository 'agent-runtime\src') + ';' + (Join-Path $repository 'agent-runtime')
    $env:EMPLOYEE_QUALIFICATION_V3_FINAL_MANIFEST_SHA = $expectedManifestSha256
    $env:EMPLOYEE_QUALIFICATION_V3_FINAL_EXIT = [string]$hostExitCode
    $env:EMPLOYEE_QUALIFICATION_V3_FINAL_LEAKS = [string]$logLeakCount
    & $python -c @'
from pathlib import Path
import os
from tests.integration.adapters.employee.egress_input_qualification_v3 import finalize_live_candidate
root = Path(r"D:\codex\agent-runtime\tests\integration\adapters\employee\evidence")
run = "employee-egress-input-qualification-v3-20260814-candidate-03"
finalize_live_candidate(
    lifecycle_path=root / f"{run}.lifecycle.jsonl",
    pending_path=root / f"{run}.pending.json",
    result_path=root / f"{run}.result.json",
    manifest_sha256=os.environ["EMPLOYEE_QUALIFICATION_V3_FINAL_MANIFEST_SHA"],
    host_exit_code=int(os.environ["EMPLOYEE_QUALIFICATION_V3_FINAL_EXIT"]),
    log_leak_count=int(os.environ["EMPLOYEE_QUALIFICATION_V3_FINAL_LEAKS"]),
)
'@
    if ($LASTEXITCODE -ne 0) {
        throw 'employee.qualification_v3_finalize_failed'
    }

    $result = Get-Content -LiteralPath $resultPath -Raw | ConvertFrom-Json
    Remove-Item -LiteralPath $pendingPath -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $stagingPath -Force -ErrorAction SilentlyContinue
    if ($result.status -ne 'qualified') {
        throw "employee.qualification_v3_not_qualified:$($result.reason)"
    }
    Write-Output ([pscustomobject]@{
        status = $result.status
        runId = $runId
        manifestSha256 = $expectedManifestSha256
        lifecycle = $lifecyclePath
        result = $resultPath
    })
}
finally {
    Remove-Item Env:\PYTHONPATH -ErrorAction SilentlyContinue
    Remove-Item Env:\EMPLOYEE_QUALIFICATION_V3_FINAL_MANIFEST_SHA -ErrorAction SilentlyContinue
    Remove-Item Env:\EMPLOYEE_QUALIFICATION_V3_FINAL_EXIT -ErrorAction SilentlyContinue
    Remove-Item Env:\EMPLOYEE_QUALIFICATION_V3_FINAL_LEAKS -ErrorAction SilentlyContinue
}
