param(
    [Parameter(Mandatory = $true)][string]$BaseUrl,
    [Parameter(Mandatory = $true)][string]$FixtureFile,
    [Parameter(Mandatory = $true)][string]$OutputFile,
    [Parameter(Mandatory = $true)][string]$EnvironmentAttestationDigest,
    [string]$SigningKeyEnvironmentVariable = "AGENT_RELEASE_OBSERVATION_SIGNING_KEY"
)

$ErrorActionPreference = "Stop"
$OutputEncoding = [Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()

function Get-Sha256Hex([byte[]]$Bytes) {
    $sha = [System.Security.Cryptography.SHA256]::Create()
    try { return [Convert]::ToHexString($sha.ComputeHash($Bytes)).ToLowerInvariant() }
    finally { $sha.Dispose() }
}

if ($EnvironmentAttestationDigest -notmatch '^[0-9a-f]{64}$') {
    throw "EnvironmentAttestationDigest 必须是小写 SHA-256。"
}
$signingKey = [Environment]::GetEnvironmentVariable($SigningKeyEnvironmentVariable)
if ([string]::IsNullOrWhiteSpace($signingKey)) {
    throw "缺少隔离 release tooling 签名密钥环境变量。"
}

$fixtureBytes = [IO.File]::ReadAllBytes((Resolve-Path -LiteralPath $FixtureFile))
$fixtureDigest = Get-Sha256Hex $fixtureBytes
$fixtures = $fixtureBytes | ConvertFrom-Json -Depth 64
$observations = [Collections.Generic.List[object]]::new()

foreach ($fixture in $fixtures) {
    $started = [DateTimeOffset]::UtcNow
    try {
        $response = Invoke-RestMethod -Method Post -Uri "$($BaseUrl.TrimEnd('/'))/agent/chat" `
            -ContentType "application/json; charset=utf-8" `
            -Body ($fixture.request | ConvertTo-Json -Depth 64 -Compress) `
            -TimeoutSec ([Math]::Max(1, [int]$fixture.timeoutSeconds))
        $status = "COMPLETED"
        $reason = if ($response.errorCode) { [string]$response.errorCode } else { "NONE" }
        $responseDigest = Get-Sha256Hex ([Text.Encoding]::UTF8.GetBytes(($response | ConvertTo-Json -Depth 64 -Compress)))
    } catch {
        $status = "FAILED"
        $reason = "NORMAL_AGENT_API_FAILURE"
        $responseDigest = "0" * 64
    }
    $observations.Add([ordered]@{
        caseId = [string]$fixture.caseId
        expectedOutcome = [string]$fixture.expectedOutcome
        status = $status
        safeReasonCode = $reason
        responseDigest = $responseDigest
        durationMs = [long]([DateTimeOffset]::UtcNow - $started).TotalMilliseconds
    })
}

$bundle = [ordered]@{
    schemaVersion = "DOC-OBS-1"
    fixtureDigest = $fixtureDigest
    environmentAttestationDigest = $EnvironmentAttestationDigest
    createdAt = [DateTimeOffset]::UtcNow.ToString("O")
    observations = $observations
}
$canonical = $bundle | ConvertTo-Json -Depth 64 -Compress
$hmac = [System.Security.Cryptography.HMACSHA256]::new([Text.Encoding]::UTF8.GetBytes($signingKey))
try { $signature = [Convert]::ToHexString($hmac.ComputeHash([Text.Encoding]::UTF8.GetBytes($canonical))).ToLowerInvariant() }
finally { $hmac.Dispose() }

$signedBundle = [ordered]@{ bundle = $bundle; signatureAlgorithm = "HMAC-SHA256"; signature = $signature }
[IO.File]::WriteAllText((Join-Path (Get-Location) $OutputFile),
    ($signedBundle | ConvertTo-Json -Depth 64), [Text.UTF8Encoding]::new($false))
