[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$ManifestSha256,
    [string]$RunId = 'employee-egress-live-bootstrap-v1-20260817-candidate-01',
    [string]$AuthorizationReference = 'P3_00:GATE-024',
    [string]$RepositoryRoot = (Split-Path -Parent (Split-Path -Parent $PSScriptRoot))
)

$ErrorActionPreference = 'Stop'
$expectedRunId = 'employee-egress-live-bootstrap-v1-20260817-candidate-01'
$expectedAuthorizationReference = 'P3_00:GATE-024'
$repository = [IO.Path]::GetFullPath($RepositoryRoot)
if ($repository -cne 'D:\codex' -or $RunId -cne $expectedRunId -or
        $AuthorizationReference -cne $expectedAuthorizationReference -or
        $ManifestSha256 -cnotmatch '^[0-9a-f]{64}$' -or
        $env:EMPLOYEE_EGRESS_BOOTSTRAP_LIVE_AUTHORIZED -cne '1') {
    throw 'employee.egress_live_bootstrap_authorization_binding_invalid'
}
$python = (Get-Command python.exe -ErrorAction Stop).Source
$previousPythonPath = [Environment]::GetEnvironmentVariable('PYTHONPATH', 'Process')
try {
    $env:PYTHONPATH = (Join-Path $repository 'agent-runtime\src') + ';' +
        (Join-Path $repository 'agent-runtime')
    & $python -m tests.integration.adapters.employee.live_bootstrap_v1 `
        --repository-root $repository --manifest-sha256 $ManifestSha256
    if ($LASTEXITCODE -ne 0) {
        throw 'employee.egress_live_bootstrap_failed'
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
