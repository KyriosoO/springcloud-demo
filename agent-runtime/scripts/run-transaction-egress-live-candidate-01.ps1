[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$ManifestSha256,
    [string]$RunId = 'transaction-egress-v1-20260814-candidate-01',
    [string]$AuthorizationReference = 'P3_00:GATE-026',
    [string]$RepositoryRoot = (Split-Path -Parent (Split-Path -Parent $PSScriptRoot))
)

$ErrorActionPreference = 'Stop'
$expectedRunId = 'transaction-egress-v1-20260814-candidate-01'
$expectedAuthorizationReference = 'P3_00:GATE-026'
$maximumPaidAnswerCalls = 30
$repository = [IO.Path]::GetFullPath($RepositoryRoot)
if ($repository -ne 'D:\codex') { throw 'transaction.egress_candidate_repository_invalid' }
$evidenceDirectory = Join-Path $repository 'agent-runtime\tests\integration\adapters\transaction\evidence'
$manifestPath = Join-Path $evidenceDirectory "$expectedRunId.manifest.json"
$authorizationPath = Join-Path $evidenceDirectory "$expectedRunId.authorization.json"
$lifecyclePath = Join-Path $evidenceDirectory "$expectedRunId.lifecycle.jsonl"
$consumedPath = Join-Path $evidenceDirectory "$expectedRunId.authorization.consumed.json"
$resultPath = Join-Path $evidenceDirectory "$expectedRunId.result.json"

if ($RunId -cne $expectedRunId -or $AuthorizationReference -cne $expectedAuthorizationReference -or
        $ManifestSha256 -notmatch '^[0-9a-f]{64}$' -or -not (Test-Path -LiteralPath $manifestPath) -or
        -not (Test-Path -LiteralPath $authorizationPath)) {
    throw 'transaction.egress_candidate_authorization_binding_invalid'
}
$actualManifestSha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $manifestPath).Hash.ToLowerInvariant()
$manifest = Get-Content -LiteralPath $manifestPath -Raw -Encoding UTF8 | ConvertFrom-Json
$authorization = Get-Content -LiteralPath $authorizationPath -Raw -Encoding UTF8 | ConvertFrom-Json
if ($actualManifestSha256 -cne $ManifestSha256 -or $manifest.schemaVersion -ne 1 -or
        $manifest.status -cne 'prepared_unconsumed' -or $manifest.runId -cne $expectedRunId -or
        $manifest.authorizationReference -cne $expectedAuthorizationReference -or
        $manifest.executionBoundary.transactionSearchMaximum -ne 1 -or
        $manifest.executionBoundary.paidAnswerMaximum -ne $maximumPaidAnswerCalls -or
        $manifest.executionBoundary.retryAllowed -ne $false -or
        $manifest.executionBoundary.resumeAllowed -ne $false -or
        $authorization.runId -cne $expectedRunId -or
        $authorization.manifestSha256 -cne $ManifestSha256 -or
        $authorization.authorizationReference -cne $expectedAuthorizationReference -or
        $authorization.liveExecutionAuthorized -ne $false -or
        (Test-Path -LiteralPath $lifecyclePath) -or (Test-Path -LiteralPath $consumedPath) -or
        (Test-Path -LiteralPath $resultPath)) {
    throw 'transaction.egress_candidate_authorization_binding_invalid'
}
$repositoryPrefix = $repository + [IO.Path]::DirectorySeparatorChar
foreach ($asset in @($manifest.history) + @($manifest.assetHashes)) {
    $assetPath = [IO.Path]::GetFullPath((Join-Path $repository ([string]$asset.path)))
    if (-not $assetPath.StartsWith($repositoryPrefix, [StringComparison]::OrdinalIgnoreCase) -or
            -not (Test-Path -LiteralPath $assetPath) -or
            (Get-FileHash -Algorithm SHA256 -LiteralPath $assetPath).Hash.ToLowerInvariant() -cne [string]$asset.sha256) {
        throw 'transaction.egress_candidate_asset_hash_invalid'
    }
}

# Secrets are read only after immutable binding succeeds.
$apiKey = [Environment]::GetEnvironmentVariable('LLM_API_KEY', 'Process')
$queryType = [Environment]::GetEnvironmentVariable('TRANSACTION_EGRESS_LIVE_TEST_TYPE', 'Process')
$userJwt = [Environment]::GetEnvironmentVariable('TRANSACTION_EGRESS_LIVE_USER_JWT', 'Process')
$baseUrl = [Environment]::GetEnvironmentVariable('TRANSACTION_EGRESS_LIVE_BASE_URL', 'Process')
if ([string]::IsNullOrWhiteSpace($apiKey) -or [string]::IsNullOrWhiteSpace($queryType) -or
        [string]::IsNullOrWhiteSpace($userJwt) -or [string]::IsNullOrWhiteSpace($baseUrl)) {
    throw 'transaction.egress_candidate_environment_missing'
}

$python = (Get-Command python.exe -ErrorAction Stop).Source
$tempRoot = [IO.Path]::GetFullPath([IO.Path]::GetTempPath())
$runRoot = [IO.Path]::GetFullPath((Join-Path $tempRoot "transaction-egress-candidate-$([Guid]::NewGuid().ToString('N'))"))
New-Item -ItemType Directory -Path $runRoot | Out-Null
$stdoutPath = Join-Path $runRoot 'pytest.out.log'
$stderrPath = Join-Path $runRoot 'pytest.err.log'
$names = @('RUN_TRANSACTION_EGRESS_CANDIDATE_01','TRANSACTION_EGRESS_MANIFEST_SHA256','TRANSACTION_EGRESS_LIFECYCLE_OUTPUT','TRANSACTION_EGRESS_RESULT_OUTPUT')
$snapshot = @{}
foreach ($name in $names) { $snapshot[$name] = [Environment]::GetEnvironmentVariable($name, 'Process') }
try {
    $env:RUN_TRANSACTION_EGRESS_CANDIDATE_01 = '1'
    $env:TRANSACTION_EGRESS_MANIFEST_SHA256 = $ManifestSha256
    $env:TRANSACTION_EGRESS_LIFECYCLE_OUTPUT = $lifecyclePath
    $env:TRANSACTION_EGRESS_RESULT_OUTPUT = $resultPath
    $process = Start-Process -FilePath $python -ArgumentList @(
        '-m','pytest','tests/integration/adapters/transaction/test_real_transaction_egress_candidate.py','-q','--tb=no'
    ) -WorkingDirectory (Join-Path $repository 'agent-runtime') -WindowStyle Hidden -Wait -PassThru `
        -RedirectStandardOutput $stdoutPath -RedirectStandardError $stderrPath
    $combined = ''
    foreach ($path in @($stdoutPath,$stderrPath)) {
        if (-not (Test-Path -LiteralPath $path) -or (Get-Item -LiteralPath $path).Length -gt 8388608) {
            throw 'transaction.egress_candidate_log_scan_invalid'
        }
        $combined += [string](Get-Content -LiteralPath $path -Raw -Encoding UTF8)
    }
    if ($combined.Contains($apiKey,[StringComparison]::Ordinal) -or
            $combined.Contains($queryType,[StringComparison]::Ordinal) -or
            $combined.Contains($userJwt,[StringComparison]::Ordinal)) {
        throw 'transaction.egress_candidate_log_leak'
    }
    if ($process.ExitCode -ne 0 -or -not (Test-Path -LiteralPath $resultPath)) {
        if (Test-Path -LiteralPath $consumedPath) { throw 'transaction.egress_candidate_execution_failed_consumed' }
        if (Test-Path -LiteralPath $lifecyclePath) { throw 'transaction.egress_candidate_execution_failed_unconsumed' }
        throw 'transaction.egress_candidate_initialization_failed'
    }
    $result = Get-Content -LiteralPath $resultPath -Raw -Encoding UTF8 | ConvertFrom-Json
    if ($result.status -cne 'passed' -or $result.counts.transactionSearchStarted -ne 1 -or
            $result.counts.answerStarted -ne $maximumPaidAnswerCalls -or
            $result.counts.answerTerminal -ne $maximumPaidAnswerCalls -or
            $result.counts.validAnswers -lt 27 -or $result.counts.retryCount -ne 0 -or
            $result.counts.resumeCount -ne 0 -or $result.safety.forbiddenPayloadFieldCount -ne 0 -or
            $result.safety.forbiddenLiteralCount -ne 0 -or $result.safety.logLeakCount -ne 0) {
        throw 'transaction.egress_candidate_result_invalid'
    }
    [PSCustomObject]@{ status='passed'; runId=$expectedRunId; transactionSearches=1; paidAnswerCalls=30; result=$resultPath }
}
finally {
    foreach ($name in $names) {
        $oldValue = $snapshot[$name]
        if ($null -eq $oldValue) { Remove-Item "Env:\$name" -ErrorAction SilentlyContinue }
        else { [Environment]::SetEnvironmentVariable($name,[string]$oldValue,'Process') }
    }
    $apiKey=$null; $queryType=$null; $userJwt=$null
    if (Test-Path -LiteralPath $runRoot) { Remove-Item -LiteralPath $runRoot -Recurse -Force }
}
