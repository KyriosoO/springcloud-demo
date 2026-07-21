[CmdletBinding()]
param(
  [Parameter(Mandatory)]
  [ValidateSet('Preflight', 'BeginStage', 'Checkpoint', 'RecoveryCheck', 'PostApply')]
  [string]$Mode,

  [Parameter(Mandatory)]
  [string]$OutputPath,

  [string]$ExpectedHead,
  [string]$AuthorizationRef,
  [string]$ExternalConsumerResolutionRef,
  [string]$RunId,
  [ValidateSet('RENAME_PROJECT', 'ARCHIVE_GIT_LINEAGE', 'VERIFY_TARGET_REACTOR', 'CREATE_TARGET_PROJECT', 'ISOLATE_RUNTIME_ENTRY', 'FINAL_VALIDATION')]
  [string]$Stage,
  [string]$ItemId,
  [string]$ExpectedEffect
)

$ErrorActionPreference = 'Stop'
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$ScriptPath = $MyInvocation.MyCommand.Path
$ExpectedOutputRelativePath = 'docs/design/agent/evidence/baseline-isolation/p0/baseline-isolation-report.json'
$ExpectedExternalEvidenceRelativePath = 'docs/design/agent/evidence/baseline-isolation/p0/external-consumer-resolution.json'
$LineageCommit = 'b9db2ee0e552d5063aae8bd07ef398532736ed77'
$ExternalEvidenceDesignHashes = [ordered]@{
  overview = [ordered]@{ path = 'docs/design/agent/L2/00_单体Agent目标架构L2实施详细设计总览_v1.0.md'; sha256 = 'B3EFEECBF534B234F4A5D2CB3EBADEBE1594636F157ECF25D4353E20CD677BE0' }
  isolation = [ordered]@{ path = 'docs/design/agent/L2/02_目标基线隔离与迁移门禁_L2实施详细设计_v1.0.md'; sha256 = 'F9CCDF6987884A654AC46DC336B5C7F209107093A1842D440A3F85D85551141C' }
  exitDesign = [ordered]@{ path = 'docs/design/agent/L2/02A_外部消费者活动基线退出与DB-02-001关闭_L2实施详细设计_v1.0.md'; sha256 = '108856C320E35234B445ECA1044959FB276464F5BEEA3882A64E30621C1FA9CD' }
  l0 = [ordered]@{ path = 'docs/design/agent/单体Agent智能体总体架构_L0_v1.0.md'; sha256 = '5EECECDB784B78C7E0089AA9A16C6DD1959A58A0C61BA649270837C5C4385968' }
  agentL1 = [ordered]@{ path = 'docs/design/agent/单体Agent应用与能力架构_L1_v1.0.md'; sha256 = '152466BABD621DA498188D4C1BD5AE19E6E07EF0D8CD8CB5B23DBF9751B6AAB4' }
  retrievalL1 = [ordered]@{ path = 'docs/design/agent/检索与索引基础设施架构_L1_v1.0.md'; sha256 = '83C7EA8385F44755BE2D821693ABED0B19D0A51A98893FDEC3BFD9F12938F42A' }
}
$ExpectedDesignHashes = [ordered]@{
  overview = [ordered]@{ path = 'docs/design/agent/L2/00_单体Agent目标架构L2实施详细设计总览_v1.0.md'; sha256 = 'EC07BDC8CA8556F0F5AF52E4E630180559317221C8BAF44BB26E3040C57DD45D' }
  isolation = [ordered]@{ path = 'docs/design/agent/L2/02_目标基线隔离与迁移门禁_L2实施详细设计_v1.0.md'; sha256 = '2A75E29B681D646915B1AE88F05B2B0B1E1C000EC69F13B548E01BAB53CC490F' }
  exitDesign = [ordered]@{ path = 'docs/design/agent/L2/02A_外部消费者活动基线退出与DB-02-001关闭_L2实施详细设计_v1.0.md'; sha256 = '47210DEC764D33B704CF457AA0DCB30F46599B9173EA3C3C16DB27FB97639CE9' }
  l0 = [ordered]@{ path = 'docs/design/agent/单体Agent智能体总体架构_L0_v1.0.md'; sha256 = '5EECECDB784B78C7E0089AA9A16C6DD1959A58A0C61BA649270837C5C4385968' }
  agentL1 = [ordered]@{ path = 'docs/design/agent/单体Agent应用与能力架构_L1_v1.0.md'; sha256 = '152466BABD621DA498188D4C1BD5AE19E6E07EF0D8CD8CB5B23DBF9751B6AAB4' }
  retrievalL1 = [ordered]@{ path = 'docs/design/agent/检索与索引基础设施架构_L1_v1.0.md'; sha256 = '83C7EA8385F44755BE2D821693ABED0B19D0A51A98893FDEC3BFD9F12938F42A' }
}
$ProjectMappings = @(
  [ordered]@{ itemId = 'PRJ-01'; source = 'agent-adapter-api'; alpha = 'agent-adapter-api_alpha'; kind = 'JAVA_LIBRARY' },
  [ordered]@{ itemId = 'PRJ-02'; source = 'agent-adapter-document'; alpha = 'agent-adapter-document_alpha'; kind = 'JAVA_LIBRARY' },
  [ordered]@{ itemId = 'PRJ-03'; source = 'agent-adapter-employee'; alpha = 'agent-adapter-employee_alpha'; kind = 'JAVA_LIBRARY' },
  [ordered]@{ itemId = 'PRJ-04'; source = 'agent-adapter-transaction'; alpha = 'agent-adapter-transaction_alpha'; kind = 'JAVA_LIBRARY' },
  [ordered]@{ itemId = 'PRJ-05'; source = 'agent-api'; alpha = 'agent-api_alpha'; kind = 'JAVA_LIBRARY' },
  [ordered]@{ itemId = 'PRJ-06'; source = 'agent-runtime'; alpha = 'agent-runtime_alpha'; kind = 'PYTHON_RUNTIME' },
  [ordered]@{ itemId = 'PRJ-07'; source = 'agent-service'; alpha = 'agent-service_alpha'; kind = 'JAVA_SERVICE' },
  [ordered]@{ itemId = 'PRJ-08'; source = 'es-query-api'; alpha = 'es-query-api_alpha'; kind = 'JAVA_LIBRARY' },
  [ordered]@{ itemId = 'PRJ-09'; source = 'es-query-service'; alpha = 'es-query-service_alpha'; kind = 'JAVA_SERVICE' },
  [ordered]@{ itemId = 'PRJ-10'; source = 'document-provider-adapter'; alpha = 'document-provider-adapter_alpha'; kind = 'JAVA_SERVICE' }
)
$ExpectedLineagePaths = @(
  'document-generation-adapter/pom.xml',
  'document-generation-adapter/src/main/java/com/dylan/documentgeneration/DeepSeekDocumentGenerationClient.java',
  'document-generation-adapter/src/main/java/com/dylan/documentgeneration/DeepSeekGenerationProperties.java',
  'document-generation-adapter/src/main/java/com/dylan/documentgeneration/DocumentGenerationAdapterApplication.java',
  'document-generation-adapter/src/main/java/com/dylan/documentgeneration/DocumentGenerationAdapterConfiguration.java',
  'document-generation-adapter/src/main/java/com/dylan/documentgeneration/DocumentGenerationController.java',
  'document-generation-adapter/src/main/resources/application.yml',
  'document-generation-adapter/src/test/java/com/dylan/documentgeneration/DeepSeekDocumentGenerationClientTest.java'
)

if ($PSVersionTable.PSEdition -ne 'Core' -or $PSVersionTable.PSVersion.Major -lt 7) {
  Write-Error 'PARAMETER_INVALID: PowerShell 7+ (pwsh) is required.'
  exit 30
}

function Invoke-Git {
  param([Parameter(Mandatory)][string[]]$Arguments, [switch]$AllowExitOne)
  Push-Location $RepoRoot
  try {
    $output = @(& git -c core.quotepath=false @Arguments 2>&1 | ForEach-Object { $_.ToString() })
    $code = $LASTEXITCODE
  } finally {
    Pop-Location
  }
  if ($code -ne 0 -and -not ($AllowExitOne -and $code -eq 1)) {
    throw "TOOL_ERROR: git $($Arguments -join ' ') failed ($code): $($output -join "`n")"
  }
  return [ordered]@{ output = $output; exitCode = $code }
}

function Get-Sha256 {
  param([Parameter(Mandatory)][string]$Path)
  if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
    throw "BASELINE_CHECK_FAILED: required file is missing: $Path"
  }
  return (Get-FileHash -Algorithm SHA256 -LiteralPath $Path).Hash.ToUpperInvariant()
}

function Get-AbsoluteRepoPath {
  param([Parameter(Mandatory)][string]$Path)
  $absolute = if ([IO.Path]::IsPathRooted($Path)) { [IO.Path]::GetFullPath($Path) } else { [IO.Path]::GetFullPath((Join-Path $RepoRoot $Path)) }
  $prefix = $RepoRoot.TrimEnd([IO.Path]::DirectorySeparatorChar) + [IO.Path]::DirectorySeparatorChar
  if (-not $absolute.StartsWith($prefix, [StringComparison]::OrdinalIgnoreCase)) {
    throw "PARAMETER_INVALID: path is outside repository: $Path"
  }
  return $absolute
}

function Get-OutputAbsolutePath {
  $actual = Get-AbsoluteRepoPath $OutputPath
  $expected = [IO.Path]::GetFullPath((Join-Path $RepoRoot $ExpectedOutputRelativePath))
  if (-not [string]::Equals($actual, $expected, [StringComparison]::OrdinalIgnoreCase)) {
    throw "PARAMETER_INVALID: OutputPath must be $ExpectedOutputRelativePath"
  }
  return $actual
}

function Get-ExternalEvidenceAbsolutePath {
  if ([string]::IsNullOrWhiteSpace($ExternalConsumerResolutionRef)) {
    throw 'PARAMETER_INVALID: Preflight requires ExternalConsumerResolutionRef.'
  }
  $actual = Get-AbsoluteRepoPath $ExternalConsumerResolutionRef
  $expected = [IO.Path]::GetFullPath((Join-Path $RepoRoot $ExpectedExternalEvidenceRelativePath))
  if (-not [string]::Equals($actual, $expected, [StringComparison]::OrdinalIgnoreCase)) {
    throw "PARAMETER_INVALID: ExternalConsumerResolutionRef must be $ExpectedExternalEvidenceRelativePath"
  }
  return $actual
}

function Write-JsonAtomic {
  param([Parameter(Mandatory)][object]$Value, [Parameter(Mandatory)][string]$Path)
  $directory = Split-Path -Parent $Path
  if (-not (Test-Path -LiteralPath $directory)) {
    New-Item -ItemType Directory -Path $directory -Force | Out-Null
  }
  $lockPath = $Path + '.lock'
  $tempPath = Join-Path $directory ('.' + [IO.Path]::GetFileName($Path) + '.' + [guid]::NewGuid().ToString('N') + '.tmp')
  $lock = $null
  try {
    $lock = [IO.File]::Open($lockPath, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write, [IO.FileShare]::None)
    $json = $Value | ConvertTo-Json -Depth 20
    $roundTrip = $json | ConvertFrom-Json
    if ([string]::IsNullOrWhiteSpace([string]$roundTrip.schemaVersion)) {
      throw 'REPORT_SCHEMA_INVALID: schemaVersion is required.'
    }
    [IO.File]::WriteAllText($tempPath, $json + "`n", [Text.UTF8Encoding]::new($false))
    [IO.File]::Move($tempPath, $Path, $true)
  } catch [IO.IOException] {
    throw "STAGE_OWNERSHIP_UNCERTAIN: report lock is unavailable: $lockPath"
  } finally {
    if ($null -ne $lock) { $lock.Dispose() }
    if (Test-Path -LiteralPath $tempPath) { Remove-Item -LiteralPath $tempPath -Force }
    if ($null -ne $lock -and (Test-Path -LiteralPath $lockPath)) { Remove-Item -LiteralPath $lockPath -Force }
  }
}

function Read-Report {
  $path = Get-OutputAbsolutePath
  if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
    throw "REPORT_SCHEMA_INVALID: report not found: $ExpectedOutputRelativePath"
  }
  try { $report = Get-Content -Raw -Encoding UTF8 -LiteralPath $path | ConvertFrom-Json } catch { throw 'REPORT_SCHEMA_INVALID: report is not valid JSON.' }
  if ($report.schemaVersion -ne '1.0' -or [string]::IsNullOrWhiteSpace([string]$report.runId) -or [string]::IsNullOrWhiteSpace([string]$report.state)) {
    throw 'REPORT_SCHEMA_INVALID: required report identity is missing.'
  }
  return $report
}

function Sync-VerifierProvenance {
  param(
    [Parameter(Mandatory)][object]$Report,
    [Parameter(Mandatory)][string]$ModeName
  )
  $currentSha = Get-Sha256 $ScriptPath
  if ([string]$Report.verifierSha256 -eq $currentSha) { return }
  if ($null -eq $Report.preflightVerifierSha256) {
    $Report | Add-Member -NotePropertyName preflightVerifierSha256 -NotePropertyValue ([string]$Report.verifierSha256)
  }
  if ($null -eq $Report.verifierTransitions) {
    $Report | Add-Member -NotePropertyName verifierTransitions -NotePropertyValue @()
  }
  $Report.verifierTransitions = @($Report.verifierTransitions) + [ordered]@{
    fromSha256 = [string]$Report.verifierSha256
    toSha256 = $currentSha
    reason = 'IN_RUN_VERIFIER_DEFECT_FIXED'
    mode = $ModeName
    at = [DateTimeOffset]::UtcNow.ToString('o')
  }
  $Report.verifierSha256 = $currentSha
}

function Test-CompletedTransition {
  param(
    [Parameter(Mandatory)][object]$Report,
    [Parameter(Mandatory)][string]$StageName,
    [Parameter(Mandatory)][string]$StageItem
  )
  return @($Report.transitions | Where-Object {
      $_.stage -eq $StageName -and $_.itemId -eq $StageItem -and $_.status -eq 'COMPLETED'
    }).Count -eq 1
}

function Update-ReportProgress {
  param([Parameter(Mandatory)][object]$Report)

  foreach ($mapping in $ProjectMappings) {
    $item = @($Report.items | Where-Object { $_.itemId -eq $mapping.itemId }) | Select-Object -First 1
    if ($null -eq $item) { throw "REPORT_SCHEMA_INVALID: missing item: $($mapping.itemId)" }
    $archived = Test-CompletedTransition -Report $Report -StageName 'RENAME_PROJECT' -StageItem $mapping.itemId
    $created = Test-CompletedTransition -Report $Report -StageName 'CREATE_TARGET_PROJECT' -StageItem $mapping.itemId
    $item.status = if ($created) { 'TARGET_CREATED' } elseif ($archived) { 'LEGACY_ARCHIVED' } else { 'PENDING' }
    $item | Add-Member -NotePropertyName archiveStatus -NotePropertyValue $(if ($archived) { 'ARCHIVED' } else { 'PENDING' }) -Force
    $item | Add-Member -NotePropertyName targetStatus -NotePropertyValue $(if ($created) { 'CREATED' } else { 'PENDING' }) -Force
  }

  $lineageArchived = Test-CompletedTransition -Report $Report -StageName 'ARCHIVE_GIT_LINEAGE' -StageItem 'LIN-01'
  $Report.historicalLineage.status = if ($lineageArchived) { 'ARCHIVED' } else { 'PENDING' }
  $allArchived = $lineageArchived -and @($Report.items | Where-Object { $_.archiveStatus -ne 'ARCHIVED' }).Count -eq 0
  $allCreated = $allArchived -and @($Report.items | Where-Object { $_.targetStatus -ne 'CREATED' }).Count -eq 0
  $entryIsolated = Test-CompletedTransition -Report $Report -StageName 'ISOLATE_RUNTIME_ENTRY' -StageItem 'ENTRY-ISOLATION'
  $reactorVerified = Test-CompletedTransition -Report $Report -StageName 'VERIFY_TARGET_REACTOR' -StageItem 'TARGET-REACTOR'

  if ($Report.state -ne 'P0_VERIFIED') {
    $Report.state = if ($allCreated -and $entryIsolated -and $reactorVerified) {
      'TARGET_REACTOR_ISOLATED'
    } elseif ($allCreated) {
      'TARGET_SKELETON_CREATED'
    } elseif ($allArchived) {
      'LEGACY_ASSETS_ARCHIVED'
    } else {
      'PREFLIGHT_PASSED'
    }
  }
}

function Get-StringSha256 {
  param([AllowEmptyString()][string]$Value)
  $bytes = [Text.Encoding]::UTF8.GetBytes($Value)
  return [Convert]::ToHexString([Security.Cryptography.SHA256]::HashData($bytes))
}

function Normalize-Text {
  param([AllowEmptyString()][string]$Value)
  return $Value.Replace("`r`n", "`n").TrimEnd()
}

function Assert-ExactPathSet {
  param(
    [Parameter(Mandatory)][string[]]$Expected,
    [Parameter(Mandatory)][string[]]$Actual,
    [Parameter(Mandatory)][string]$Label
  )
  $difference = @(Compare-Object @($Expected | Sort-Object) @($Actual | Sort-Object))
  if ($difference.Count -gt 0) {
    $formatted = @($difference | ForEach-Object { [string]$_.SideIndicator + [string]$_.InputObject }) -join ','
    throw "LEGACY_ASSET_INTEGRITY_FAILED: unexpected path set for ${Label}: $formatted"
  }
}

function Get-ExpectedAlphaPomText {
  param(
    [Parameter(Mandatory)][string]$Commit,
    [Parameter(Mandatory)][string]$Source,
    [Parameter(Mandatory)][string]$Alpha
  )
  $pomText = Normalize-Text ((Invoke-Git @('show', "${Commit}:$Source/pom.xml")).output -join "`n")
  foreach ($mapping in $ProjectMappings) {
    if ($mapping.kind -ne 'PYTHON_RUNTIME') {
      $pomText = $pomText.Replace("<artifactId>$($mapping.source)</artifactId>", "<artifactId>$($mapping.alpha)</artifactId>")
    }
  }
  $pomText = $pomText.Replace('<artifactId>document-generation-adapter</artifactId>', '<artifactId>document-generation-adapter_alpha</artifactId>')
  $pomText = $pomText.Replace("<name>$Source</name>", "<name>$Alpha</name>")
  return $pomText
}

function Get-ManifestSummary {
  param([Parameter(Mandatory)][string[]]$RelativePaths)
  $entries = @($RelativePaths | Sort-Object | ForEach-Object {
      $normalized = $_.Replace('\', '/')
      "$normalized=$(Get-Sha256 (Join-Path $RepoRoot $normalized))"
    })
  return [ordered]@{ fileCount = $entries.Count; sha256 = Get-StringSha256 ($entries -join "`n") }
}

function Get-FixedHistoryEvidence {
  param([Parameter(Mandatory)][object]$Report)
  return @(
    foreach ($entry in @(
        [ordered]@{ source = 'scripts/verify-d01-contract.ps1'; history = 'docs/design/agent/evidence/baseline-isolation/p0/history/scripts/verify-d01-contract.ps1' },
        [ordered]@{ source = '.github/workflows/agent-contract.yml'; history = 'docs/design/agent/evidence/baseline-isolation/p0/history/workflows/agent-contract.yml' }
      )) {
      $expectedObject = ((Invoke-Git @('rev-parse', "$($Report.sourceCommit):$($entry.source)")).output | Select-Object -First 1).Trim()
      $actualObject = ((Invoke-Git @('hash-object', "--path=$($entry.source)", '--', $entry.history)).output | Select-Object -First 1).Trim()
      if ($actualObject -ne $expectedObject) { throw "CI_AUTHORITY_CONFLICT: fixed history content drift: $($entry.history)" }
      [ordered]@{ sourcePath = $entry.source; historyPath = $entry.history; sourceObjectId = $expectedObject; historyObjectId = $actualObject; status = 'ARCHIVED_EXACT' }
    }
  )
}

function Update-ReportFileEvidence {
  param([Parameter(Mandatory)][object]$Report)
  foreach ($mapping in $ProjectMappings) {
    $item = @($Report.items | Where-Object { $_.itemId -eq $mapping.itemId }) | Select-Object -First 1
    $alphaPaths = @((Invoke-Git @('ls-files', '-co', '--exclude-standard', '--', $mapping.alpha)).output | Where-Object { $_ })
    $targetRoot = Join-Path $RepoRoot $mapping.source
    $targetPaths = @(Get-ChildItem -LiteralPath $targetRoot -Recurse -File | Where-Object { $_.FullName -notmatch '[\\/](target|__pycache__)[\\/]' } | ForEach-Object { $_.FullName.Substring($RepoRoot.Length + 1).Replace('\', '/') })
    $alphaManifest = Get-ManifestSummary -RelativePaths $alphaPaths
    $targetManifest = Get-ManifestSummary -RelativePaths $targetPaths
    $item | Add-Member -NotePropertyName archiveTrackedFileCount -NotePropertyValue $alphaManifest.fileCount -Force
    $item | Add-Member -NotePropertyName archiveManifestSha256 -NotePropertyValue $alphaManifest.sha256 -Force
    $item | Add-Member -NotePropertyName targetFileCount -NotePropertyValue $targetManifest.fileCount -Force
    $item | Add-Member -NotePropertyName targetManifestSha256 -NotePropertyValue $targetManifest.sha256 -Force
    $item | Add-Member -NotePropertyName alphaIgnoredEnvironmentPresence -NotePropertyValue ([ordered]@{
        env = Test-Path -LiteralPath (Join-Path $RepoRoot "$($mapping.alpha)/.env")
        venv = Test-Path -LiteralPath (Join-Path $RepoRoot "$($mapping.alpha)/.venv")
      }) -Force
  }
  $Report | Add-Member -NotePropertyName fixedHistory -NotePropertyValue @(Get-FixedHistoryEvidence -Report $Report) -Force
}

function Assert-RunIdentity {
  param([Parameter(Mandatory)][object]$Report)
  if ([string]::IsNullOrWhiteSpace($RunId) -or $Report.runId -ne $RunId) {
    throw 'REPORT_SCHEMA_INVALID: RunId does not match the report.'
  }
}

function Assert-DesignBaseline {
  $actual = [ordered]@{}
  foreach ($key in $ExpectedDesignHashes.Keys) {
    $entry = $ExpectedDesignHashes[$key]
    $hash = Get-Sha256 (Join-Path $RepoRoot $entry.path)
    if ($hash -ne $entry.sha256) {
      throw "DESIGN_BASELINE_CHANGED: $key expected=$($entry.sha256) actual=$hash"
    }
    $actual[$key] = $hash
  }
  return $actual
}

function Get-CurrentDocumentHashes {
  $actual = [ordered]@{}
  foreach ($key in $ExpectedDesignHashes.Keys) {
    $actual[$key] = Get-Sha256 (Join-Path $RepoRoot $ExpectedDesignHashes[$key].path)
  }
  return $actual
}

function Assert-CleanExpectedHead {
  if ([string]::IsNullOrWhiteSpace($ExpectedHead) -or $ExpectedHead -notmatch '^[0-9a-fA-F]{40}$') {
    throw 'PARAMETER_INVALID: Preflight requires a full 40-character ExpectedHead.'
  }
  $head = ((Invoke-Git @('rev-parse', 'HEAD')).output | Select-Object -First 1).Trim()
  if ($head -ne $ExpectedHead.ToLowerInvariant()) {
    throw "PREFLIGHT_FAILED: ExpectedHead=$ExpectedHead actual=$head"
  }
  $status = @((Invoke-Git @('status', '--porcelain=v1', '--untracked-files=all')).output)
  if ($status.Count -gt 0) {
    throw "PREFLIGHT_FAILED: worktree must be clean; changed=$($status -join ',')"
  }
  return $head
}

function Assert-ProjectMappingPreflight {
  foreach ($mapping in $ProjectMappings) {
    if (-not (Test-Path -LiteralPath (Join-Path $RepoRoot $mapping.source) -PathType Container)) {
      throw "PROJECT_MAPPING_CONFLICT: source directory is missing: $($mapping.source)"
    }
    if (Test-Path -LiteralPath (Join-Path $RepoRoot $mapping.alpha)) {
      throw "PROJECT_MAPPING_CONFLICT: alpha destination already exists: $($mapping.alpha)"
    }
  }
  if (Test-Path -LiteralPath (Join-Path $RepoRoot 'document-generation-adapter_alpha')) {
    throw 'PROJECT_MAPPING_CONFLICT: document-generation-adapter_alpha already exists.'
  }
}

function Assert-LineagePreflight {
  $objectCheck = Invoke-Git @('cat-file', '-e', "$LineageCommit^{commit}")
  if ($objectCheck.exitCode -ne 0) { throw "PREFLIGHT_FAILED: lineage commit is unreadable: $LineageCommit" }
  $lines = @((Invoke-Git @('ls-tree', '-r', '--full-tree', $LineageCommit, '--', 'document-generation-adapter')).output | Where-Object { $_ })
  if ($lines.Count -ne $ExpectedLineagePaths.Count) {
    throw "LEGACY_ASSET_INTEGRITY_FAILED: LIN-01 expected $($ExpectedLineagePaths.Count) files, actual=$($lines.Count)"
  }
  $actualPaths = @()
  foreach ($line in $lines) {
    if ($line -notmatch '^100644 blob [0-9a-f]{40}\t(.+)$') {
      throw "LEGACY_ASSET_INTEGRITY_FAILED: LIN-01 contains a non-100644 entry: $line"
    }
    $actualPaths += $Matches[1]
  }
  if (@(Compare-Object ($ExpectedLineagePaths | Sort-Object) ($actualPaths | Sort-Object)).Count -gt 0) {
    throw 'LEGACY_ASSET_INTEGRITY_FAILED: LIN-01 path set changed.'
  }
  if (-not (Get-Command git -ErrorAction SilentlyContinue) -or -not (Get-Command tar -ErrorAction SilentlyContinue)) {
    throw 'PREFLIGHT_FAILED: git archive and tar are required.'
  }
  $generationPath = Join-Path $RepoRoot 'document-generation-adapter'
  if (Test-Path -LiteralPath $generationPath) {
    $unignored = @((Invoke-Git @('ls-files', '--others', '--exclude-standard', '--', 'document-generation-adapter')).output | Where-Object { $_ })
    $tracked = @((Invoke-Git @('ls-files', '--', 'document-generation-adapter')).output | Where-Object { $_ })
    if ($unignored.Count -gt 0 -or $tracked.Count -gt 0) {
      throw 'PREFLIGHT_FAILED: current document-generation-adapter contains tracked or unignored content.'
    }
  }
  return @($lines | ForEach-Object {
      if ($_ -match '^100644 blob ([0-9a-f]{40})\t(.+)$') { [ordered]@{ mode = '100644'; objectId = $Matches[1]; path = $Matches[2] } }
    })
}

function Assert-RelevantProcessesStopped {
  foreach ($port in @(9201, 9220, 9230)) {
    $listeners = @(Get-NetTCPConnection -State Listen -LocalPort $port -ErrorAction SilentlyContinue)
    if ($listeners.Count -gt 0) {
      throw "PREFLIGHT_FAILED: relevant port $port is listening; pid=$(@($listeners.OwningProcess | Sort-Object -Unique) -join ',')"
    }
  }
  $processes = @(Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object {
      $_.ProcessId -ne $PID -and $_.Name -match '^(java|javaw|python|python3|py)\.exe$' -and $_.CommandLine -match '(?i)(agent-runtime|agent-service|es-query-service|document-provider-adapter|document-generation-adapter)'
    })
  if ($processes.Count -gt 0) {
    throw "PREFLIGHT_FAILED: related process is running; pid=$(@($processes.ProcessId | Sort-Object -Unique) -join ',')"
  }
}

function Assert-ExternalConsumerEvidence {
  param(
    [Parameter(Mandatory)][string]$Path,
    [Parameter(Mandatory)][string]$CurrentHead,
    [switch]$ValidateResultManifest
  )
  try { $evidence = Get-Content -Raw -Encoding UTF8 -LiteralPath $Path | ConvertFrom-Json } catch { throw 'EXTERNAL_CONSUMER_UNRESOLVED: evidence is not valid JSON.' }
  if ($evidence.schemaVersion -ne '1.0' -or $evidence.status -ne 'CONSUMER_EXIT_VERIFIED' -or
      $evidence.closureSemantics -ne 'CLOSED_FOR_P0_BY_INACTIVITY' -or
      $evidence.closureEstablishedBy -ne 'CONSUMER_EXIT_VERIFIED_REPORT_PUBLICATION' -or
      $evidence.p0PreflightRole -ne 'REVALIDATE_AND_GATE_ONLY' -or @($evidence.unresolvedItems).Count -ne 0) {
    throw 'EXTERNAL_CONSUMER_UNRESOLVED: closure fields are incomplete.'
  }
  foreach ($key in @('overview', 'isolation', 'exitDesign')) {
    if ($evidence.designHashes.$key -ne $ExternalEvidenceDesignHashes[$key].sha256) {
      throw "EXTERNAL_CONSUMER_UNRESOLVED: design hash mismatch: $key"
    }
  }
  if ($ValidateResultManifest) {
    foreach ($entry in @($evidence.resultFileManifest)) {
      $absolute = Join-Path $RepoRoot $entry.path
      if ((Get-Sha256 $absolute) -ne $entry.sha256) {
        throw "EXTERNAL_CONSUMER_UNRESOLVED: result manifest drift: $($entry.path)"
      }
    }
  }
  $ancestor = Invoke-Git @('merge-base', '--is-ancestor', [string]$evidence.baselineCommit, $CurrentHead) -AllowExitOne
  if ($ancestor.exitCode -ne 0) { throw 'EXTERNAL_CONSUMER_UNRESOLVED: baselineCommit is not an ancestor of ExpectedHead.' }
  $employeeChanges = @((Invoke-Git @('diff', '--name-only', "$($evidence.baselineCommit)..$CurrentHead", '--', 'employee-service')).output | Where-Object { $_ })
  if ($employeeChanges.Count -gt 0) { throw 'EXTERNAL_CONSUMER_UNRESOLVED: employee-service changed after the closure baseline.' }
  return [ordered]@{ path = $ExpectedExternalEvidenceRelativePath; sha256 = Get-Sha256 $Path; resolutionId = $evidence.resolutionId; status = $evidence.status }
}

function Get-ReferenceClassifications {
  $textExtensions = @('.xml', '.ps1', '.psm1', '.sh', '.cmd', '.bat', '.yml', '.yaml', '.properties', '.toml', '.gradle', '.kts', '.py', '.html', '.java', '.json', '.md', '.config', '.conf', '.ini')
  $tokens = '(?i)(agent-adapter-(?:api|document|employee|transaction)|agent-api|agent-runtime|agent-service|es-query-(?:api|service)|document-provider-adapter|document-generation-adapter)(?:_alpha)?'
  $classifications = [ordered]@{ must_archive_history = @(); must_remain_target = @(); evidence_only = @(); forbidden_active_alpha_reference = @() }
  $files = @((Invoke-Git @('ls-files', '-co', '--exclude-standard', '-z')).output -join "`n" -split "`0" | Where-Object { $_ })
  foreach ($relativeRaw in $files) {
    $relative = $relativeRaw.Replace('\', '/')
    $absolute = Join-Path $RepoRoot $relative
    if (-not (Test-Path -LiteralPath $absolute -PathType Leaf) -or [IO.Path]::GetExtension($relative) -notin $textExtensions) { continue }
    try { $content = Get-Content -Raw -Encoding UTF8 -LiteralPath $absolute } catch { continue }
    if ($content -notmatch $tokens) { continue }
    if ($relative -match '^(agent-adapter-(?:api|document|employee|transaction)|agent-api|agent-runtime|agent-service|es-query-(?:api|service)|document-provider-adapter|document-generation-adapter)_alpha(?:/|$)') {
      $classifications.must_archive_history += $relative
    } elseif ($relative -match '^docs/design/agent/evidence/baseline-isolation/p0/history/') {
      $classifications.must_archive_history += $relative
    } elseif ($relative -match '^docs/' -or $relative -in @('scripts/verify-agent-baseline-isolation.ps1', 'scripts/verify-agent-external-consumer-exit.ps1')) {
      $classifications.evidence_only += $relative
    } elseif ($content -match '(?i)(agent-adapter-(?:api|document|employee|transaction)|agent-api|agent-runtime|agent-service|es-query-(?:api|service)|document-provider-adapter|document-generation-adapter)_alpha(?![A-Za-z0-9_])') {
      $classifications.forbidden_active_alpha_reference += $relative
    } else {
      $classifications.must_remain_target += $relative
    }
  }
  foreach ($key in @($classifications.Keys)) { $classifications[$key] = @($classifications[$key] | Sort-Object -Unique) }
  if ($classifications.forbidden_active_alpha_reference.Count -gt 0) {
    throw "ACTIVE_ALPHA_REFERENCE_FORBIDDEN: $($classifications.forbidden_active_alpha_reference -join ',')"
  }
  return $classifications
}

function New-PreflightReport {
  param([string]$Head, [object]$DesignHashes, [object]$ExternalEvidence, [object[]]$Lineage, [object]$ReferenceClassifications)
  $now = [DateTimeOffset]::UtcNow.ToString('o')
  $newRunId = 'P0-' + [DateTimeOffset]::UtcNow.ToString('yyyyMMddTHHmmssfffZ') + '-' + [guid]::NewGuid().ToString('N').Substring(0, 8)
  return [ordered]@{
    schemaVersion = '1.0'; runId = $newRunId; sourceCommit = $Head; verifierSha256 = Get-Sha256 $ScriptPath
    designHashes = $DesignHashes; authorization = [ordered]@{ reference = $AuthorizationRef; implementerPid = $PID; exclusive = $true }
    externalConsumerResolutionRef = $ExternalEvidence; state = 'PREFLIGHT_PASSED'; currentStage = $null; pendingStage = $null
    items = @($ProjectMappings | ForEach-Object { [ordered]@{ itemId = $_.itemId; action = 'RENAME_AND_RECREATE'; sourcePath = $_.source; alphaPath = $_.alpha; targetPath = $_.source; kind = $_.kind; status = 'PENDING' } })
    historicalLineage = [ordered]@{ itemId = 'LIN-01'; sourceCommit = $LineageCommit; alphaPath = 'document-generation-adapter_alpha'; status = 'PENDING'; entries = $Lineage }
    transitions = @([ordered]@{ from = 'IMPLEMENTATION_AUTHORIZED'; to = 'PREFLIGHT_PASSED'; at = $now; mode = 'Preflight' })
    checks = @(
      [ordered]@{ id = 'HEAD_AND_WORKTREE'; status = 'PASSED' }, [ordered]@{ id = 'DESIGN_BASELINE'; status = 'PASSED' },
      [ordered]@{ id = 'PROJECT_MAPPING'; status = 'PASSED' }, [ordered]@{ id = 'LIN_01'; status = 'PASSED' },
      [ordered]@{ id = 'EXTERNAL_CONSUMER'; status = 'PASSED' }, [ordered]@{ id = 'PROCESS_ISOLATION'; status = 'PASSED' },
      [ordered]@{ id = 'REFERENCE_CLASSIFICATION'; status = 'PASSED' }
    )
    referenceClassifications = $ReferenceClassifications
    esMigrationCandidates = @([ordered]@{ source = 'legacy ES query/index/alias mechanisms'; classification = 'PENDING_CONFIRMATION'; owner = 'future retrieval/index detailed design'; action = 'NO_COPY_NO_WRITE' })
    failureCodes = @(); unresolvedItems = @(); createdAt = $now; updatedAt = $now
  }
}

function Invoke-Preflight {
  [void](Get-OutputAbsolutePath)
  if ([string]::IsNullOrWhiteSpace($AuthorizationRef)) { throw 'PARAMETER_INVALID: Preflight requires AuthorizationRef.' }
  $head = Assert-CleanExpectedHead
  $designHashes = Assert-DesignBaseline
  Assert-ProjectMappingPreflight
  $lineage = @(Assert-LineagePreflight)
  Assert-RelevantProcessesStopped
  $externalPath = Get-ExternalEvidenceAbsolutePath
  $externalEvidence = Assert-ExternalConsumerEvidence -Path $externalPath -CurrentHead $head -ValidateResultManifest
  $references = Get-ReferenceClassifications
  $report = New-PreflightReport -Head $head -DesignHashes $designHashes -ExternalEvidence $externalEvidence -Lineage $lineage -ReferenceClassifications $references
  Write-JsonAtomic -Value $report -Path (Get-OutputAbsolutePath)
  $report | ConvertTo-Json -Depth 20
}

function Invoke-BeginStage {
  foreach ($value in @($RunId, $Stage, $ItemId, $ExpectedEffect)) { if ([string]::IsNullOrWhiteSpace($value)) { throw 'PARAMETER_INVALID: BeginStage requires RunId, Stage, ItemId, and ExpectedEffect.' } }
  $report = Read-Report; Assert-RunIdentity $report
  Update-ReportProgress -Report $report
  if ($null -ne $report.currentStage -or $null -ne $report.pendingStage -or @($report.transitions | Where-Object { $_.status -eq 'STARTED' }).Count -gt 0) {
    throw 'RECOVERY_REQUIRED: another stage is still STARTED.'
  }
  $allowedStates = switch ($Stage) {
    { $_ -in @('RENAME_PROJECT', 'ARCHIVE_GIT_LINEAGE') } { @('PREFLIGHT_PASSED'); break }
    'CREATE_TARGET_PROJECT' { @('LEGACY_ASSETS_ARCHIVED'); break }
    { $_ -in @('ISOLATE_RUNTIME_ENTRY', 'VERIFY_TARGET_REACTOR') } { @('TARGET_SKELETON_CREATED', 'TARGET_REACTOR_ISOLATED'); break }
    'FINAL_VALIDATION' { @('TARGET_REACTOR_ISOLATED'); break }
  }
  if ($report.state -notin $allowedStates) { throw "RECOVERY_REQUIRED: stage=$Stage cannot begin from state=$($report.state)" }
  if ($Stage -in @('RENAME_PROJECT', 'CREATE_TARGET_PROJECT') -and @($ProjectMappings | Where-Object { $_.itemId -eq $ItemId }).Count -ne 1) {
    throw "REPORT_SCHEMA_INVALID: unknown project item: $ItemId"
  }
  if ($Stage -eq 'ARCHIVE_GIT_LINEAGE' -and $ItemId -ne 'LIN-01') { throw 'REPORT_SCHEMA_INVALID: lineage item must be LIN-01.' }
  if ($Stage -eq 'ISOLATE_RUNTIME_ENTRY' -and $ItemId -ne 'ENTRY-ISOLATION') { throw 'REPORT_SCHEMA_INVALID: runtime item must be ENTRY-ISOLATION.' }
  if ($Stage -eq 'VERIFY_TARGET_REACTOR' -and $ItemId -ne 'TARGET-REACTOR') { throw 'REPORT_SCHEMA_INVALID: reactor item must be TARGET-REACTOR.' }
  if ($Stage -eq 'FINAL_VALIDATION' -and $ItemId -ne 'FINAL-GATE') { throw 'REPORT_SCHEMA_INVALID: final item must be FINAL-GATE.' }
  if (@($report.transitions | Where-Object { $_.stage -eq $Stage -and $_.itemId -eq $ItemId }).Count -gt 0) { throw 'STAGE_OWNERSHIP_UNCERTAIN: duplicate stage item is forbidden.' }
  $transition = [ordered]@{ stage = $Stage; itemId = $ItemId; expectedEffect = $ExpectedEffect; status = 'STARTED'; at = [DateTimeOffset]::UtcNow.ToString('o') }
  $report.transitions = @($report.transitions) + $transition; $report.currentStage = $Stage; $report.pendingStage = $ItemId; $report.updatedAt = $transition.at
  Sync-VerifierProvenance -Report $report -ModeName 'BeginStage'
  Write-JsonAtomic -Value $report -Path (Get-OutputAbsolutePath); $transition | ConvertTo-Json -Depth 6
}

function Assert-CheckpointPostcondition {
  param([string]$StageName, [string]$StageItem, [Parameter(Mandatory)][object]$Report)
  $mapping = @($ProjectMappings | Where-Object { $_.itemId -eq $StageItem }) | Select-Object -First 1
  switch ($StageName) {
    'RENAME_PROJECT' {
      if ($null -eq $mapping -or (Test-Path -LiteralPath (Join-Path $RepoRoot $mapping.source)) -or -not (Test-Path -LiteralPath (Join-Path $RepoRoot $mapping.alpha) -PathType Container)) { throw 'BASELINE_CHECK_FAILED: project rename postcondition failed.' }
    }
    'ARCHIVE_GIT_LINEAGE' {
      if ($StageItem -ne 'LIN-01' -or -not (Test-Path -LiteralPath (Join-Path $RepoRoot 'document-generation-adapter_alpha') -PathType Container)) { throw 'BASELINE_CHECK_FAILED: LIN-01 archive postcondition failed.' }
    }
    'CREATE_TARGET_PROJECT' {
      if ($null -eq $mapping -or -not (Test-Path -LiteralPath (Join-Path $RepoRoot $mapping.source) -PathType Container) -or -not (Test-Path -LiteralPath (Join-Path $RepoRoot $mapping.alpha) -PathType Container)) { throw 'TARGET_NOT_GREENFIELD: target creation postcondition failed.' }
    }
    'VERIFY_TARGET_REACTOR' { Assert-NoActiveAlphaReferences }
    'ISOLATE_RUNTIME_ENTRY' { Assert-RuntimeEntryIsolation -Report $Report }
    'FINAL_VALIDATION' { return @(Invoke-FinalValidations -Report $Report) }
  }
  return @()
}

function Invoke-Checkpoint {
  foreach ($value in @($RunId, $Stage, $ItemId)) { if ([string]::IsNullOrWhiteSpace($value)) { throw 'PARAMETER_INVALID: Checkpoint requires RunId, Stage, and ItemId.' } }
  $report = Read-Report; Assert-RunIdentity $report
  $matches = @($report.transitions | Where-Object { $_.stage -eq $Stage -and $_.itemId -eq $ItemId })
  if ($matches.Count -ne 1 -or $matches[0].status -ne 'STARTED') { throw 'RECOVERY_REQUIRED: exactly one matching STARTED transition is required.' }
  $allStarted = @($report.transitions | Where-Object { $_.status -eq 'STARTED' })
  if ($allStarted.Count -ne 1 -or $report.currentStage -ne $Stage -or $report.pendingStage -ne $ItemId) {
    throw 'RECOVERY_REQUIRED: report stage ownership does not match the requested checkpoint.'
  }
  $validationResults = @(Assert-CheckpointPostcondition -StageName $Stage -StageItem $ItemId -Report $report)
  if ($Stage -eq 'FINAL_VALIDATION') {
    if ($validationResults.Count -ne 6 -or @($validationResults | Where-Object { $_.status -ne 'PASSED' }).Count -gt 0) {
      throw 'P0_GATE_NOT_MET: FINAL_VALIDATION evidence is incomplete.'
    }
    $report | Add-Member -NotePropertyName validationResults -NotePropertyValue $validationResults -Force
    $report.checks = @($report.checks | Where-Object { $_.id -ne 'P0_COMPREHENSIVE_VALIDATION' }) + [ordered]@{ id = 'P0_COMPREHENSIVE_VALIDATION'; status = 'PASSED'; resultCount = $validationResults.Count }
  }
  $matches[0].status = 'COMPLETED'; $matches[0] | Add-Member -NotePropertyName completedAt -NotePropertyValue ([DateTimeOffset]::UtcNow.ToString('o')) -Force
  $report.currentStage = $null; $report.pendingStage = $null; $report.updatedAt = $matches[0].completedAt
  Update-ReportProgress -Report $report
  Sync-VerifierProvenance -Report $report -ModeName 'Checkpoint'
  Write-JsonAtomic -Value $report -Path (Get-OutputAbsolutePath); $matches[0] | ConvertTo-Json -Depth 6
}

function Assert-NoActiveAlphaReferences {
  [xml]$pom = Get-Content -Raw -Encoding UTF8 -LiteralPath (Join-Path $RepoRoot 'serviceCenter/pom.xml')
  if (($pom.OuterXml) -match '(?i)_alpha') { throw 'ACTIVE_ALPHA_REFERENCE_FORBIDDEN: serviceCenter/pom.xml contains alpha.' }
  $references = Get-ReferenceClassifications
  if ($references.forbidden_active_alpha_reference.Count -gt 0) { throw 'ACTIVE_ALPHA_REFERENCE_FORBIDDEN: active alpha reference found.' }
}

function Assert-RuntimeEntryIsolation {
  param([Parameter(Mandatory)][object]$Report)
  $start = Get-Content -Raw -Encoding UTF8 -LiteralPath (Join-Path $RepoRoot 'scripts/start-all-services.ps1')
  foreach ($pattern in @('(?i)agent-service', '(?i)es-query-service', '(?i)agent-runtime', '(?i)document-provider-adapter', '(?i)document-generation-adapter')) {
    if ($start -match $pattern) { throw "DEFAULT_START_NOT_ISOLATED: $pattern" }
  }
  $historyScript = Join-Path $RepoRoot 'docs/design/agent/evidence/baseline-isolation/p0/history/scripts/verify-d01-contract.ps1'
  $historyWorkflow = Join-Path $RepoRoot 'docs/design/agent/evidence/baseline-isolation/p0/history/workflows/agent-contract.yml'
  if (-not (Test-Path -LiteralPath $historyScript -PathType Leaf) -or -not (Test-Path -LiteralPath $historyWorkflow -PathType Leaf)) { throw 'CI_AUTHORITY_CONFLICT: fixed history entry is missing.' }
  [void]@(Get-FixedHistoryEvidence -Report $Report)
  $workflow = Get-Content -Raw -Encoding UTF8 -LiteralPath (Join-Path $RepoRoot '.github/workflows/agent-contract.yml')
  foreach ($forbidden in @('verify-d01-contract', 'baseline-isolation/p0/history', 'document-generation-adapter_alpha')) {
    if ($workflow -match [regex]::Escape($forbidden)) { throw "CI_AUTHORITY_CONFLICT: active workflow references history: $forbidden" }
  }
  foreach ($required in @('agent-api', 'agent-service', 'agent-adapter-api', 'agent-adapter-document', 'agent-adapter-employee', 'agent-adapter-transaction', 'agent-runtime', 'es-query-api', 'es-query-service', 'document-provider-adapter', 'python -m unittest')) {
    if ($workflow -notmatch [regex]::Escape($required)) { throw "CI_AUTHORITY_CONFLICT: active target gate is incomplete: $required" }
  }
}

function Assert-ArchivedAssetIntegrity {
  param([Parameter(Mandatory)][object]$Report)

  $head = ((Invoke-Git @('rev-parse', 'HEAD')).output | Select-Object -First 1).Trim()
  if ($head -ne [string]$Report.sourceCommit) { throw "SOURCE_COMMIT_CHANGED: expected=$($Report.sourceCommit) actual=$head" }
  foreach ($mapping in $ProjectMappings) {
    $trackedPaths = @((Invoke-Git @('ls-tree', '-r', '--name-only', [string]$Report.sourceCommit, '--', $mapping.source)).output | Where-Object { $_ })
    if ($trackedPaths.Count -eq 0) { throw "LEGACY_ASSET_INTEGRITY_FAILED: source tree is empty: $($mapping.source)" }
    $expectedAlphaPaths = @($trackedPaths | ForEach-Object { $mapping.alpha + $_.Substring($mapping.source.Length) })
    $actualAlphaPaths = @((Invoke-Git @('ls-files', '-co', '--exclude-standard', '--', $mapping.alpha)).output | Where-Object { $_ })
    Assert-ExactPathSet -Expected $expectedAlphaPaths -Actual $actualAlphaPaths -Label $mapping.alpha
    foreach ($oldPath in $trackedPaths) {
      $suffix = $oldPath.Substring($mapping.source.Length).TrimStart('/')
      $newPath = "$($mapping.alpha)/$suffix"
      $absolute = Join-Path $RepoRoot $newPath
      if (-not (Test-Path -LiteralPath $absolute -PathType Leaf)) { throw "LEGACY_ASSET_INTEGRITY_FAILED: missing $newPath" }
      if ($suffix -ne 'pom.xml') {
        $expectedObject = ((Invoke-Git @('rev-parse', "$($Report.sourceCommit):$oldPath")).output | Select-Object -First 1).Trim()
        $actualObject = ((Invoke-Git @('hash-object', "--path=$oldPath", '--', $newPath)).output | Select-Object -First 1).Trim()
        if ($actualObject -ne $expectedObject) { throw "LEGACY_ASSET_INTEGRITY_FAILED: content drift: $newPath" }
      }
    }
    if ($mapping.kind -ne 'PYTHON_RUNTIME') {
      $expectedPom = Get-ExpectedAlphaPomText -Commit ([string]$Report.sourceCommit) -Source $mapping.source -Alpha $mapping.alpha
      $actualPom = Normalize-Text (Get-Content -Raw -Encoding UTF8 -LiteralPath (Join-Path $RepoRoot "$($mapping.alpha)/pom.xml"))
      if ($actualPom -cne $expectedPom) {
        throw "LEGACY_ASSET_INTEGRITY_FAILED: alpha POM contains changes outside the authorized identity/dependency rewrite: $($mapping.alpha)"
      }
    }
  }

  $expectedLineagePaths = @($Report.historicalLineage.entries | ForEach-Object { ([string]$_.path).Replace('document-generation-adapter/', 'document-generation-adapter_alpha/') })
  $actualLineagePaths = @((Invoke-Git @('ls-files', '-co', '--exclude-standard', '--', 'document-generation-adapter_alpha')).output | Where-Object { $_ })
  Assert-ExactPathSet -Expected $expectedLineagePaths -Actual $actualLineagePaths -Label 'document-generation-adapter_alpha'
  foreach ($entry in @($Report.historicalLineage.entries)) {
    $suffix = ([string]$entry.path).Substring('document-generation-adapter/'.Length)
    $newPath = "document-generation-adapter_alpha/$suffix"
    $absolute = Join-Path $RepoRoot $newPath
    if (-not (Test-Path -LiteralPath $absolute -PathType Leaf)) { throw "LEGACY_ASSET_INTEGRITY_FAILED: missing $newPath" }
    if ($suffix -ne 'pom.xml') {
      $actualObject = ((Invoke-Git @('hash-object', "--path=$($entry.path)", '--', $newPath)).output | Select-Object -First 1).Trim()
      if ($actualObject -ne [string]$entry.objectId) { throw "LEGACY_ASSET_INTEGRITY_FAILED: lineage drift: $newPath" }
    }
  }
  $expectedLineagePom = Get-ExpectedAlphaPomText -Commit ([string]$Report.historicalLineage.sourceCommit) -Source 'document-generation-adapter' -Alpha 'document-generation-adapter_alpha'
  $actualLineagePom = Normalize-Text (Get-Content -Raw -Encoding UTF8 -LiteralPath (Join-Path $RepoRoot 'document-generation-adapter_alpha/pom.xml'))
  if ($actualLineagePom -cne $expectedLineagePom) {
    throw 'LEGACY_ASSET_INTEGRITY_FAILED: LIN-01 POM contains changes outside the authorized identity/dependency rewrite.'
  }
}

function Assert-TargetSkeletons {
  $libraryNames = @('agent-adapter-api', 'agent-adapter-document', 'agent-adapter-employee', 'agent-adapter-transaction', 'agent-api', 'es-query-api')
  foreach ($name in $libraryNames) {
    $files = @(Get-ChildItem -LiteralPath (Join-Path $RepoRoot $name) -Recurse -File | Where-Object { $_.FullName -notmatch '[\\/](target|__pycache__)[\\/]' })
    if ($files.Count -ne 1 -or $files[0].Name -ne 'pom.xml') { throw "TARGET_NOT_GREENFIELD: $name must contain only pom.xml" }
    [xml]$pom = Get-Content -Raw -Encoding UTF8 -LiteralPath $files[0].FullName
    if ([string]$pom.project.artifactId -ne $name -or [string]$pom.project.name -ne $name -or [string]$pom.project.properties.'spring-boot.repackage.skip' -ne 'true') {
      throw "TARGET_NOT_GREENFIELD: invalid library identity or packaging: $name"
    }
    $dependencies = @($pom.project.dependencies.dependency)
    $cloud = @($dependencies | Where-Object { $_.groupId -eq 'org.springframework.cloud' })
    $expectedCloudArtifacts = @('spring-cloud-starter', 'spring-cloud-starter-config')
    if ($dependencies.Count -ne 2 -or $cloud.Count -ne 2 -or
        @(Compare-Object $expectedCloudArtifacts @($cloud.artifactId | Sort-Object)).Count -gt 0 -or
        @($cloud | Where-Object { $_.scope -ne 'provided' -or $_.optional -ne 'true' }).Count -gt 0) {
      throw "TARGET_NOT_GREENFIELD: inherited Cloud dependencies are not neutralized: $name"
    }
  }

  $serviceSpecs = [ordered]@{
    'agent-service' = @('pom.xml', 'src/main/java/com/dylan/baseline/agent/AgentServiceApplication.java', 'src/main/resources/application.yml', 'src/test/java/com/dylan/baseline/agent/AgentServiceApplicationTest.java')
    'es-query-service' = @('pom.xml', 'src/main/java/com/dylan/baseline/esquery/EsQueryServiceApplication.java', 'src/main/resources/application.yml', 'src/test/java/com/dylan/baseline/esquery/EsQueryServiceApplicationTest.java')
    'document-provider-adapter' = @('pom.xml', 'src/main/java/com/dylan/baseline/documentprovider/DocumentProviderAdapterApplication.java', 'src/main/resources/application.yml', 'src/test/java/com/dylan/baseline/documentprovider/DocumentProviderAdapterApplicationTest.java')
  }
  foreach ($name in $serviceSpecs.Keys) {
    $root = Join-Path $RepoRoot $name
    $actual = @(Get-ChildItem -LiteralPath $root -Recurse -File | Where-Object { $_.FullName -notmatch '[\\/](target|__pycache__)[\\/]' } | ForEach-Object { $_.FullName.Substring($root.Length + 1).Replace('\', '/') } | Sort-Object)
    if (@(Compare-Object @($serviceSpecs[$name] | Sort-Object) $actual).Count -gt 0) { throw "TARGET_NOT_GREENFIELD: unexpected file set: $name" }
    [xml]$servicePom = Get-Content -Raw -Encoding UTF8 -LiteralPath (Join-Path $root 'pom.xml')
    $serviceDependencies = @($servicePom.project.dependencies.dependency)
    $expectedServiceArtifacts = @('spring-boot-starter-actuator', 'spring-boot-starter-test', 'spring-boot-starter-web')
    if ($serviceDependencies.Count -ne 3 -or
        @(Compare-Object $expectedServiceArtifacts @($serviceDependencies.artifactId | Sort-Object)).Count -gt 0 -or
        @($serviceDependencies | Where-Object { $_.groupId -ne 'org.springframework.boot' }).Count -gt 0 -or
        @($serviceDependencies | Where-Object { $_.artifactId -eq 'spring-boot-starter-test' -and $_.scope -ne 'test' }).Count -ne 0 -or
        @($serviceDependencies | Where-Object { $_.artifactId -ne 'spring-boot-starter-test' -and -not [string]::IsNullOrWhiteSpace([string]$_.scope) }).Count -ne 0) {
      throw "TARGET_NOT_GREENFIELD: service dependency set is not minimal: $name"
    }
    $productionText = @($actual | Where-Object { $_ -like 'src/main/*' } | ForEach-Object { Get-Content -Raw -Encoding UTF8 -LiteralPath (Join-Path $root $_) }) -join "`n"
    if ($productionText -match '(?i)(flyway|datasource|elasticsearch|openfeign|vendorclient|repository|createalias|writeindex)') {
      throw "TARGET_NOT_GREENFIELD: forbidden capability found: $name"
    }
    $yaml = Get-Content -Raw -Encoding UTF8 -LiteralPath (Join-Path $root 'src/main/resources/application.yml')
    foreach ($required in @('port:\s*0', 'config:\s*\r?\n\s+enabled:\s*false', 'discovery:\s*\r?\n\s+enabled:\s*false', 'register-with-eureka:\s*false', 'fetch-registry:\s*false', 'include:\s*health', 'show-details:\s*never')) {
      if ($yaml -notmatch $required) { throw "TARGET_NOT_GREENFIELD: missing inert-runtime setting in ${name}: $required" }
    }
  }

  $runtimeRoot = Join-Path $RepoRoot 'agent-runtime'
  $runtimeFiles = @(Get-ChildItem -LiteralPath $runtimeRoot -Recurse -File | Where-Object { $_.FullName -notmatch '[\\/](target|__pycache__)[\\/]' } | ForEach-Object { $_.FullName.Substring($runtimeRoot.Length + 1).Replace('\', '/') } | Sort-Object)
  $expectedRuntime = @('pyproject.toml', 'src/agent_runtime/__main__.py', 'tests/test_idle_runtime.py') | Sort-Object
  if (@(Compare-Object $expectedRuntime $runtimeFiles).Count -gt 0) { throw 'TARGET_NOT_GREENFIELD: unexpected Python runtime file set.' }
  $pyproject = Get-Content -Raw -Encoding UTF8 -LiteralPath (Join-Path $runtimeRoot 'pyproject.toml')
  if ($pyproject -notmatch '(?m)^dependencies\s*=\s*\[\s*\]\s*$' -or $pyproject -notmatch '>=3\.12,<3\.13') { throw 'TARGET_NOT_GREENFIELD: Python runtime contract is invalid.' }
  if ((Test-Path -LiteralPath (Join-Path $runtimeRoot '.env')) -or (Test-Path -LiteralPath (Join-Path $runtimeRoot '.venv'))) { throw 'TARGET_NOT_GREENFIELD: target runtime contains environment residue.' }

  if (Test-Path -LiteralPath (Join-Path $RepoRoot 'document-generation-adapter')) { throw 'TARGET_NOT_GREENFIELD: document-generation-adapter target must not exist.' }
}

function Invoke-RecordedValidation {
  param(
    [Parameter(Mandatory)][string]$Id,
    [Parameter(Mandatory)][string]$Executable,
    [Parameter(Mandatory)][string[]]$Arguments
  )
  Push-Location $RepoRoot
  try {
    $output = @(& $Executable @Arguments 2>&1 | ForEach-Object { $_.ToString() })
    $code = $LASTEXITCODE
  } finally {
    Pop-Location
  }
  $joined = $output -join "`n"
  if ($code -ne 0) { throw "BASELINE_CHECK_FAILED: validation $Id failed ($code): $joined" }
  if ($Id -eq 'NO_ALPHA_DEPENDENCIES' -and $joined -match '(?m)^\[INFO\].*com\.dylan:.*_alpha') {
    throw 'ACTIVE_ALPHA_REFERENCE_FORBIDDEN: active dependency tree contains alpha.'
  }
  if ($Id -eq 'EMPTY_LIBRARY_RUNTIME_SCOPE' -and @($output | Where-Object { $_ -match '^\[INFO\]\s+none\s*$' }).Count -ne 6) {
    throw 'TARGET_NOT_GREENFIELD: one or more empty libraries have runtime dependencies.'
  }
  return [ordered]@{
    id = $Id
    status = 'PASSED'
    command = "$Executable $($Arguments -join ' ')"
    outputSha256 = Get-StringSha256 $joined
    completedAt = [DateTimeOffset]::UtcNow.ToString('o')
  }
}

function Invoke-EffectivePomValidation {
  $libraryNames = @('agent-adapter-api', 'agent-adapter-document', 'agent-adapter-employee', 'agent-adapter-transaction', 'agent-api', 'es-query-api')
  $maven = Join-Path $RepoRoot 'serviceCenter/mvnw.cmd'
  $tempRoot = Join-Path $RepoRoot ('.tmp/baseline-isolation-effective-' + [guid]::NewGuid().ToString('N'))
  New-Item -ItemType Directory -Path $tempRoot | Out-Null
  $captured = [Collections.Generic.List[string]]::new()
  try {
    foreach ($name in $libraryNames) {
      $outputPath = Join-Path $tempRoot "$name.xml"
      Push-Location $RepoRoot
      try {
        $commandOutput = @(& $maven '-f' "$name/pom.xml" '--batch-mode' '--no-transfer-progress' 'help:effective-pom' "-Doutput=$outputPath" 2>&1 | ForEach-Object { $_.ToString() })
        $code = $LASTEXITCODE
      } finally {
        Pop-Location
      }
      if ($code -ne 0 -or -not (Test-Path -LiteralPath $outputPath -PathType Leaf)) {
        $commandDetails = $commandOutput -join "`n"
        throw "BASELINE_CHECK_FAILED: effective POM validation failed for ${name}: $commandDetails"
      }
      [xml]$effectivePom = Get-Content -Raw -Encoding UTF8 -LiteralPath $outputPath
      $dependencies = @($effectivePom.project.dependencies.dependency)
      $cloud = @($dependencies | Where-Object { $_.groupId -eq 'org.springframework.cloud' })
      if ($cloud.Count -ne 2 -or @($cloud | Where-Object { $_.scope -ne 'provided' -or $_.optional -ne 'true' }).Count -gt 0 -or
          [string]$effectivePom.project.properties.'spring-boot.repackage.skip' -ne 'true') {
        throw "TARGET_NOT_GREENFIELD: effective POM is not inert: $name"
      }
      $captured.Add((Normalize-Text (Get-Content -Raw -Encoding UTF8 -LiteralPath $outputPath)))
    }
  } finally {
    foreach ($file in @(Get-ChildItem -LiteralPath $tempRoot -File -ErrorAction SilentlyContinue)) { Remove-Item -LiteralPath $file.FullName -Force }
    if (Test-Path -LiteralPath $tempRoot) { Remove-Item -LiteralPath $tempRoot -Force }
  }
  return [ordered]@{
    id = 'EMPTY_LIBRARY_EFFECTIVE_POMS'
    status = 'PASSED'
    command = "$maven -f <empty-library>/pom.xml --batch-mode --no-transfer-progress help:effective-pom"
    outputSha256 = Get-StringSha256 ($captured -join "`n")
    completedAt = [DateTimeOffset]::UtcNow.ToString('o')
  }
}

function Invoke-FinalValidations {
  param([Parameter(Mandatory)][object]$Report)
  Assert-TargetSkeletons
  Assert-ArchivedAssetIntegrity -Report $Report
  Assert-NoActiveAlphaReferences
  Assert-RuntimeEntryIsolation -Report $Report

  $moduleList = '../agent-api,../agent-adapter-api,../agent-adapter-document,../agent-adapter-employee,../agent-adapter-transaction,../agent-service,../es-query-api,../es-query-service,../document-provider-adapter'
  $libraryModuleList = '../agent-api,../agent-adapter-api,../agent-adapter-document,../agent-adapter-employee,../agent-adapter-transaction,../es-query-api'
  $maven = Join-Path $RepoRoot 'serviceCenter/mvnw.cmd'
  $previousNoBytecode = $env:PYTHONDONTWRITEBYTECODE
  $env:PYTHONDONTWRITEBYTECODE = '1'
  try {
    return @(
      Invoke-RecordedValidation -Id 'PYTHON_IDLE_RUNTIME_TESTS' -Executable 'python' -Arguments @('-m', 'unittest', 'discover', '-s', 'agent-runtime/tests')
      Invoke-RecordedValidation -Id 'TARGET_JAVA_TESTS' -Executable $maven -Arguments @('-f', 'serviceCenter/pom.xml', '--batch-mode', '--no-transfer-progress', '-pl', $moduleList, '-am', 'test')
      Invoke-EffectivePomValidation
      Invoke-RecordedValidation -Id 'EMPTY_LIBRARY_RUNTIME_SCOPE' -Executable $maven -Arguments @('-f', 'serviceCenter/pom.xml', '--batch-mode', '--no-transfer-progress', '-pl', $libraryModuleList, '-DincludeScope=runtime', 'dependency:list')
      Invoke-RecordedValidation -Id 'FULL_REACTOR_BUILD' -Executable $maven -Arguments @('-f', 'serviceCenter/pom.xml', '--batch-mode', '--no-transfer-progress', '-DskipTests', 'install')
      Invoke-RecordedValidation -Id 'NO_ALPHA_DEPENDENCIES' -Executable $maven -Arguments @('-f', 'serviceCenter/pom.xml', '--batch-mode', '--no-transfer-progress', "-Dincludes=com.dylan:*_alpha", 'dependency:tree')
    )
  } finally {
    if ($null -eq $previousNoBytecode) { Remove-Item Env:PYTHONDONTWRITEBYTECODE -ErrorAction SilentlyContinue } else { $env:PYTHONDONTWRITEBYTECODE = $previousNoBytecode }
  }
}

function Assert-PostApplyState {
  param([Parameter(Mandatory)][object]$Report)
  foreach ($mapping in $ProjectMappings) {
    if (-not (Test-Path -LiteralPath (Join-Path $RepoRoot $mapping.source) -PathType Container) -or -not (Test-Path -LiteralPath (Join-Path $RepoRoot $mapping.alpha) -PathType Container)) { throw "P0_GATE_NOT_MET: mapping incomplete: $($mapping.itemId)" }
  }
  if (-not (Test-Path -LiteralPath (Join-Path $RepoRoot 'document-generation-adapter_alpha') -PathType Container)) { throw 'P0_GATE_NOT_MET: LIN-01 is missing.' }
  Assert-ArchivedAssetIntegrity -Report $Report
  Assert-TargetSkeletons
  Assert-NoActiveAlphaReferences
  Assert-RuntimeEntryIsolation -Report $Report
}

function Invoke-RecoveryCheck {
  $report = Read-Report; Assert-RunIdentity $report
  $mismatches = [Collections.Generic.List[object]]::new()
  $fieldState = foreach ($mapping in $ProjectMappings) {
    $sourceExists = Test-Path -LiteralPath (Join-Path $RepoRoot $mapping.source)
    $alphaExists = Test-Path -LiteralPath (Join-Path $RepoRoot $mapping.alpha)
    $renamed = Test-CompletedTransition -Report $report -StageName 'RENAME_PROJECT' -StageItem $mapping.itemId
    $created = Test-CompletedTransition -Report $report -StageName 'CREATE_TARGET_PROJECT' -StageItem $mapping.itemId
    $expectedSource = -not $renamed -or $created
    $expectedAlpha = $renamed
    if ($sourceExists -ne $expectedSource -or $alphaExists -ne $expectedAlpha) {
      $mismatches.Add([ordered]@{ itemId = $mapping.itemId; expectedSourceExists = $expectedSource; actualSourceExists = $sourceExists; expectedAlphaExists = $expectedAlpha; actualAlphaExists = $alphaExists })
    }
    [ordered]@{ itemId = $mapping.itemId; sourceExists = $sourceExists; alphaExists = $alphaExists; expectedSourceExists = $expectedSource; expectedAlphaExists = $expectedAlpha }
  }
  $lineageExpected = Test-CompletedTransition -Report $report -StageName 'ARCHIVE_GIT_LINEAGE' -StageItem 'LIN-01'
  $lineageExists = Test-Path -LiteralPath (Join-Path $RepoRoot 'document-generation-adapter_alpha')
  if ($lineageExists -ne $lineageExpected) {
    $mismatches.Add([ordered]@{ itemId = 'LIN-01'; expectedAlphaExists = $lineageExpected; actualAlphaExists = $lineageExists })
  }
  $entryExpected = Test-CompletedTransition -Report $report -StageName 'ISOLATE_RUNTIME_ENTRY' -StageItem 'ENTRY-ISOLATION'
  if ($entryExpected) {
    foreach ($historyPath in @('docs/design/agent/evidence/baseline-isolation/p0/history/scripts/verify-d01-contract.ps1', 'docs/design/agent/evidence/baseline-isolation/p0/history/workflows/agent-contract.yml')) {
      if (-not (Test-Path -LiteralPath (Join-Path $RepoRoot $historyPath) -PathType Leaf)) {
        $mismatches.Add([ordered]@{ itemId = 'ENTRY-ISOLATION'; missingPath = $historyPath })
      }
    }
  }
  $allArchivesExpected = $lineageExpected -and @($ProjectMappings | Where-Object { -not (Test-CompletedTransition -Report $report -StageName 'RENAME_PROJECT' -StageItem $_.itemId) }).Count -eq 0
  if ($allArchivesExpected) {
    try { Assert-ArchivedAssetIntegrity -Report $report } catch { $mismatches.Add([ordered]@{ itemId = 'ARCHIVE-INTEGRITY'; detail = $_.Exception.Message }) }
  }
  $allTargetsExpected = @($ProjectMappings | Where-Object { -not (Test-CompletedTransition -Report $report -StageName 'CREATE_TARGET_PROJECT' -StageItem $_.itemId) }).Count -eq 0
  if ($allTargetsExpected) {
    try { Assert-TargetSkeletons } catch { $mismatches.Add([ordered]@{ itemId = 'TARGET-INTEGRITY'; detail = $_.Exception.Message }) }
  }
  if ($entryExpected) {
    try { Assert-RuntimeEntryIsolation -Report $report } catch { $mismatches.Add([ordered]@{ itemId = 'ENTRY-INTEGRITY'; detail = $_.Exception.Message }) }
  }
  $started = @($report.transitions | Where-Object { $_.status -eq 'STARTED' })
  [ordered]@{ schemaVersion = '1.0'; runId = $RunId; status = if ($started.Count -gt 0 -or $mismatches.Count -gt 0) { 'RECOVERY_REQUIRED' } else { 'RECOVERY_CHECKED' }; startedItems = $started; fieldState = $fieldState; mismatches = @($mismatches); suggestedReverseOrder = @($report.transitions | Where-Object { $_.status -eq 'COMPLETED' } | Sort-Object completedAt -Descending); checkedAt = [DateTimeOffset]::UtcNow.ToString('o'); projectFilesModified = $false } | ConvertTo-Json -Depth 20
}

function Invoke-PostApply {
  $report = Read-Report; Assert-RunIdentity $report
  if (@($report.transitions | Where-Object { $_.status -eq 'STARTED' }).Count -gt 0) { throw 'RECOVERY_REQUIRED: unfinished STARTED transition exists.' }
  if ([string]::IsNullOrWhiteSpace($AuthorizationRef) -and [string]$report.authorization.reference -match '(?i)NO-P0') {
    throw 'P0_GATE_NOT_MET: an explicit P0 implementation authorization reference is required.'
  }
  if (-not [string]::IsNullOrWhiteSpace($AuthorizationRef) -and [string]$report.authorization.reference -ne $AuthorizationRef) {
    if ($null -eq $report.authorizationHistory) { $report | Add-Member -NotePropertyName authorizationHistory -NotePropertyValue @() }
    $report.authorizationHistory = @($report.authorizationHistory) + [ordered]@{
      reference = [string]$report.authorization.reference
      supersededAt = [DateTimeOffset]::UtcNow.ToString('o')
      reason = 'EXPLICIT_P0_IMPLEMENTATION_AUTHORIZATION_RECEIVED'
    }
    $report.authorization.reference = $AuthorizationRef
    $report.authorization.implementerPid = $PID
  }
  Update-ReportProgress -Report $report
  $isRevalidation = $report.state -eq 'P0_VERIFIED'
  if ($report.state -notin @('TARGET_REACTOR_ISOLATED', 'P0_VERIFIED')) { throw "P0_GATE_NOT_MET: report progress is incomplete: $($report.state)" }
  if (-not (Test-CompletedTransition -Report $report -StageName 'FINAL_VALIDATION' -StageItem 'FINAL-GATE')) { throw 'P0_GATE_NOT_MET: FINAL_VALIDATION is incomplete.' }
  $validationResults = @($report.validationResults)
  $minimumRecordedResults = if ($isRevalidation) { 4 } else { 6 }
  if ($validationResults.Count -lt $minimumRecordedResults -or @($validationResults | Where-Object { $_.status -ne 'PASSED' }).Count -gt 0) { throw 'P0_GATE_NOT_MET: recorded validation evidence is incomplete.' }
  $postApplyValidationResults = @(Invoke-FinalValidations -Report $report)
  if ($postApplyValidationResults.Count -ne 6 -or @($postApplyValidationResults | Where-Object { $_.status -ne 'PASSED' }).Count -gt 0) {
    throw 'P0_GATE_NOT_MET: PostApply validation evidence is incomplete.'
  }
  $report.validationResults = $postApplyValidationResults
  $report | Add-Member -NotePropertyName postApplyValidationResults -NotePropertyValue $postApplyValidationResults -Force
  $report.checks = @($report.checks | Where-Object { $_.id -ne 'P0_POST_APPLY_REVALIDATION' }) + [ordered]@{ id = 'P0_POST_APPLY_REVALIDATION'; status = 'PASSED'; resultCount = $postApplyValidationResults.Count }
  Update-ReportFileEvidence -Report $report
  if ($null -eq $report.preflightDesignHashes) { $report | Add-Member -NotePropertyName preflightDesignHashes -NotePropertyValue $report.designHashes }
  $report | Add-Member -NotePropertyName currentDocumentHashes -NotePropertyValue (Get-CurrentDocumentHashes) -Force
  $externalPath = [string]$report.externalConsumerResolutionRef.path
  if ((Get-Sha256 (Join-Path $RepoRoot $externalPath)) -ne [string]$report.externalConsumerResolutionRef.sha256) {
    throw 'EXTERNAL_CONSUMER_UNRESOLVED: evidence file changed after Preflight.'
  }
  [void](Assert-ExternalConsumerEvidence -Path (Join-Path $RepoRoot $externalPath) -CurrentHead ((Invoke-Git @('rev-parse', 'HEAD')).output[0].Trim()))
  $report.referenceClassifications = Get-ReferenceClassifications
  Sync-VerifierProvenance -Report $report -ModeName 'PostApply'
  $report.state = 'P0_VERIFIED'; $report.updatedAt = [DateTimeOffset]::UtcNow.ToString('o'); $report.unresolvedItems = @(); $report.failureCodes = @()
  $report.transitions = @($report.transitions) + [ordered]@{
    from = if ($isRevalidation) { 'P0_VERIFIED' } else { 'TARGET_REACTOR_ISOLATED' }
    to = 'P0_VERIFIED'
    mode = if ($isRevalidation) { 'PostApplyRevalidation' } else { 'PostApply' }
    at = $report.updatedAt
  }
  Write-JsonAtomic -Value $report -Path (Get-OutputAbsolutePath); $report | ConvertTo-Json -Depth 20
}

try {
  switch ($Mode) {
    'Preflight' { Invoke-Preflight }
    'BeginStage' { Invoke-BeginStage }
    'Checkpoint' { Invoke-Checkpoint }
    'RecoveryCheck' { Invoke-RecoveryCheck }
    'PostApply' { Invoke-PostApply }
  }
  exit 0
} catch {
  $message = $_.Exception.Message
  [Console]::Error.WriteLine($message)
  if ($message -match '^(PARAMETER_INVALID|REPORT_SCHEMA_INVALID)') { exit 30 }
  if ($message -match '^(RECOVERY_REQUIRED|RECOVERY_CONFIRMATION_REQUIRED|STAGE_OWNERSHIP_UNCERTAIN)') { exit 20 }
  if ($message -match '^TOOL_ERROR') { exit 40 }
  exit 10
}
