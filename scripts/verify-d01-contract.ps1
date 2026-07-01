param(
  [Parameter(Mandatory)] [string]$BaseRef
)

$ErrorActionPreference = 'Stop'
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$ServiceCenter = Join-Path $RepoRoot 'serviceCenter'
$RuntimeRoot = Join-Path $RepoRoot 'agent-runtime'

if ($PSVersionTable.PSEdition -ne 'Core') {
  throw 'PowerShell 7+ (pwsh) is required.'
}

$VenvPython = if ($IsWindows) {
  Join-Path $RuntimeRoot '.venv\Scripts\python.exe'
} else {
  Join-Path $RuntimeRoot '.venv/bin/python'
}
$PythonCommand = Get-Command python -ErrorAction SilentlyContinue
$Python = if (Test-Path -LiteralPath $VenvPython) {
  $VenvPython
} elseif ($null -ne $PythonCommand) {
  $PythonCommand.Source
} else {
  throw 'Python runtime not found in .venv or PATH.'
}
$Maven = if ($IsWindows) {
  Join-Path $ServiceCenter 'mvnw.cmd'
} else {
  Join-Path $ServiceCenter 'mvnw'
}

function Invoke-Checked {
  param(
    [Parameter(Mandatory)] [string]$WorkingDirectory,
    [Parameter(Mandatory)] [string]$FilePath,
    [Parameter(Mandatory)] [string[]]$Arguments
  )
  Push-Location $WorkingDirectory
  try {
    & $FilePath @Arguments
    if ($LASTEXITCODE -ne 0) {
      throw "command failed ($LASTEXITCODE): $FilePath $($Arguments -join ' ')"
    }
  } finally {
    Pop-Location
  }
}

function Assert-NoMatches {
  param(
    [Parameter(Mandatory)] [string]$Pattern,
    [Parameter(Mandatory)] [string[]]$Paths
  )
  $files = foreach ($path in $Paths) {
    $absolute = Join-Path $RepoRoot $path
    if (-not (Test-Path -LiteralPath $absolute)) {
      throw "static-check path not found: $absolute"
    }
    $item = Get-Item -LiteralPath $absolute
    if ($item.PSIsContainer) {
      Get-ChildItem -LiteralPath $absolute -Recurse -File | Where-Object {
        $_.Extension -in @('.java', '.py', '.json', '.yaml', '.yml', '.md', '.ps1')
      }
    } else {
      $item
    }
  }
  $matches = @($files | Select-String -Pattern $Pattern)
  if ($matches.Count -gt 0) {
    $sample = $matches | Select-Object -First 20 | Out-String
    throw "forbidden pattern found: $Pattern`n$sample"
  }
}

function Assert-AllowedPaths {
  param([Parameter(Mandatory)] [string]$CompareRef)
  Push-Location $RepoRoot
  try {
    $base = (& git merge-base HEAD $CompareRef).Trim()
    if ($LASTEXITCODE -ne 0 -or -not $base) {
      throw "cannot resolve merge-base for $CompareRef"
    }
    $allowedFiles = @(
      'agent-api/pom.xml',
      'scripts/verify-d01-contract.ps1',
      '.github/workflows/agent-contract.yml',
      '.cnb.yml',
      '.cnb/d01-contract.Dockerfile',
      'serviceCenter/mvnw',
      'docs/design/D01_Agent契约生成与治理_L2实施详细设计_v1.0.md'
    )
    $violations = & git diff --name-only $base HEAD | Where-Object {
      $_ -notmatch '^agent-api/src/main/java/com/dylan/agent/api/contract/runtime/' -and
      $_ -notmatch '^agent-api/src/test/java/com/dylan/agent/api/contract/' -and
      $_ -notmatch '^agent-api/src/test/resources/contract/candidate/' -and
      $_ -notmatch '^agent-runtime/(scripts|tests)/target_contract/' -and
      $_ -notin $allowedFiles
    }
    if ($violations) {
      throw "D01 changed-path violations:`n$($violations -join "`n")"
    }
  } finally {
    Pop-Location
  }
}

if (-not (Test-Path -LiteralPath $Maven)) {
  throw "Maven wrapper not found: $Maven"
}
Invoke-Checked $ServiceCenter $Maven @(
  '-pl', '../agent-api', 'test', '--batch-mode'
)
Invoke-Checked $RuntimeRoot $Python @(
  'scripts/target_contract/check_contract_drift.py'
)
Invoke-Checked $RuntimeRoot $Python @(
  '-m', 'pytest', 'tests/target_contract', '-q'
)
Invoke-Checked $RuntimeRoot $Python @('-m', 'pytest', '-q')
Invoke-Checked $ServiceCenter $Maven @(
  '-pl', '../agent-service', '-am', 'test', '--batch-mode'
)

Assert-NoMatches -Pattern 'com\.dylan\.agent\.api\.contract\.runtime' -Paths @(
  'agent-service/src/main', 'agent-runtime/app'
)
Assert-NoMatches -Pattern 'AgentIntent|ClarifyAgentPlan|planVersion|strategyVersion' -Paths @(
  'agent-api/src/main/java/com/dylan/agent/api/contract/runtime',
  'agent-api/src/test/resources/contract/candidate/openapi',
  'agent-api/src/test/resources/contract/candidate/fixtures'
)
Assert-NoMatches -Pattern 'merge_duplicate_enums|deduplicate_aliased_enums|remove_root_model_wrappers|fix_alias_patterns|add_upper_enum_aliases|fix_discriminator_bases|model_rebuild' -Paths @(
  'agent-runtime/scripts/target_contract'
)
Assert-NoMatches -Pattern 'app\.contracts\.(generated_models|models)' -Paths @(
  'agent-runtime/tests/target_contract'
)

Assert-AllowedPaths $BaseRef

Write-Host 'D01 contract governance verification passed.'
