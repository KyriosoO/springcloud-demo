[CmdletBinding()]
param(
    [string]$PythonExecutable = (Get-Command python.exe -ErrorAction Stop).Source,
    [switch]$TargetedOnly
)

$ErrorActionPreference = 'Stop'

$runtimeRoot = [IO.Path]::GetFullPath((Split-Path -Parent $PSScriptRoot))
$repositoryRoot = [IO.Path]::GetFullPath((Split-Path -Parent $runtimeRoot))
$projectFile = Join-Path $runtimeRoot 'pyproject.toml'
if (-not (Test-Path -LiteralPath $projectFile -PathType Leaf)) {
    throw 'nonlive_regression.project_invalid'
}

$basePython = [IO.Path]::GetFullPath($PythonExecutable)
if (-not (Test-Path -LiteralPath $basePython -PathType Leaf)) {
    throw 'nonlive_regression.python_missing'
}

$temporaryRoot = [IO.Path]::GetFullPath([IO.Path]::GetTempPath())
$runName = 'agent-runtime-nonlive-' + [Guid]::NewGuid().ToString('N')
$runRoot = [IO.Path]::GetFullPath((Join-Path $temporaryRoot $runName))
if (-not $runRoot.StartsWith(
        $temporaryRoot.TrimEnd([IO.Path]::DirectorySeparatorChar) + [IO.Path]::DirectorySeparatorChar,
        [StringComparison]::OrdinalIgnoreCase
    ) -or -not ([IO.Path]::GetFileName($runRoot)).StartsWith(
        'agent-runtime-nonlive-',
        [StringComparison]::Ordinal
    )) {
    throw 'nonlive_regression.temporary_path_invalid'
}

$previousPythonPath = [Environment]::GetEnvironmentVariable('PYTHONPATH', 'Process')
$locationPushed = $false
try {
    & $basePython -c "import sys; raise SystemExit(0 if sys.version_info[:2] == (3, 12) else 1)"
    if ($LASTEXITCODE -ne 0) {
        throw 'nonlive_regression.python_version_invalid'
    }

    New-Item -ItemType Directory -Path $runRoot | Out-Null
    & $basePython -m venv --system-site-packages $runRoot
    if ($LASTEXITCODE -ne 0) {
        throw 'nonlive_regression.venv_create_failed'
    }

    $isolatedPython = Join-Path $runRoot 'Scripts\python.exe'
    if (-not (Test-Path -LiteralPath $isolatedPython -PathType Leaf)) {
        throw 'nonlive_regression.venv_python_missing'
    }

    [Environment]::SetEnvironmentVariable('PYTHONPATH', $null, 'Process')
    & $isolatedPython -m pip install --disable-pip-version-check 'setuptools==80.9.0'
    if ($LASTEXITCODE -ne 0) {
        throw 'nonlive_regression.build_backend_install_failed'
    }
    & $isolatedPython -m pip install --disable-pip-version-check --no-deps --no-build-isolation $runtimeRoot
    if ($LASTEXITCODE -ne 0) {
        throw 'nonlive_regression.install_failed'
    }

    Push-Location -LiteralPath $runtimeRoot
    $locationPushed = $true
    & $isolatedPython -m pytest `
        'tests/integration/adapters/transaction/test_transaction_egress_candidate_v3_host.py' `
        'tests/integration/adapters/transaction/test_transaction_egress_candidate_v4_host.py'
    if ($LASTEXITCODE -ne 0) {
        throw 'nonlive_regression.transaction_host_failed'
    }

    if (-not $TargetedOnly) {
        & $isolatedPython -m pytest
        if ($LASTEXITCODE -ne 0) {
            throw 'nonlive_regression.full_suite_failed'
        }
    }
}
finally {
    if ($locationPushed) {
        Pop-Location
    }
    [Environment]::SetEnvironmentVariable('PYTHONPATH', $previousPythonPath, 'Process')
    if (Test-Path -LiteralPath $runRoot) {
        $resolvedRunRoot = [IO.Path]::GetFullPath((Resolve-Path -LiteralPath $runRoot).Path)
        $expectedPrefix = $temporaryRoot.TrimEnd([IO.Path]::DirectorySeparatorChar) + [IO.Path]::DirectorySeparatorChar
        if (-not $resolvedRunRoot.StartsWith($expectedPrefix, [StringComparison]::OrdinalIgnoreCase) -or
                -not ([IO.Path]::GetFileName($resolvedRunRoot)).StartsWith(
                    'agent-runtime-nonlive-',
                    [StringComparison]::Ordinal
                )) {
            throw 'nonlive_regression.cleanup_path_invalid'
        }
        Remove-Item -LiteralPath $resolvedRunRoot -Recurse -Force
    }
}
