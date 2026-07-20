param(
  [Parameter(Mandatory)]
  [ValidateSet('Preflight', 'PostApply', 'RecoveryCheck')]
  [string]$Mode,

  [Parameter(Mandatory)]
  [string]$OutputPath,

  [string]$ExpectedHead,
  [string]$AuthorizationRef,
  [string]$ImpactAcceptanceRef,
  [string]$BootstrapScriptHash,
  [string]$ResolutionId,
  [string]$P0ReportPath
)

$ErrorActionPreference = 'Stop'
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$ScriptPath = $MyInvocation.MyCommand.Path
$DesignPath = Join-Path $RepoRoot 'docs/design/agent/L2/02A_外部消费者活动基线退出与DB-02-001关闭_L2实施详细设计_v1.0.md'
$OverviewPath = Join-Path $RepoRoot 'docs/design/agent/L2/00_单体Agent目标架构L2实施详细设计总览_v1.0.md'
$IsolationPath = Join-Path $RepoRoot 'docs/design/agent/L2/02_目标基线隔离与迁移门禁_L2实施详细设计_v1.0.md'
$ServiceCenterPom = Join-Path $RepoRoot 'serviceCenter/pom.xml'
$StartScript = Join-Path $RepoRoot 'scripts/start-all-services.ps1'
$GatewayRouter = Join-Path $RepoRoot 'gateway-service/src/main/java/com/dylan/springgateway/config/GatewayRouter.java'
$GatewayTest = Join-Path $RepoRoot 'gateway-service/src/test/java/com/dylan/springgateway/config/GatewayEmployeeRouteExitTest.java'
$HomePage = Join-Path $RepoRoot 'auth-service/src/main/resources/static/home.html'
$EmployeeRoot = Join-Path $RepoRoot 'employee-service'
$ExpectedOutputRelativePath = 'docs/design/agent/evidence/baseline-isolation/p0/external-consumer-resolution.json'
$ExpectedP0ReportRelativePath = 'docs/design/agent/evidence/baseline-isolation/p0/baseline-isolation-report.json'
$Maven = if ($IsWindows) {
  Join-Path $RepoRoot 'serviceCenter/mvnw.cmd'
} else {
  Join-Path $RepoRoot 'serviceCenter/mvnw'
}
$ExpectedDesignHashes = [ordered]@{
  overview = '21ED707E698FD4908B45C7B9CFCE90392E169012F6F0B4C05181D7FD99166499'
  isolation = 'F58ECC9FCDB622BAE0E366E593A503B22FF3589248880E0EB61D922CB454FF90'
  exitDesign = 'DE4C9AE0B26096E960A8FFA5058894AE5800B6FBADE1FF852C040835538E9206'
}

if ($PSVersionTable.PSEdition -ne 'Core' -or $PSVersionTable.PSVersion.Major -lt 7) {
  throw 'PowerShell 7+ (pwsh) is required.'
}

function Invoke-Git {
  param([Parameter(Mandatory)][string[]]$Arguments)

  Push-Location $RepoRoot
  try {
    $result = & git -c core.quotepath=false @Arguments 2>&1
    if ($LASTEXITCODE -ne 0) {
      throw "git command failed ($LASTEXITCODE): git $($Arguments -join ' ')`n$($result -join "`n")"
    }
    return @($result)
  } finally {
    Pop-Location
  }
}

function Assert-GitAncestor {
  param(
    [Parameter(Mandatory)][string]$Ancestor,
    [Parameter(Mandatory)][string]$Descendant
  )

  if ($Ancestor -notmatch '^[0-9a-fA-F]{40}$' -or $Descendant -notmatch '^[0-9a-fA-F]{40}$') {
    throw "DESIGN_BASELINE_CHANGED: commit identity must be a full 40-character SHA-1"
  }

  Push-Location $RepoRoot
  try {
    $result = @(& git -c core.quotepath=false merge-base --is-ancestor $Ancestor $Descendant 2>&1)
    $exitCode = $LASTEXITCODE
  } finally {
    Pop-Location
  }
  if ($exitCode -eq 1) {
    throw "DESIGN_BASELINE_CHANGED: baselineCommit=$Ancestor is not an ancestor of currentHead=$Descendant"
  }
  if ($exitCode -ne 0) {
    throw "DESIGN_BASELINE_CHANGED: unable to verify baseline ancestry ($exitCode): $($result -join "`n")"
  }
}

function Assert-EmployeeBaselineIntegrity {
  param(
    [Parameter(Mandatory)][string]$BaselineCommit,
    [Parameter(Mandatory)][string]$CurrentCommit
  )

  $committedChanges = @(Invoke-Git @('diff', '--name-only', "$BaselineCommit..$CurrentCommit", '--', 'employee-service'))
  if ($committedChanges.Count -gt 0) {
    throw "INACTIVE_ASSET_CHANGED: employee-service changed after baselineCommit=$BaselineCommit"
  }
}

function Get-Sha256 {
  param([Parameter(Mandatory)][string]$Path)

  if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
    throw "required file not found: $Path"
  }
  return (Get-FileHash -Algorithm SHA256 -LiteralPath $Path).Hash.ToUpperInvariant()
}

function Get-TextSha256 {
  param([Parameter(Mandatory)][AllowEmptyString()][string]$Value)

  $bytes = [Text.Encoding]::UTF8.GetBytes($Value)
  return [Convert]::ToHexString([Security.Cryptography.SHA256]::HashData($bytes))
}

function Invoke-CheckedCommand {
  param(
    [Parameter(Mandatory)][string]$DisplayCommand,
    [Parameter(Mandatory)][string]$FilePath,
    [Parameter(Mandatory)][string[]]$Arguments,
    [Parameter(Mandatory)][string]$ResultSummary,
    [string]$ForbiddenOutputPattern
  )

  $startedAt = [DateTimeOffset]::UtcNow.ToString('o')
  Push-Location $RepoRoot
  try {
    $output = @(& $FilePath @Arguments 2>&1 | ForEach-Object { $_.ToString() })
    $exitCode = $LASTEXITCODE
  } finally {
    Pop-Location
  }
  if ($exitCode -ne 0) {
    $tail = @($output | Select-Object -Last 80) -join "`n"
    throw "VALIDATION_FAILED: command failed ($exitCode): $DisplayCommand`n$tail"
  }
  if (-not ($output -match 'BUILD SUCCESS')) {
    throw "VALIDATION_FAILED: BUILD SUCCESS marker missing: $DisplayCommand"
  }
  if ($ForbiddenOutputPattern -and ($output -match $ForbiddenOutputPattern)) {
    throw "VALIDATION_FAILED: forbidden dependency was emitted: $DisplayCommand"
  }
  return [ordered]@{
    command = $DisplayCommand
    status = 'PASSED'
    result = $ResultSummary
    outputSha256 = Get-TextSha256 ($output -join "`n")
    startedAt = $startedAt
    completedAt = [DateTimeOffset]::UtcNow.ToString('o')
  }
}

function Get-RelativePath {
  param([Parameter(Mandatory)][string]$Path)

  return [IO.Path]::GetRelativePath($RepoRoot, (Resolve-Path -LiteralPath $Path).Path).Replace('\', '/')
}

function Get-OutputAbsolutePath {
  $candidate = if ([IO.Path]::IsPathRooted($OutputPath)) {
    [IO.Path]::GetFullPath($OutputPath)
  } else {
    [IO.Path]::GetFullPath((Join-Path $RepoRoot $OutputPath))
  }
  $expected = [IO.Path]::GetFullPath((Join-Path $RepoRoot $ExpectedOutputRelativePath))
  if (-not [string]::Equals($candidate, $expected, [StringComparison]::OrdinalIgnoreCase)) {
    throw "OUTPUT_PATH_NOT_ALLOWED: expected=$ExpectedOutputRelativePath actual=$OutputPath"
  }
  return $candidate
}

function Get-P0ReportAbsolutePath {
  if ([string]::IsNullOrWhiteSpace($P0ReportPath)) {
    throw 'RecoveryCheck requires P0ReportPath.'
  }
  $candidate = if ([IO.Path]::IsPathRooted($P0ReportPath)) {
    [IO.Path]::GetFullPath($P0ReportPath)
  } else {
    [IO.Path]::GetFullPath((Join-Path $RepoRoot $P0ReportPath))
  }
  $expected = [IO.Path]::GetFullPath((Join-Path $RepoRoot $ExpectedP0ReportRelativePath))
  if (-not [string]::Equals($candidate, $expected, [StringComparison]::OrdinalIgnoreCase)) {
    throw "P0_REPORT_PATH_NOT_ALLOWED: expected=$ExpectedP0ReportRelativePath actual=$P0ReportPath"
  }
  return $candidate
}

function Assert-DesignBaseline {
  $actual = [ordered]@{
    overview = Get-Sha256 $OverviewPath
    isolation = Get-Sha256 $IsolationPath
    exitDesign = Get-Sha256 $DesignPath
  }
  foreach ($key in $ExpectedDesignHashes.Keys) {
    if ($actual[$key] -ne $ExpectedDesignHashes[$key]) {
      throw "DESIGN_BASELINE_CHANGED: $key expected=$($ExpectedDesignHashes[$key]) actual=$($actual[$key])"
    }
  }
  return $actual
}

function Get-StatePath {
  $fullOutputPath = Get-OutputAbsolutePath
  $bytes = [Text.Encoding]::UTF8.GetBytes($fullOutputPath.ToLowerInvariant())
  $hash = [Convert]::ToHexString([Security.Cryptography.SHA256]::HashData($bytes)).ToLowerInvariant()
  return Join-Path ([IO.Path]::GetTempPath()) "codex-agent-external-consumer-exit-$hash.json"
}

function Write-JsonAtomic {
  param(
    [Parameter(Mandatory)][object]$Value,
    [Parameter(Mandatory)][string]$Path
  )

  $directory = Split-Path -Parent $Path
  if (-not (Test-Path -LiteralPath $directory)) {
    New-Item -ItemType Directory -Path $directory -Force | Out-Null
  }
  $tempPath = Join-Path $directory ('.' + [IO.Path]::GetFileName($Path) + '.' + [guid]::NewGuid().ToString('N') + '.tmp')
  try {
    $json = $Value | ConvertTo-Json -Depth 12
    [IO.File]::WriteAllText($tempPath, $json + "`n", [Text.UTF8Encoding]::new($false))
    [IO.File]::Move($tempPath, $Path, $true)
  } finally {
    if (Test-Path -LiteralPath $tempPath) {
      Remove-Item -LiteralPath $tempPath -Force
    }
  }
}

function Assert-PowerShellSyntax {
  param([Parameter(Mandatory)][string]$Path)

  $tokens = $null
  $errors = $null
  [Management.Automation.Language.Parser]::ParseFile($Path, [ref]$tokens, [ref]$errors) | Out-Null
  if ($errors.Count -gt 0) {
    throw "PowerShell syntax errors in $Path`n$($errors.Message -join "`n")"
  }
}

function Get-RootModules {
  [xml]$pom = Get-Content -Raw -Encoding UTF8 -LiteralPath $ServiceCenterPom
  $namespace = [Xml.XmlNamespaceManager]::new($pom.NameTable)
  $namespace.AddNamespace('m', 'http://maven.apache.org/POM/4.0.0')
  return @($pom.SelectNodes('/m:project/m:modules/m:module', $namespace) | ForEach-Object { $_.InnerText.Trim() })
}

function Assert-EmployeeStopped {
  $listeners = @(Get-NetTCPConnection -State Listen -LocalPort 9210 -ErrorAction SilentlyContinue)
  if ($listeners.Count -gt 0) {
    $pids = @($listeners | Select-Object -ExpandProperty OwningProcess -Unique)
    throw "EXIT_PREFLIGHT_FAILED: port 9210 is listening; pid=$($pids -join ',')"
  }

  $employeeProcesses = @(Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object {
      $_.CommandLine -and $_.CommandLine -match '(?i)employee-service'
    })
  if ($employeeProcesses.Count -gt 0) {
    throw "EXIT_PREFLIGHT_FAILED: employee-service process is running; pid=$($employeeProcesses.ProcessId -join ',')"
  }
}

function Get-ChangedPaths {
  $paths = New-Object 'System.Collections.Generic.HashSet[string]' ([StringComparer]::OrdinalIgnoreCase)
  foreach ($line in (Invoke-Git @('status', '--short', '--untracked-files=all'))) {
    if (-not $line) { continue }
    $path = $line.Substring(3).Trim()
    if ($path.Contains(' -> ')) { $path = $path.Split(' -> ')[-1] }
    [void]$paths.Add($path.Replace('\', '/'))
  }
  return @($paths | Sort-Object)
}

function Assert-PreflightWorkspace {
  $scriptRelative = Get-RelativePath $ScriptPath
  $changed = @(Get-ChangedPaths)
  if ($changed.Count -ne 1 -or $changed[0] -ne $scriptRelative) {
    throw "EXIT_PREFLIGHT_FAILED: worktree may contain only $scriptRelative; actual=$($changed -join ',')"
  }
}

function Assert-NoEmployeeChanges {
  $diff = @(Invoke-Git @('diff', '--name-only', 'HEAD', '--', 'employee-service'))
  $untracked = @(Invoke-Git @('ls-files', '--others', '--exclude-standard', '--', 'employee-service'))
  if ($diff.Count -gt 0 -or $untracked.Count -gt 0) {
    throw "INACTIVE_ASSET_CHANGED: employee-service contains changes"
  }
}

function Get-EmployeeSourceIntegrity {
  param([Parameter(Mandatory)][string]$BaselineCommit)

  Assert-NoEmployeeChanges
  $head = (@(Invoke-Git @('rev-parse', 'HEAD'))[0]).Trim()
  Assert-EmployeeBaselineIntegrity -BaselineCommit $BaselineCommit -CurrentCommit $head
  $trackedFiles = @(Invoke-Git @('ls-files', '--', 'employee-service') | Sort-Object)
  if ($trackedFiles.Count -eq 0) {
    throw 'INACTIVE_ASSET_CHANGED: employee-service has no tracked files'
  }
  $manifestLines = foreach ($relative in $trackedFiles) {
    $absolute = Join-Path $RepoRoot $relative
    if (-not (Test-Path -LiteralPath $absolute -PathType Leaf)) {
      throw "INACTIVE_ASSET_CHANGED: tracked employee-service file is missing: $relative"
    }
    "$relative`0$(Get-Sha256 $absolute)"
  }
  return [ordered]@{
    status = 'UNCHANGED'
    trackedFileCount = $trackedFiles.Count
    aggregateSha256 = Get-TextSha256 ($manifestLines -join "`n")
    comparison = 'working tree is clean and committed employee-service tree is unchanged since baselineCommit'
  }
}

function Get-EmployeeReferenceClassifications {
  $employeePom = Join-Path $EmployeeRoot 'pom.xml'
  if (-not (Test-Path -LiteralPath $employeePom -PathType Leaf) -or
      (Get-Content -Raw -Encoding UTF8 -LiteralPath $employeePom) -notmatch '<artifactId>es-query-api</artifactId>') {
    throw 'REFERENCE_CLASSIFICATION_FAILED: inactive employee consumer evidence is missing'
  }

  $legacyCallerMatches = New-Object 'System.Collections.Generic.HashSet[string]' ([StringComparer]::OrdinalIgnoreCase)
  foreach ($root in @('agent-adapter-employee', 'agent-service')) {
    if (-not (Test-Path -LiteralPath (Join-Path $RepoRoot $root) -PathType Container)) {
      throw "REFERENCE_CLASSIFICATION_FAILED: legacy caller root is missing: $root"
    }
    foreach ($relative in (Invoke-Git @('ls-files', '--', $root))) {
      if ([IO.Path]::GetExtension($relative) -notin @('.java', '.yml', '.yaml', '.xml', '.properties')) { continue }
      $absolute = Join-Path $RepoRoot $relative
      if ((Get-Content -Raw -Encoding UTF8 -LiteralPath $absolute) -match '(?i)employee-service') {
        [void]$legacyCallerMatches.Add($relative.Replace('\', '/'))
      }
    }
  }
  if ($legacyCallerMatches.Count -eq 0) {
    throw 'REFERENCE_CLASSIFICATION_FAILED: no p0_pending_legacy_caller reference was found'
  }

  $employeeConfig = 'config-service/src/main/resources/config/application-emp.yml'
  $employeeConfigAbsolute = Join-Path $RepoRoot $employeeConfig
  if (-not (Test-Path -LiteralPath $employeeConfigAbsolute -PathType Leaf) -or
      (Get-Content -Raw -Encoding UTF8 -LiteralPath $employeeConfigAbsolute) -notmatch '(?i)(employee|9210)') {
    throw 'REFERENCE_CLASSIFICATION_FAILED: inactive employee configuration is missing'
  }

  return @(
    [ordered]@{
      classification = 'evidence_only/inactive_business_consumer'
      paths = @('employee-service/')
      evidencePaths = @('employee-service/pom.xml')
      owner = '02A'
      allowedUntil = 'target employee contract migration is separately designed'
    },
    [ordered]@{
      classification = 'p0_pending_legacy_caller'
      paths = @('agent-adapter-employee/', 'agent-service/')
      evidencePaths = @($legacyCallerMatches | Sort-Object)
      owner = '02 P0'
      allowedUntil = 'P0 legacy Agent isolation completes'
    },
    [ordered]@{
      classification = 'inactive_business_configuration'
      paths = @($employeeConfig)
      evidencePaths = @($employeeConfig)
      owner = 'employee-service'
      allowedUntil = 'employee-service is separately reactivated or retired'
    }
  )
}

function Assert-StaticExitState {
  $modules = @(Get-RootModules)
  if (@($modules | Where-Object { $_ -eq '../employee-service' }).Count -ne 0) {
    throw 'CONSUMER_STILL_ACTIVE: serviceCenter reactor still contains ../employee-service'
  }
  if (@($modules | Where-Object { $_ -eq '../document-provider-adapter' }).Count -ne 1) {
    throw 'CONSUMER_STILL_ACTIVE: document-provider-adapter must remain in serviceCenter reactor for P0'
  }

  Assert-PowerShellSyntax $StartScript
  $startContent = Get-Content -Raw -Encoding UTF8 -LiteralPath $StartScript
  foreach ($pattern in @("Name\s*=\s*'employee-service'", 'Port\s*=\s*9210', "'EMPLOYEE-SERVICE'")) {
    if ($startContent -match $pattern) {
      throw "RUNTIME_ENTRY_STILL_ACTIVE: start-all-services.ps1 matches $pattern"
    }
  }
  if ($startContent -notmatch "'DOCUMENT-GENERATION-ADAPTER'") {
    throw 'SCOPE_EXPANSION_REQUIRED: DOCUMENT-GENERATION-ADAPTER wait item belongs to P0 and must remain'
  }

  $routerContent = Get-Content -Raw -Encoding UTF8 -LiteralPath $GatewayRouter
  foreach ($literal in @('.route("emp"', '/employees/**', '/employee-workflow.html', '/employee-es.html', 'lb://employee-service')) {
    if ($routerContent.Contains($literal)) {
      throw "RUNTIME_ENTRY_STILL_ACTIVE: GatewayRouter still contains $literal"
    }
  }
  foreach ($requiredRoute in @('hello_route', 'ws_route', 'auth_route', 'direct_route', 'mq_route', 'workflow', 'agent_page', 'agent_api')) {
    if (-not $routerContent.Contains(".route(`"$requiredRoute`"")) {
      throw "SCOPE_EXPANSION_REQUIRED: unrelated Gateway route missing: $requiredRoute"
    }
  }

  $homeContent = Get-Content -Raw -Encoding UTF8 -LiteralPath $HomePage
  foreach ($literal in @('Employee ES', 'Employee workflow', 'openEmployeeEs', 'openEmpWorkflow', '/employee-es.html', '/employee-workflow.html')) {
    if ($homeContent.Contains($literal)) {
      throw "RUNTIME_ENTRY_STILL_ACTIVE: home.html still contains $literal"
    }
  }
  if (-not $homeContent.Contains('Agent Query') -or -not $homeContent.Contains('openAgent')) {
    throw 'SCOPE_EXPANSION_REQUIRED: Agent home entry must remain'
  }

  Assert-NoEmployeeChanges
  if (-not (Test-Path -LiteralPath $GatewayTest -PathType Leaf)) {
    throw "required Gateway test not found: $GatewayTest"
  }
}

function Assert-NoOtherActiveEntry {
  param([Parameter(Mandatory)][string[]]$AllowedReferencePaths)

  $textExtensions = @(
    '.xml', '.ps1', '.psm1', '.sh', '.cmd', '.bat', '.yml', '.yaml',
    '.properties', '.toml', '.gradle', '.kts', '.py', '.html', '.java',
    '.json', '.config', '.conf', '.ini'
  )
  $activeFiles = @(Invoke-Git @('ls-files', '-co', '--exclude-standard') | Sort-Object -Unique) | Where-Object {
    $leafName = [IO.Path]::GetFileName($_)
    $_ -notmatch '^(docs/|employee-service/)' -and
    $_ -ne 'config-service/src/main/resources/config/application-emp.yml' -and
    $_ -ne 'scripts/verify-agent-external-consumer-exit.ps1' -and
    $_ -notin $AllowedReferencePaths -and
    ([IO.Path]::GetExtension($_) -in $textExtensions -or $leafName -in @('Dockerfile', 'Jenkinsfile', 'Makefile'))
  }
  $violations = foreach ($relative in $activeFiles) {
    $absolute = Join-Path $RepoRoot $relative
    if (-not (Test-Path -LiteralPath $absolute -PathType Leaf)) { continue }
    $content = Get-Content -Raw -Encoding UTF8 -LiteralPath $absolute
    if ($content -match '(?i)(employee-service(?:_alpha)?|localhost:9210|\b9210\b)') {
      $relative
    }
  }
  if (@($violations).Count -gt 0) {
    throw "CONSUMER_STILL_ACTIVE: unclassified active entry found: $(@($violations) -join ',')"
  }
}

function Invoke-PostApplyValidation {
  if (-not (Test-Path -LiteralPath $Maven -PathType Leaf)) {
    throw "VALIDATION_FAILED: Maven wrapper not found: $Maven"
  }
  $results = @()
  $results += Invoke-CheckedCommand `
    -DisplayCommand '.\serviceCenter\mvnw.cmd -f .\serviceCenter\pom.xml --batch-mode -DskipTests install' `
    -FilePath $Maven `
    -Arguments @('-f', 'serviceCenter/pom.xml', '--batch-mode', '-DskipTests', 'install') `
    -ResultSummary 'complete 28-module reactor passed; employee-service absent; document-provider-adapter passed'
  $results += Invoke-CheckedCommand `
    -DisplayCommand '.\serviceCenter\mvnw.cmd -f .\serviceCenter\pom.xml --batch-mode -pl ../gateway-service -am test' `
    -FilePath $Maven `
    -Arguments @('-f', 'serviceCenter/pom.xml', '--batch-mode', '-pl', '../gateway-service', '-am', 'test') `
    -ResultSummary 'common-security and gateway-service tests passed, including GatewayEmployeeRouteExitTest'
  $results += Invoke-CheckedCommand `
    -DisplayCommand '.\serviceCenter\mvnw.cmd -f .\serviceCenter\pom.xml --batch-mode -DskipTests -Dincludes=com.dylan:employee-service,com.dylan:employee-service_alpha dependency:tree' `
    -FilePath $Maven `
    -Arguments @('-f', 'serviceCenter/pom.xml', '--batch-mode', '-DskipTests', '-Dincludes=com.dylan:employee-service,com.dylan:employee-service_alpha', 'dependency:tree') `
    -ResultSummary 'active reactor dependency trees contain no employee-service or employee-service_alpha artifact' `
    -ForbiddenOutputPattern '^\[INFO\]\s+[| +\\-]*com\.dylan:employee-service(?:_alpha)?:'
  return $results
}

function Get-PostApplyContext {
  param(
    [Parameter(Mandatory)][string]$StatePath,
    [Parameter(Mandatory)][string]$OutputAbsolute
  )

  if (Test-Path -LiteralPath $StatePath -PathType Leaf) {
    $state = Get-Content -Raw -Encoding UTF8 -LiteralPath $StatePath | ConvertFrom-Json
    if ($state.status -ne 'EXIT_PREFLIGHT_PASSED') {
      throw 'EXIT_PREFLIGHT_FAILED: invalid Preflight state'
    }
    $state | Add-Member -NotePropertyName contextKind -NotePropertyValue 'PREFLIGHT_STATE' -Force
    return $state
  }
  if (-not (Test-Path -LiteralPath $OutputAbsolute -PathType Leaf)) {
    throw 'EXIT_PREFLIGHT_FAILED: matching Preflight state or verified report was not found'
  }

  $existing = Get-Content -Raw -Encoding UTF8 -LiteralPath $OutputAbsolute | ConvertFrom-Json
  if ($existing.status -ne 'CONSUMER_EXIT_VERIFIED' -or
      $existing.resolutionId -ne $ResolutionId -or
      [string]::IsNullOrWhiteSpace($existing.authorizationRef) -or
      [string]::IsNullOrWhiteSpace($existing.impactAcceptanceRef) -or
      [string]::IsNullOrWhiteSpace($existing.bootstrapScriptHash)) {
    throw 'RECOVERY_REQUIRED: existing resolution report cannot authorize repeat verification'
  }
  Assert-ResolutionReportSchema $existing
  Assert-ResultFileManifestCurrent $existing
  $currentDesignHashes = Assert-DesignBaseline
  foreach ($key in $ExpectedDesignHashes.Keys) {
    if ($existing.designHashes.$key -ne $currentDesignHashes[$key]) {
      throw "DESIGN_BASELINE_CHANGED: existing report hash mismatch for $key"
    }
  }
  return [pscustomobject]@{
    status = 'EXIT_PREFLIGHT_PASSED'
    contextKind = 'VERIFIED_REPORT_REFRESH'
    baselineCommit = $existing.baselineCommit
    authorizationRef = $existing.authorizationRef
    impactAcceptanceRef = $existing.impactAcceptanceRef
    bootstrapScriptHash = $existing.bootstrapScriptHash
    designHashes = $existing.designHashes
    completedAt = $existing.startedAt
    validationAttempts = @($existing.validationAttempts)
  }
}

function Assert-ResolutionReportSchema {
  param([Parameter(Mandatory)][object]$Report)

  $consumer = @($Report.consumers)[0]
  $classificationNames = @($Report.referenceClassifications | ForEach-Object { $_.classification })
  $manifestPaths = @($Report.resultFileManifest | ForEach-Object { $_.path })
  $verifierManifest = @($Report.resultFileManifest | Where-Object { $_.path -eq 'scripts/verify-agent-external-consumer-exit.ps1' })
  if ($Report.schemaVersion -ne '1.0' -or
      $Report.status -ne 'CONSUMER_EXIT_VERIFIED' -or
      $Report.closureSemantics -ne 'CLOSED_FOR_P0_BY_INACTIVITY' -or
      $Report.closureEstablishedBy -ne 'CONSUMER_EXIT_VERIFIED_REPORT_PUBLICATION' -or
      $Report.p0PreflightRole -ne 'REVALIDATE_AND_GATE_ONLY' -or
      @($verifierManifest).Count -ne 1 -or
      $Report.verifierScriptHash -ne $verifierManifest[0].sha256 -or
      @($Report.consumers).Count -ne 1 -or
      @($Report.referenceClassifications).Count -ne 3 -or
      @($classificationNames | Sort-Object -Unique).Count -ne 3 -or
      'evidence_only/inactive_business_consumer' -notin $classificationNames -or
      'p0_pending_legacy_caller' -notin $classificationNames -or
      'inactive_business_configuration' -notin $classificationNames -or
      @($Report.validationCommands).Count -ne 3 -or
      @($Report.validationCommands | Where-Object { $_.status -ne 'PASSED' }).Count -ne 0 -or
      @($Report.resultFileManifest).Count -ne 6 -or
      @($manifestPaths | Sort-Object -Unique).Count -ne 6 -or
      $consumer.name -ne 'employee-service' -or
      $consumer.reactorStatus -ne 'INACTIVE' -or
      $consumer.defaultStartStatus -ne 'INACTIVE' -or
      $consumer.gatewayStatus -ne 'INACTIVE' -or
      $consumer.defaultUiStatus -ne 'INACTIVE' -or
      $consumer.sourceIntegrity -ne 'UNCHANGED' -or
      $consumer.renamedToAlpha -ne $false -or
      @($Report.unresolvedItems).Count -ne 0) {
    throw 'REPORT_SCHEMA_INVALID: required fields or cardinalities do not match schemaVersion 1.0'
  }
  $roundTrip = $Report | ConvertTo-Json -Depth 12 | ConvertFrom-Json
  if ($roundTrip.resolutionId -ne $Report.resolutionId) {
    throw 'REPORT_SCHEMA_INVALID: JSON round-trip changed the resolution identity'
  }
}

function Assert-ResultFileManifestCurrent {
  param([Parameter(Mandatory)][object]$Report)

  foreach ($entry in @($Report.resultFileManifest)) {
    $absolute = Join-Path $RepoRoot $entry.path
    if (-not (Test-Path -LiteralPath $absolute -PathType Leaf) -or
        (Get-Sha256 $absolute) -ne $entry.sha256) {
      throw "RECOVERY_REQUIRED: result manifest drift: $($entry.path)"
    }
  }
}

function Get-ResultFileManifest {
  $paths = @(
    'serviceCenter/pom.xml',
    'scripts/start-all-services.ps1',
    'gateway-service/src/main/java/com/dylan/springgateway/config/GatewayRouter.java',
    'auth-service/src/main/resources/static/home.html',
    'scripts/verify-agent-external-consumer-exit.ps1',
    'gateway-service/src/test/java/com/dylan/springgateway/config/GatewayEmployeeRouteExitTest.java'
  )
  return @($paths | ForEach-Object {
      $absolute = Join-Path $RepoRoot $_
      [ordered]@{ path = $_; sha256 = Get-Sha256 $absolute }
    })
}

function Invoke-Preflight {
  foreach ($value in @($ExpectedHead, $AuthorizationRef, $ImpactAcceptanceRef, $BootstrapScriptHash)) {
    if ([string]::IsNullOrWhiteSpace($value)) {
      throw 'Preflight requires ExpectedHead, AuthorizationRef, ImpactAcceptanceRef, and BootstrapScriptHash.'
    }
  }

  $designHashes = Assert-DesignBaseline
  $head = (@(Invoke-Git @('rev-parse', 'HEAD'))[0]).Trim()
  if ($head -ne $ExpectedHead) {
    throw "DESIGN_BASELINE_CHANGED: ExpectedHead=$ExpectedHead actual=$head"
  }
  if ((Get-Sha256 $ScriptPath) -ne $BootstrapScriptHash.ToUpperInvariant()) {
    throw 'EXIT_PREFLIGHT_FAILED: BootstrapScriptHash does not match the verifier script'
  }
  Assert-PreflightWorkspace
  Assert-EmployeeStopped
  if (-not (Test-Path -LiteralPath $EmployeeRoot -PathType Container)) {
    throw 'EXIT_PREFLIGHT_FAILED: employee-service directory is missing'
  }
  $modules = @(Get-RootModules)
  if (@($modules | Where-Object { $_ -eq '../employee-service' }).Count -ne 1) {
    throw 'EXIT_PREFLIGHT_FAILED: expected exactly one employee-service root module before apply'
  }
  if (@($modules | Where-Object { $_ -eq '../document-provider-adapter' }).Count -ne 1) {
    throw 'EXIT_PREFLIGHT_FAILED: document-provider-adapter root module must remain for P0'
  }

  $state = [ordered]@{
    schemaVersion = '1.0'
    mode = 'Preflight'
    status = 'EXIT_PREFLIGHT_PASSED'
    baselineCommit = $head
    authorizationRef = $AuthorizationRef
    impactAcceptanceRef = $ImpactAcceptanceRef
    bootstrapScriptHash = $BootstrapScriptHash.ToUpperInvariant()
    designHashes = $designHashes
    completedAt = [DateTimeOffset]::UtcNow.ToString('o')
  }
  Write-JsonAtomic -Value $state -Path (Get-StatePath)
  $state | ConvertTo-Json -Depth 8
}

function Invoke-PostApply {
  if ([string]::IsNullOrWhiteSpace($ResolutionId)) {
    throw 'PostApply requires ResolutionId.'
  }
  $statePath = Get-StatePath
  $outputAbsolute = Get-OutputAbsolutePath
  $preflight = Get-PostApplyContext -StatePath $statePath -OutputAbsolute $outputAbsolute
  $designHashes = Assert-DesignBaseline
  $head = (@(Invoke-Git @('rev-parse', 'HEAD'))[0]).Trim()
  if ($preflight.contextKind -eq 'PREFLIGHT_STATE') {
    if ($head -ne $preflight.baselineCommit) {
      throw "DESIGN_BASELINE_CHANGED: Preflight head=$($preflight.baselineCommit) actual=$head"
    }
  } else {
    Assert-GitAncestor -Ancestor $preflight.baselineCommit -Descendant $head
  }
  Assert-StaticExitState
  $sourceIntegrity = Get-EmployeeSourceIntegrity -BaselineCommit $preflight.baselineCommit
  $referenceClassifications = @(Get-EmployeeReferenceClassifications)
  $allowedReferencePaths = @($referenceClassifications | ForEach-Object { $_.evidencePaths } | Sort-Object -Unique)
  Assert-NoOtherActiveEntry -AllowedReferencePaths $allowedReferencePaths

  $changed = @(Get-ChangedPaths)
  $allowed = @(
    'auth-service/src/main/resources/static/home.html',
    'docs/design/agent/L2/02_目标基线隔离与迁移门禁_L2实施详细设计_v1.0.md',
    'docs/design/agent/L2/02A_外部消费者活动基线退出与DB-02-001关闭_L2实施详细设计_v1.0.md',
    'docs/design/agent/L2/02A_外部消费者活动基线退出与DB-02-001关闭_L2实施详细设计_v1.0_代码评审报告.md',
    'gateway-service/src/main/java/com/dylan/springgateway/config/GatewayRouter.java',
    'gateway-service/src/test/java/com/dylan/springgateway/config/GatewayEmployeeRouteExitTest.java',
    'scripts/start-all-services.ps1',
    'scripts/verify-agent-external-consumer-exit.ps1',
    'serviceCenter/pom.xml'
  )
  $unexpected = @($changed | Where-Object { $_ -notin $allowed -and $_ -ne $OutputPath.Replace('\', '/') })
  if ($unexpected.Count -gt 0) {
    throw "SCOPE_EXPANSION_REQUIRED: unexpected changed paths: $($unexpected -join ',')"
  }

  $validationResults = @(Invoke-PostApplyValidation)
  $mavenVersionOutput = @(& $Maven -v 2>&1 | ForEach-Object { $_.ToString() })
  if ($LASTEXITCODE -ne 0) {
    throw 'VALIDATION_FAILED: unable to read Maven and Java versions'
  }
  $mavenVersion = @($mavenVersionOutput | Where-Object { $_ -match '^Apache Maven ' } | Select-Object -First 1)
  $javaVersion = @($mavenVersionOutput | Where-Object { $_ -match '^Java version:' } | Select-Object -First 1)
  $now = [DateTimeOffset]::UtcNow.ToString('o')
  $report = [ordered]@{
    schemaVersion = '1.0'
    resolutionId = $ResolutionId
    chosenSolution = 'SCHEME_B_ACTIVE_BASELINE_EXIT'
    baselineCommit = $preflight.baselineCommit
    bootstrapScriptHash = $preflight.bootstrapScriptHash
    verifierScriptHash = Get-Sha256 $ScriptPath
    designHashes = $designHashes
    authorizationRef = $preflight.authorizationRef
    impactAcceptanceRef = $preflight.impactAcceptanceRef
    consumers = @(
      [ordered]@{
        name = 'employee-service'
        reactorStatus = 'INACTIVE'
        defaultStartStatus = 'INACTIVE'
        gatewayStatus = 'INACTIVE'
        defaultUiStatus = 'INACTIVE'
        ciStatus = 'NOT_SELECTED'
        releaseStatus = 'NOT_AUTHORIZED'
        sourceIntegrity = 'UNCHANGED'
        sourceIntegrityEvidence = $sourceIntegrity
        renamedToAlpha = $false
      }
    )
    referenceClassifications = $referenceClassifications
    checks = @(
      [ordered]@{ id = 'TEST-002'; status = 'PASSED'; detail = 'complete reactor build passed; employee-service absent and document-provider-adapter present' },
      [ordered]@{ id = 'TEST-003'; status = 'PASSED'; detail = 'default start and Eureka wait entries removed; P0 generation wait item preserved' },
      [ordered]@{ id = 'TEST-004'; status = 'PASSED'; detail = 'Gateway tests passed; employee routes and default home entries are absent' },
      [ordered]@{ id = 'TEST-005'; status = 'PASSED'; detail = "employee-service unchanged: trackedFiles=$($sourceIntegrity.trackedFileCount), aggregateSha256=$($sourceIntegrity.aggregateSha256)" },
      [ordered]@{ id = 'TEST-006'; status = 'PASSED'; detail = 'tracked/untracked active-entry scan and dependency trees found no unclassified employee activation' },
      [ordered]@{ id = 'TEST-007'; status = 'PASSED'; detail = 'report publication closes DB-02-001 and is bound to current design hashes, baseline HEAD, authorization, and result manifest; P0 Preflight only revalidates and gates' }
    )
    toolVersions = [ordered]@{
      powershell = $PSVersionTable.PSVersion.ToString()
      git = ((Invoke-Git @('--version')) -join ' ').Trim()
      maven = ($mavenVersion -join '').Trim()
      java = ($javaVersion -join '').Trim()
    }
    validationCommands = $validationResults
    startedAt = $preflight.completedAt
    completedAt = $now
    failureCodes = @()
    validationAttempts = @($preflight.validationAttempts)
    unresolvedItems = @()
    resultFileManifest = @(Get-ResultFileManifest)
    status = 'CONSUMER_EXIT_VERIFIED'
    closureSemantics = 'CLOSED_FOR_P0_BY_INACTIVITY'
    closureEstablishedBy = 'CONSUMER_EXIT_VERIFIED_REPORT_PUBLICATION'
    p0PreflightRole = 'REVALIDATE_AND_GATE_ONLY'
    recoveryPolicy = 'P0_REPORT_GOVERNS'
    assertions = @(
      'employee-service was not deleted or renamed',
      'employee contracts were not migrated and employee functionality was not replaced',
      'no production shutdown or production readiness is asserted',
      '02 P0 Preflight revalidates this closure evidence and does not create or change the DB-02-001 closure fact',
      'document-provider-adapter and document-generation-adapter remain governed by 02 P0'
    )
  }

  Assert-ResolutionReportSchema $report
  $lockPath = $outputAbsolute + '.lock'
  $lock = $null
  try {
    $lockDirectory = Split-Path -Parent $lockPath
    if (-not (Test-Path -LiteralPath $lockDirectory)) {
      New-Item -ItemType Directory -Path $lockDirectory -Force | Out-Null
    }
    $lock = [IO.File]::Open($lockPath, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write, [IO.FileShare]::None)
    Write-JsonAtomic -Value $report -Path $outputAbsolute
  } finally {
    if ($null -ne $lock) { $lock.Dispose() }
    if (Test-Path -LiteralPath $lockPath) { Remove-Item -LiteralPath $lockPath -Force }
  }
  if (Test-Path -LiteralPath $statePath) {
    Remove-Item -LiteralPath $statePath -Force
  }
  $report | ConvertTo-Json -Depth 12
}

function Invoke-RecoveryCheck {
  if ([string]::IsNullOrWhiteSpace($ResolutionId) -or [string]::IsNullOrWhiteSpace($P0ReportPath)) {
    throw 'RecoveryCheck requires ResolutionId and P0ReportPath.'
  }
  $outputAbsolute = Get-OutputAbsolutePath
  if (-not (Test-Path -LiteralPath $outputAbsolute -PathType Leaf)) {
    throw "resolution report not found: $outputAbsolute"
  }
  $report = Get-Content -Raw -Encoding UTF8 -LiteralPath $outputAbsolute | ConvertFrom-Json
  if ($report.resolutionId -ne $ResolutionId -or $report.status -ne 'CONSUMER_EXIT_VERIFIED') {
    throw 'RECOVERY_REQUIRED: resolution report identity or status mismatch'
  }
  Assert-ResolutionReportSchema $report
  Assert-ResultFileManifestCurrent $report
  $head = (@(Invoke-Git @('rev-parse', 'HEAD'))[0]).Trim()
  Assert-GitAncestor -Ancestor $report.baselineCommit -Descendant $head
  Assert-EmployeeBaselineIntegrity -BaselineCommit $report.baselineCommit -CurrentCommit $head
  $currentDesignHashes = Assert-DesignBaseline
  foreach ($key in $ExpectedDesignHashes.Keys) {
    if ($report.designHashes.$key -ne $currentDesignHashes[$key]) {
      throw "DESIGN_BASELINE_CHANGED: report hash mismatch for $key"
    }
  }
  Assert-StaticExitState
  $referenceClassifications = @(Get-EmployeeReferenceClassifications)
  $allowedReferencePaths = @($referenceClassifications | ForEach-Object { $_.evidencePaths } | Sort-Object -Unique)
  Assert-NoOtherActiveEntry -AllowedReferencePaths $allowedReferencePaths

  $p0Absolute = Get-P0ReportAbsolutePath
  if (Test-Path -LiteralPath $p0Absolute -PathType Leaf) {
    $p0Content = Get-Content -Raw -Encoding UTF8 -LiteralPath $p0Absolute
    $reportHash = Get-Sha256 $outputAbsolute
    try {
      $p0Report = $p0Content | ConvertFrom-Json
    } catch {
      throw 'RECOVERY_REQUIRED: P0 report is not valid JSON'
    }
    $referencePath = [string]$p0Report.externalConsumerResolutionRef.path
    $referenceHash = [string]$p0Report.externalConsumerResolutionRef.sha256
    $normalizedReferencePath = $referencePath.Replace('\', '/')
    $referencesReport = [string]::Equals($normalizedReferencePath, $ExpectedOutputRelativePath, [StringComparison]::OrdinalIgnoreCase)
    $referencesHash = [string]::Equals($referenceHash, $reportHash, [StringComparison]::OrdinalIgnoreCase)
    $p0Started = $p0Content -match '(?i)(STARTED|APPLIED|COMPLETED|CONSUMED_BY_P0)'
    if ($p0Started -and (-not $referencesReport -or -not $referencesHash)) {
      throw 'RECOVERY_REQUIRED: started P0 report has a missing or inconsistent external consumer reference'
    }
    if ($referencesReport -and $referencesHash -and $p0Started) {
      throw 'ROLLBACK_ORDER_VIOLATION: P0 has consumed this report and started project actions'
    }
  }

  [ordered]@{
    schemaVersion = '1.0'
    resolutionId = $ResolutionId
    status = 'RECOVERY_ALLOWED_BEFORE_P0'
    requiredOrder = @('default homepage', 'Gateway route', 'start/Eureka entries', 'root module')
    checkedAt = [DateTimeOffset]::UtcNow.ToString('o')
  } | ConvertTo-Json -Depth 6
}

switch ($Mode) {
  'Preflight' { Invoke-Preflight }
  'PostApply' { Invoke-PostApply }
  'RecoveryCheck' { Invoke-RecoveryCheck }
}
