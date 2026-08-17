[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$ManifestSha256,
    [string]$RunId = 'transaction-egress-v4-20260817-candidate-04',
    [string]$AuthorizationReference = 'P3_00:GATE-026',
    [string]$RepositoryRoot = (Split-Path -Parent (Split-Path -Parent $PSScriptRoot))
)

$ErrorActionPreference = 'Stop'
$expectedRunId = 'transaction-egress-v4-20260817-candidate-04'
$expectedAuthorizationReference = 'P3_00:GATE-026'
$maximumPaidAnswerCalls = 30
$repository = [IO.Path]::GetFullPath($RepositoryRoot)
if ($repository -ne 'D:\codex') { throw 'transaction.egress_candidate_repository_invalid' }
$runtime = Join-Path $repository 'agent-runtime'
$runtimeSource = Join-Path $runtime 'src'
$evidenceDirectory = Join-Path $runtime 'tests\integration\adapters\transaction\evidence'
$manifestPath = Join-Path $evidenceDirectory "$expectedRunId.manifest.json"
$authorizationPath = Join-Path $evidenceDirectory "$expectedRunId.authorization.json"
$hostJournalPath = Join-Path $evidenceDirectory "$expectedRunId.host-preflight.jsonl"
$hostResultPath = Join-Path $evidenceDirectory "$expectedRunId.host-result.json"
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
if ($actualManifestSha256 -cne $ManifestSha256 -or $manifest.schemaVersion -ne 4 -or
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
        (Test-Path -LiteralPath $hostJournalPath) -or (Test-Path -LiteralPath $hostResultPath) -or
        (Test-Path -LiteralPath $lifecyclePath) -or (Test-Path -LiteralPath $consumedPath) -or
        (Test-Path -LiteralPath $resultPath)) {
    throw 'transaction.egress_candidate_authorization_binding_invalid'
}
$repositoryPrefix = $repository + [IO.Path]::DirectorySeparatorChar
$python = (Get-Command python.exe -ErrorAction Stop).Source
$hostPreflight = Join-Path $runtime 'tests\integration\adapters\transaction\egress_candidate_v4_host.py'
$hostRelativePath = 'agent-runtime/tests/integration/adapters/transaction/egress_candidate_v4_host.py'
$hostAssets = @($manifest.assetHashes | Where-Object { [string]$_.path -ceq $hostRelativePath })
if ($hostAssets.Count -ne 1 -or -not $hostPreflight.StartsWith($repositoryPrefix,[StringComparison]::OrdinalIgnoreCase) -or
        -not (Test-Path -LiteralPath $hostPreflight) -or
        (Get-FileHash -Algorithm SHA256 -LiteralPath $hostPreflight).Hash.ToLowerInvariant() -cne [string]$hostAssets[0].sha256) {
    throw 'transaction.egress_candidate_asset_hash_invalid'
}
& $python $hostPreflight --repository-root $repository --journal $hostJournalPath `
    --result $hostResultPath --manifest-sha256 $ManifestSha256 --manifest $manifestPath
if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $hostResultPath)) {
    throw 'transaction.egress_candidate_host_preflight_failed'
}
$hostResult = Get-Content -LiteralPath $hostResultPath -Raw -Encoding UTF8 | ConvertFrom-Json
if ($hostResult.status -cne 'passed' -or $hostResult.sourceValidated -ne $true -or
        $hostResult.collectionValidated -ne $true -or
        $hostResult.counts.databaseSelectorStatements -ne 0 -or
        $hostResult.counts.transactionSearchRequests -ne 0 -or
        $hostResult.counts.modelOutboundRequests -ne 0) {
    throw 'transaction.egress_candidate_host_preflight_failed'
}

# Secrets and the database selector are reached only after the frozen-source preflight passes.
$apiKey = [Environment]::GetEnvironmentVariable('LLM_API_KEY', 'Process')
$userJwt = [Environment]::GetEnvironmentVariable('TRANSACTION_EGRESS_LIVE_USER_JWT', 'Process')
$baseUrl = [Environment]::GetEnvironmentVariable('TRANSACTION_EGRESS_LIVE_BASE_URL', 'Process')
$databaseUrl = [Environment]::GetEnvironmentVariable('TRANSACTION_EGRESS_LIVE_DB_URL', 'Process')
$databaseUsername = [Environment]::GetEnvironmentVariable('TRANSACTION_EGRESS_LIVE_DB_USERNAME', 'Process')
$databasePassword = [Environment]::GetEnvironmentVariable('TRANSACTION_EGRESS_LIVE_DB_PASSWORD', 'Process')
if ([string]::IsNullOrWhiteSpace($apiKey) -or [string]::IsNullOrWhiteSpace($userJwt) -or
        [string]::IsNullOrWhiteSpace($baseUrl) -or [string]::IsNullOrWhiteSpace($databaseUrl) -or
        [string]::IsNullOrWhiteSpace($databaseUsername) -or [string]::IsNullOrWhiteSpace($databasePassword)) {
    throw 'transaction.egress_candidate_environment_missing'
}

$connector = Get-ChildItem -Path (Join-Path $env:USERPROFILE '.m2\repository\com\mysql\mysql-connector-j') `
    -Recurse -Filter 'mysql-connector-j-*.jar' -File -ErrorAction Stop |
    Where-Object { $_.Name -notmatch '(sources|javadoc)' } |
    Sort-Object FullName -Descending |
    Select-Object -First 1
if ($null -eq $connector) { throw 'transaction.egress_candidate_database_driver_missing' }

$tempRoot = [IO.Path]::GetFullPath([IO.Path]::GetTempPath())
$runRoot = [IO.Path]::GetFullPath((Join-Path $tempRoot "transaction-egress-candidate-$([Guid]::NewGuid().ToString('N'))"))
New-Item -ItemType Directory -Path $runRoot | Out-Null
$selectorSource = Join-Path $runRoot 'TransactionTypeSelector.java'
$selectorErrorPath = Join-Path $runRoot 'selector.err.log'
$stdoutPath = Join-Path $runRoot 'pytest.out.log'
$stderrPath = Join-Path $runRoot 'pytest.err.log'
$names = @(
    'RUN_TRANSACTION_EGRESS_CANDIDATE_04','TRANSACTION_EGRESS_MANIFEST_SHA256',
    'TRANSACTION_EGRESS_LIFECYCLE_OUTPUT','TRANSACTION_EGRESS_RESULT_OUTPUT',
    'TRANSACTION_EGRESS_LIVE_TEST_TYPE','TRANSACTION_EGRESS_SELECTOR_DB_URL',
    'TRANSACTION_EGRESS_SELECTOR_DB_USERNAME','TRANSACTION_EGRESS_SELECTOR_DB_PASSWORD','PYTHONPATH'
)
$snapshot = @{}
foreach ($name in $names) { $snapshot[$name] = [Environment]::GetEnvironmentVariable($name, 'Process') }
try {
    $selectorProgram = @'
import java.sql.Connection;
import java.sql.DriverManager;
import java.sql.PreparedStatement;
import java.sql.ResultSet;

public final class TransactionTypeSelector {
    private static final String SQL = "SELECT TRANS_TYPE FROM t_transaction WHERE TRANS_TYPE IS NOT NULL AND CHAR_LENGTH(TRIM(TRANS_TYPE)) BETWEEN 1 AND 64 ORDER BY TRANS_ID LIMIT 1";

    public static void main(String[] args) throws Exception {
        String url = required("TRANSACTION_EGRESS_SELECTOR_DB_URL");
        String username = required("TRANSACTION_EGRESS_SELECTOR_DB_USERNAME");
        String password = required("TRANSACTION_EGRESS_SELECTOR_DB_PASSWORD");
        try (Connection connection = DriverManager.getConnection(url, username, password);
             PreparedStatement statement = connection.prepareStatement(SQL);
             ResultSet rows = statement.executeQuery()) {
            if (!rows.next()) {
                throw new IllegalStateException("transaction.type_not_found");
            }
            String value = rows.getString(1);
            if (value == null || !value.equals(value.trim()) || value.length() < 1 || value.length() > 64 || containsForbidden(value)) {
                throw new IllegalStateException("transaction.type_invalid");
            }
            System.out.print(value);
        }
    }

    private static String required(String name) {
        String value = System.getenv(name);
        if (value == null || value.isBlank()) {
            throw new IllegalStateException("transaction.selector_environment_missing");
        }
        return value;
    }

    private static boolean containsForbidden(String value) {
        for (int index = 0; index < value.length(); index++) {
            char item = value.charAt(index);
            if (Character.isISOControl(item) || item == '\u202A' || item == '\u202B' ||
                    item == '\u202C' || item == '\u202D' || item == '\u202E' ||
                    item == '\u2066' || item == '\u2067' || item == '\u2068' || item == '\u2069') {
                return true;
            }
        }
        return false;
    }
}
'@
    [IO.File]::WriteAllText($selectorSource, $selectorProgram, [Text.UTF8Encoding]::new($false))
    & javac.exe -encoding UTF-8 -cp $connector.FullName -d $runRoot $selectorSource 2>$selectorErrorPath
    if ($LASTEXITCODE -ne 0) { throw 'transaction.egress_candidate_selector_compile_failed' }

    $env:TRANSACTION_EGRESS_SELECTOR_DB_URL = $databaseUrl
    $env:TRANSACTION_EGRESS_SELECTOR_DB_USERNAME = $databaseUsername
    $env:TRANSACTION_EGRESS_SELECTOR_DB_PASSWORD = $databasePassword
    $queryType = [string](& java.exe -cp "$runRoot;$($connector.FullName)" TransactionTypeSelector 2>$selectorErrorPath)
    if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($queryType)) {
        throw 'transaction.egress_candidate_database_selector_failed'
    }
    Remove-Item Env:\TRANSACTION_EGRESS_SELECTOR_DB_URL -ErrorAction SilentlyContinue
    Remove-Item Env:\TRANSACTION_EGRESS_SELECTOR_DB_USERNAME -ErrorAction SilentlyContinue
    Remove-Item Env:\TRANSACTION_EGRESS_SELECTOR_DB_PASSWORD -ErrorAction SilentlyContinue

    $env:RUN_TRANSACTION_EGRESS_CANDIDATE_04 = '1'
    $env:TRANSACTION_EGRESS_MANIFEST_SHA256 = $ManifestSha256
    $env:TRANSACTION_EGRESS_LIFECYCLE_OUTPUT = $lifecyclePath
    $env:TRANSACTION_EGRESS_RESULT_OUTPUT = $resultPath
    $env:TRANSACTION_EGRESS_LIVE_TEST_TYPE = $queryType
    $env:PYTHONPATH = "$runtimeSource;$runtime"
    $process = Start-Process -FilePath $python -ArgumentList @(
        '-m','pytest','tests/integration/adapters/transaction/test_real_transaction_egress_candidate_v4.py','-q','--tb=no'
    ) -WorkingDirectory $runtime -WindowStyle Hidden -Wait -PassThru `
        -RedirectStandardOutput $stdoutPath -RedirectStandardError $stderrPath
    $combined = ''
    foreach ($path in @($selectorErrorPath,$stdoutPath,$stderrPath)) {
        if (-not (Test-Path -LiteralPath $path) -or (Get-Item -LiteralPath $path).Length -gt 8388608) {
            throw 'transaction.egress_candidate_log_scan_invalid'
        }
        $combined += [string](Get-Content -LiteralPath $path -Raw -Encoding UTF8)
    }
    foreach ($sensitive in @($apiKey,$queryType,$userJwt,$databaseUsername,$databasePassword)) {
        if (-not [string]::IsNullOrEmpty($sensitive) -and $combined.Contains($sensitive,[StringComparison]::Ordinal)) {
            throw 'transaction.egress_candidate_log_leak'
        }
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
    $apiKey=$null; $queryType=$null; $userJwt=$null; $databaseUrl=$null; $databaseUsername=$null; $databasePassword=$null
    if (Test-Path -LiteralPath $runRoot) { Remove-Item -LiteralPath $runRoot -Recurse -Force }
}
