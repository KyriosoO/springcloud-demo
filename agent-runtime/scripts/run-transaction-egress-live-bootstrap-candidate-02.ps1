[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$ManifestSha256,
    [string]$RunId = 'transaction-egress-live-bootstrap-v2-20260818-candidate-02',
    [string]$AuthorizationReference = 'P3_00:GATE-061',
    [string]$RepositoryRoot = (Split-Path -Parent (Split-Path -Parent $PSScriptRoot))
)

$ErrorActionPreference = 'Stop'
$expectedRunId = 'transaction-egress-live-bootstrap-v2-20260818-candidate-02'
$expectedAuthorizationReference = 'P3_00:GATE-061'
$repository = [IO.Path]::GetFullPath($RepositoryRoot)
if ($repository -cne 'D:\codex' -or $RunId -cne $expectedRunId -or
        $AuthorizationReference -cne $expectedAuthorizationReference -or
        $ManifestSha256 -cnotmatch '^[0-9a-f]{64}$' -or
        $env:TRANSACTION_EGRESS_BOOTSTRAP_V2_LIVE_AUTHORIZED -cne '1') {
    throw 'transaction.egress_live_bootstrap_v2_authorization_binding_invalid'
}

$python = (Get-Command python.exe -ErrorAction Stop).Source
$previousPythonPath = [Environment]::GetEnvironmentVariable('PYTHONPATH', 'Process')
try {
    $env:PYTHONPATH = (Join-Path $repository 'agent-runtime\src') + ';' +
        (Join-Path $repository 'agent-runtime')
    & $python -m tests.integration.adapters.transaction.live_bootstrap_v2 `
        --repository-root $repository --manifest-sha256 $ManifestSha256
    if ($LASTEXITCODE -ne 0) {
        throw 'transaction.egress_live_bootstrap_v2_failed'
    }
}
finally {
    if ($null -eq $previousPythonPath) {
        Remove-Item Env:\PYTHONPATH -ErrorAction SilentlyContinue
    }
    else {
        [Environment]::SetEnvironmentVariable('PYTHONPATH', $previousPythonPath, 'Process')
    }
}
