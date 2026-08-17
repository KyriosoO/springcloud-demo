[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$runId = 'employee-egress-v3-20260817-candidate-03'
$authorizationReference = 'P3_00:GATE-024'
$repository = 'D:\codex'
$evidenceDirectory = Join-Path $repository 'agent-runtime\tests\integration\adapters\employee\evidence'
$manifestPath = Join-Path $evidenceDirectory "$runId.manifest.json"
$authorizationPath = Join-Path $evidenceDirectory "$runId.authorization.json"
$lifecyclePath = Join-Path $evidenceDirectory "$runId.lifecycle.jsonl"
$consumedPath = Join-Path $evidenceDirectory "$runId.authorization.consumed.json"
$pendingPath = Join-Path $evidenceDirectory "$runId.pending.json"
$stagingPath = Join-Path $evidenceDirectory "$runId.staging.json"
$resultPath = Join-Path $evidenceDirectory "$runId.result.json"
$taskDirectory = Join-Path $repository 'agent-runtime\.codex-live\employee-egress-v3'
$mavenLog = Join-Path $taskDirectory 'maven.log'
$pythonLog = Join-Path $taskDirectory 'python.log'
$python = (Get-Command python.exe -ErrorAction Stop).Source
$manifestSha = [Environment]::GetEnvironmentVariable('EMPLOYEE_EGRESS_V3_EXPECTED_MANIFEST_SHA256', 'Process')

if ($env:EMPLOYEE_EGRESS_V3_LIVE_AUTHORIZED -ne '1' -or
        $manifestSha -notmatch '^[0-9a-f]{64}$') {
    throw 'employee.egress_candidate_v3_live_not_authorized'
}
foreach ($name in @(
    'COMMON_SECURITY_JWT_HMAC_KEY_ACTIVE',
    'EMPLOYEE_EGRESS_V3_ADMIN_JWT',
    'LLM_API_KEY'
)) {
    if ([string]::IsNullOrWhiteSpace([Environment]::GetEnvironmentVariable($name, 'Process'))) {
        throw "employee.egress_candidate_v3_env_missing:$name"
    }
}
foreach ($path in @($manifestPath, $authorizationPath)) {
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        throw 'employee.egress_candidate_v3_binding_missing'
    }
}
foreach ($path in @($lifecyclePath, $consumedPath, $pendingPath, $stagingPath, $resultPath)) {
    if (Test-Path -LiteralPath $path) {
        throw 'employee.egress_candidate_v3_output_exists'
    }
}
if ((Get-FileHash -LiteralPath $manifestPath -Algorithm SHA256).Hash.ToLowerInvariant() -cne $manifestSha) {
    throw 'employee.egress_candidate_v3_manifest_mismatch'
}

$env:PYTHONPATH = (Join-Path $repository 'agent-runtime\src') + ';' + (Join-Path $repository 'agent-runtime')
$env:EMPLOYEE_EGRESS_V3_PREFLIGHT_SHA = $manifestSha
& $python -c @'
from pathlib import Path
import os
from tests.integration.adapters.employee.egress_candidate_v3 import (
    RUN_ID, LifecycleJournal, load_strict_json, validate_authorization, validate_manifest,
)
root = Path(r"D:\codex")
evidence = root / "agent-runtime/tests/integration/adapters/employee/evidence"
manifest_sha = os.environ["EMPLOYEE_EGRESS_V3_PREFLIGHT_SHA"]
validate_manifest(load_strict_json(evidence / f"{RUN_ID}.manifest.json"), repository_root=root)
validate_authorization(load_strict_json(evidence / f"{RUN_ID}.authorization.json"), manifest_sha256=manifest_sha)
LifecycleJournal(evidence / f"{RUN_ID}.lifecycle.jsonl", manifest_sha256=manifest_sha)
'@
Remove-Item Env:\EMPLOYEE_EGRESS_V3_PREFLIGHT_SHA -ErrorAction SilentlyContinue
if ($LASTEXITCODE -ne 0) {
    Remove-Item Env:\PYTHONPATH -ErrorAction SilentlyContinue
    throw 'employee.egress_candidate_v3_preflight_failed'
}

New-Item -ItemType Directory -Path $taskDirectory -Force | Out-Null
$hostExitCode = 1
$logLeakCount = 0
try {
    $env:RUN_EMPLOYEE_EGRESS_CANDIDATE_V3 = '1'
    $env:EMPLOYEE_EGRESS_V3_MANIFEST_SHA256 = $manifestSha
    $env:EMPLOYEE_EGRESS_V3_LIFECYCLE = $lifecyclePath
    $env:EMPLOYEE_EGRESS_V3_CONSUMED = $consumedPath
    $env:EMPLOYEE_EGRESS_V3_PENDING = $pendingPath
    $env:EMPLOYEE_EGRESS_V3_STAGING = $stagingPath
    $env:EMPLOYEE_EGRESS_V3_PYTHON = $python
    $env:EMPLOYEE_EGRESS_V3_PYTHON_LOG = $pythonLog
    $env:EMPLOYEE_EGRESS_V3_REPOSITORY = $repository

    & mvn -f (Join-Path $repository 'serviceCenter\pom.xml') `
        -pl ':employee-service' -am `
        '-Dtest=EmployeeEgressCandidateV3LiveIntegrationTest' `
        '-Dsurefire.failIfNoSpecifiedTests=false' test *> $mavenLog
    $hostExitCode = $LASTEXITCODE

    $sensitive = @(
        'synthetic-employee-',
        [Environment]::GetEnvironmentVariable('COMMON_SECURITY_JWT_HMAC_KEY_ACTIVE', 'Process'),
        [Environment]::GetEnvironmentVariable('EMPLOYEE_EGRESS_V3_ADMIN_JWT', 'Process'),
        [Environment]::GetEnvironmentVariable('LLM_API_KEY', 'Process')
    ) | Where-Object { -not [string]::IsNullOrWhiteSpace($_) }
    foreach ($log in @($mavenLog, $pythonLog)) {
        if (Test-Path -LiteralPath $log -PathType Leaf) {
            if ((Get-Item -LiteralPath $log).Length -gt 8388608) {
                $logLeakCount++
                continue
            }
            foreach ($literal in $sensitive) {
                if (Select-String -LiteralPath $log -SimpleMatch -Quiet -Pattern $literal) {
                    $logLeakCount++
                }
            }
        }
    }
}
catch {
    $hostExitCode = 1
}
finally {
    foreach ($log in @($mavenLog, $pythonLog)) {
        Remove-Item -LiteralPath $log -Force -ErrorAction SilentlyContinue
    }
    foreach ($name in @(
        'RUN_EMPLOYEE_EGRESS_CANDIDATE_V3', 'EMPLOYEE_EGRESS_V3_MANIFEST_SHA256',
        'EMPLOYEE_EGRESS_V3_LIFECYCLE', 'EMPLOYEE_EGRESS_V3_CONSUMED',
        'EMPLOYEE_EGRESS_V3_PENDING', 'EMPLOYEE_EGRESS_V3_STAGING',
        'EMPLOYEE_EGRESS_V3_PYTHON', 'EMPLOYEE_EGRESS_V3_PYTHON_LOG',
        'EMPLOYEE_EGRESS_V3_REPOSITORY'
    )) {
        Remove-Item "Env:\$name" -ErrorAction SilentlyContinue
    }
}

$env:EMPLOYEE_EGRESS_V3_FINAL_SHA = $manifestSha
$env:EMPLOYEE_EGRESS_V3_FINAL_EXIT = [string]$hostExitCode
$env:EMPLOYEE_EGRESS_V3_FINAL_LEAKS = [string]$logLeakCount
& $python -c @'
from pathlib import Path
import os
from tests.integration.adapters.employee.egress_candidate_v3 import (
    RUN_ID, finalize_candidate, load_strict_json, write_fallback_pending,
)
root = Path(r"D:\codex\agent-runtime\tests\integration\adapters\employee\evidence")
manifest_sha = os.environ["EMPLOYEE_EGRESS_V3_FINAL_SHA"]
lifecycle = root / f"{RUN_ID}.lifecycle.jsonl"
consumed = root / f"{RUN_ID}.authorization.consumed.json"
pending = root / f"{RUN_ID}.pending.json"
result = root / f"{RUN_ID}.result.json"
host_exit = int(os.environ["EMPLOYEE_EGRESS_V3_FINAL_EXIT"])
log_leaks = int(os.environ["EMPLOYEE_EGRESS_V3_FINAL_LEAKS"])
if not pending.is_file():
    write_fallback_pending(
        lifecycle_path=lifecycle, pending_path=pending, manifest_sha256=manifest_sha
    )
pending_value = load_strict_json(pending)
failure = pending_value["failure"]
finalize_candidate(
    lifecycle_path=lifecycle,
    consumed_path=consumed,
    pending_path=pending,
    result_path=result,
    manifest_sha256=manifest_sha,
    failure_phase=failure["phase"],
    failure_reason=failure["reason"],
    host_exit_code=host_exit,
    log_leak_count=log_leaks,
    raw_logs_deleted=True,
)
'@
$finalizerExitCode = $LASTEXITCODE
Remove-Item Env:\PYTHONPATH -ErrorAction SilentlyContinue
Remove-Item Env:\EMPLOYEE_EGRESS_V3_FINAL_SHA -ErrorAction SilentlyContinue
Remove-Item Env:\EMPLOYEE_EGRESS_V3_FINAL_EXIT -ErrorAction SilentlyContinue
Remove-Item Env:\EMPLOYEE_EGRESS_V3_FINAL_LEAKS -ErrorAction SilentlyContinue
if ($finalizerExitCode -ne 0 -or -not (Test-Path -LiteralPath $resultPath -PathType Leaf)) {
    throw 'employee.egress_candidate_v3_finalize_failed'
}

$result = Get-Content -LiteralPath $resultPath -Raw -Encoding UTF8 | ConvertFrom-Json
Remove-Item -LiteralPath $pendingPath -Force -ErrorAction SilentlyContinue
Remove-Item -LiteralPath $stagingPath -Force -ErrorAction SilentlyContinue
if ($result.status -cne 'passed' -or $result.lifecycle.recordCount -ne 76 -or
        $result.counts.databaseSelectStarted -ne 3 -or $result.counts.databaseInsertStarted -ne 1 -or
        $result.counts.databaseDeleteStarted -ne 1 -or $result.counts.employeeDetailStarted -ne 1 -or
        $result.counts.modelAnswerStarted -ne 30 -or $result.counts.modelAnswerTerminal -ne 30 -or
        $result.counts.validAnswers -lt 27 -or $result.cleanup.deleted -ne 1 -or
        $result.cleanup.remaining -ne 0 -or $result.counts.retryCount -ne 0 -or
        $result.counts.resumeCount -ne 0 -or $result.safety.logLeakCount -ne 0) {
    throw 'employee.egress_candidate_v3_not_passed'
}
[PSCustomObject]@{
    status = $result.status
    runId = $runId
    manifestSha256 = $manifestSha
    paidAnswerCalls = $result.counts.modelAnswerStarted
    lifecycle = $lifecyclePath
    consumed = $consumedPath
    result = $resultPath
}
