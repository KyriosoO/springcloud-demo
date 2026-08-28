[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$FrozenRepository,

    [Parameter(Mandatory = $true)]
    [string]$AuthorizationPath,

    [Parameter(Mandatory = $true)]
    [string]$ResultRoot,

    [string]$ArtifactRepository = 'D:\codex'
)

$ErrorActionPreference = 'Stop'
$baseLauncher = Join-Path $PSScriptRoot 'run-employee-natural-language-uat-candidate-01.ps1'
& $baseLauncher `
    -FrozenRepository $FrozenRepository `
    -AuthorizationPath $AuthorizationPath `
    -ResultRoot $ResultRoot `
    -ArtifactRepository $ArtifactRepository `
    -ManifestRelativePath 'tests\uat\employee_nl\evidence\employee-natural-language-v1-20260828-candidate-03.manifest.json' `
    -ExpectedRunId 'employee-natural-language-v1-20260828-candidate-03' `
    -ExpectedMaximumModelCalls 26 `
    -ExpectedMaximumEmployeeSearchCalls 28 `
    -RunnerModule 'tests.uat.employee_nl.runner'

if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}
