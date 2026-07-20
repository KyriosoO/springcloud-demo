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
$ExpectedDesignHashes = [ordered]@{
  overview = [ordered]@{ path = 'docs/design/agent/L2/00_单体Agent目标架构L2实施详细设计总览_v1.0.md'; sha256 = 'B3EFEECBF534B234F4A5D2CB3EBADEBE1594636F157ECF25D4353E20CD677BE0' }
  isolation = [ordered]@{ path = 'docs/design/agent/L2/02_目标基线隔离与迁移门禁_L2实施详细设计_v1.0.md'; sha256 = 'F9CCDF6987884A654AC46DC336B5C7F209107093A1842D440A3F85D85551141C' }
  exitDesign = [ordered]@{ path = 'docs/design/agent/L2/02A_外部消费者活动基线退出与DB-02-001关闭_L2实施详细设计_v1.0.md'; sha256 = '108856C320E35234B445ECA1044959FB276464F5BEEA3882A64E30621C1FA9CD' }
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
    [Parameter(Mandatory)][string]$CurrentHead
  )
  try { $evidence = Get-Content -Raw -Encoding UTF8 -LiteralPath $Path | ConvertFrom-Json } catch { throw 'EXTERNAL_CONSUMER_UNRESOLVED: evidence is not valid JSON.' }
  if ($evidence.schemaVersion -ne '1.0' -or $evidence.status -ne 'CONSUMER_EXIT_VERIFIED' -or
      $evidence.closureSemantics -ne 'CLOSED_FOR_P0_BY_INACTIVITY' -or
      $evidence.closureEstablishedBy -ne 'CONSUMER_EXIT_VERIFIED_REPORT_PUBLICATION' -or
      $evidence.p0PreflightRole -ne 'REVALIDATE_AND_GATE_ONLY' -or @($evidence.unresolvedItems).Count -ne 0) {
    throw 'EXTERNAL_CONSUMER_UNRESOLVED: closure fields are incomplete.'
  }
  foreach ($key in @('overview', 'isolation', 'exitDesign')) {
    if ($evidence.designHashes.$key -ne $ExpectedDesignHashes[$key].sha256) {
      throw "EXTERNAL_CONSUMER_UNRESOLVED: design hash mismatch: $key"
    }
  }
  foreach ($entry in @($evidence.resultFileManifest)) {
    $absolute = Join-Path $RepoRoot $entry.path
    if ((Get-Sha256 $absolute) -ne $entry.sha256) {
      throw "EXTERNAL_CONSUMER_UNRESOLVED: result manifest drift: $($entry.path)"
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
    if ($relative -match '^docs/design/agent/evidence/baseline-isolation/p0/history/') {
      $classifications.must_archive_history += $relative
    } elseif ($relative -match '^docs/' -or $relative -in @('scripts/verify-agent-baseline-isolation.ps1', 'scripts/verify-agent-external-consumer-exit.ps1')) {
      $classifications.evidence_only += $relative
    } elseif ($content -match '(?i)(agent|es|document-(?:provider|generation))[-\w]*_alpha') {
      $classifications.forbidden_active_alpha_reference += $relative
    } else {
      $classifications.must_remain_target += $relative
    }
  }
  foreach ($key in $classifications.Keys) { $classifications[$key] = @($classifications[$key] | Sort-Object -Unique) }
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
  $externalEvidence = Assert-ExternalConsumerEvidence -Path $externalPath -CurrentHead $head
  $references = Get-ReferenceClassifications
  $report = New-PreflightReport -Head $head -DesignHashes $designHashes -ExternalEvidence $externalEvidence -Lineage $lineage -ReferenceClassifications $references
  Write-JsonAtomic -Value $report -Path (Get-OutputAbsolutePath)
  $report | ConvertTo-Json -Depth 20
}

function Invoke-BeginStage {
  foreach ($value in @($RunId, $Stage, $ItemId, $ExpectedEffect)) { if ([string]::IsNullOrWhiteSpace($value)) { throw 'PARAMETER_INVALID: BeginStage requires RunId, Stage, ItemId, and ExpectedEffect.' } }
  $report = Read-Report; Assert-RunIdentity $report
  if ($report.state -notin @('PREFLIGHT_PASSED', 'LEGACY_ASSETS_ARCHIVED', 'TARGET_SKELETON_CREATED', 'TARGET_REACTOR_ISOLATED')) { throw "RECOVERY_REQUIRED: cannot begin a stage from state=$($report.state)" }
  if (@($report.transitions | Where-Object { $_.stage -eq $Stage -and $_.itemId -eq $ItemId }).Count -gt 0) { throw 'STAGE_OWNERSHIP_UNCERTAIN: duplicate stage item is forbidden.' }
  $transition = [ordered]@{ stage = $Stage; itemId = $ItemId; expectedEffect = $ExpectedEffect; status = 'STARTED'; at = [DateTimeOffset]::UtcNow.ToString('o') }
  $report.transitions = @($report.transitions) + $transition; $report.currentStage = $Stage; $report.pendingStage = $ItemId; $report.updatedAt = $transition.at
  Write-JsonAtomic -Value $report -Path (Get-OutputAbsolutePath); $transition | ConvertTo-Json -Depth 6
}

function Assert-CheckpointPostcondition {
  param([string]$StageName, [string]$StageItem)
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
    'ISOLATE_RUNTIME_ENTRY' { Assert-RuntimeEntryIsolation }
    'FINAL_VALIDATION' { Assert-PostApplyState }
  }
}

function Invoke-Checkpoint {
  foreach ($value in @($RunId, $Stage, $ItemId)) { if ([string]::IsNullOrWhiteSpace($value)) { throw 'PARAMETER_INVALID: Checkpoint requires RunId, Stage, and ItemId.' } }
  $report = Read-Report; Assert-RunIdentity $report
  $matches = @($report.transitions | Where-Object { $_.stage -eq $Stage -and $_.itemId -eq $ItemId })
  if ($matches.Count -ne 1 -or $matches[0].status -ne 'STARTED') { throw 'RECOVERY_REQUIRED: exactly one matching STARTED transition is required.' }
  Assert-CheckpointPostcondition -StageName $Stage -StageItem $ItemId
  $matches[0].status = 'COMPLETED'; $matches[0] | Add-Member -NotePropertyName completedAt -NotePropertyValue ([DateTimeOffset]::UtcNow.ToString('o')) -Force
  $report.currentStage = $null; $report.pendingStage = $null; $report.updatedAt = $matches[0].completedAt
  Write-JsonAtomic -Value $report -Path (Get-OutputAbsolutePath); $matches[0] | ConvertTo-Json -Depth 6
}

function Assert-NoActiveAlphaReferences {
  [xml]$pom = Get-Content -Raw -Encoding UTF8 -LiteralPath (Join-Path $RepoRoot 'serviceCenter/pom.xml')
  if (($pom.OuterXml) -match '(?i)_alpha') { throw 'ACTIVE_ALPHA_REFERENCE_FORBIDDEN: serviceCenter/pom.xml contains alpha.' }
  $references = Get-ReferenceClassifications
  if ($references.forbidden_active_alpha_reference.Count -gt 0) { throw 'ACTIVE_ALPHA_REFERENCE_FORBIDDEN: active alpha reference found.' }
}

function Assert-RuntimeEntryIsolation {
  $start = Get-Content -Raw -Encoding UTF8 -LiteralPath (Join-Path $RepoRoot 'scripts/start-all-services.ps1')
  foreach ($pattern in @("Name\s*=\s*'agent-service'", "Name\s*=\s*'es-query-service'", "Name\s*=\s*'agent-runtime'", "'DOCUMENT-GENERATION-ADAPTER'")) {
    if ($start -match $pattern) { throw "DEFAULT_START_NOT_ISOLATED: $pattern" }
  }
  $historyScript = Join-Path $RepoRoot 'docs/design/agent/evidence/baseline-isolation/p0/history/scripts/verify-d01-contract.ps1'
  $historyWorkflow = Join-Path $RepoRoot 'docs/design/agent/evidence/baseline-isolation/p0/history/workflows/agent-contract.yml'
  if (-not (Test-Path -LiteralPath $historyScript -PathType Leaf) -or -not (Test-Path -LiteralPath $historyWorkflow -PathType Leaf)) { throw 'CI_AUTHORITY_CONFLICT: fixed history entry is missing.' }
}

function Assert-PostApplyState {
  foreach ($mapping in $ProjectMappings) {
    if (-not (Test-Path -LiteralPath (Join-Path $RepoRoot $mapping.source) -PathType Container) -or -not (Test-Path -LiteralPath (Join-Path $RepoRoot $mapping.alpha) -PathType Container)) { throw "P0_GATE_NOT_MET: mapping incomplete: $($mapping.itemId)" }
  }
  if (-not (Test-Path -LiteralPath (Join-Path $RepoRoot 'document-generation-adapter_alpha') -PathType Container)) { throw 'P0_GATE_NOT_MET: LIN-01 is missing.' }
  Assert-NoActiveAlphaReferences; Assert-RuntimeEntryIsolation
}

function Invoke-RecoveryCheck {
  $report = Read-Report; Assert-RunIdentity $report
  $fieldState = foreach ($mapping in $ProjectMappings) {
    [ordered]@{ itemId = $mapping.itemId; sourceExists = Test-Path -LiteralPath (Join-Path $RepoRoot $mapping.source); alphaExists = Test-Path -LiteralPath (Join-Path $RepoRoot $mapping.alpha) }
  }
  $started = @($report.transitions | Where-Object { $_.status -eq 'STARTED' })
  [ordered]@{ schemaVersion = '1.0'; runId = $RunId; status = if ($started.Count -gt 0) { 'RECOVERY_REQUIRED' } else { 'RECOVERY_CHECKED' }; startedItems = $started; fieldState = $fieldState; suggestedReverseOrder = @($report.transitions | Where-Object { $_.status -eq 'COMPLETED' } | Sort-Object completedAt -Descending); checkedAt = [DateTimeOffset]::UtcNow.ToString('o'); projectFilesModified = $false } | ConvertTo-Json -Depth 20
}

function Invoke-PostApply {
  $report = Read-Report; Assert-RunIdentity $report
  if (@($report.transitions | Where-Object { $_.status -eq 'STARTED' }).Count -gt 0) { throw 'RECOVERY_REQUIRED: unfinished STARTED transition exists.' }
  Assert-PostApplyState
  $externalPath = [string]$report.externalConsumerResolutionRef.path
  [void](Assert-ExternalConsumerEvidence -Path (Join-Path $RepoRoot $externalPath) -CurrentHead ((Invoke-Git @('rev-parse', 'HEAD')).output[0].Trim()))
  $report.state = 'P0_VERIFIED'; $report.updatedAt = [DateTimeOffset]::UtcNow.ToString('o'); $report.unresolvedItems = @(); $report.failureCodes = @()
  $report.transitions = @($report.transitions) + [ordered]@{ from = 'TARGET_REACTOR_ISOLATED'; to = 'P0_VERIFIED'; mode = 'PostApply'; at = $report.updatedAt }
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
