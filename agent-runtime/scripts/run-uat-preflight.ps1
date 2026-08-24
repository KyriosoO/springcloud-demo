[CmdletBinding()]
param(
    [ValidateSet('Preparation', 'Execution')]
    [string]$Mode = 'Preparation',
    [string]$RepositoryRoot = ''
)

$ErrorActionPreference = 'Stop'
if ([string]::IsNullOrWhiteSpace($RepositoryRoot)) {
    $RepositoryRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
}
$repository = [IO.Path]::GetFullPath($RepositoryRoot)
$requiredAssets = @(
    'docs\REQ_00_SINGLE_AGENT_QUERY_REQUIREMENTS.md',
    'docs\design\L0_00_SINGLE_AGENT_ARCHITECTURE.md',
    'docs\design\L1_00_SINGLE_AGENT_CORE_RUNTIME_ARCHITECTURE.md',
    'docs\design\L1_01_SINGLE_AGENT_KNOWLEDGE_QUERY_ARCHITECTURE.md',
    'docs\design\L1_02_SINGLE_AGENT_BUSINESS_QUERY_ADAPTER_ARCHITECTURE.md',
    'docs\design\L2_00_00_SINGLE_AGENT_SPRING_ACCESS_RUNTIME_COORDINATION_DETAILED_DESIGN.md',
    'docs\design\L2_00_01_SINGLE_AGENT_CORE_EXECUTION_CAPABILITY_REGISTRATION_DETAILED_DESIGN.md',
    'docs\design\L2_00_02_SINGLE_AGENT_DEEPSEEK_MODEL_ACCESS_CONTROLLED_GENERATION_DETAILED_DESIGN.md',
    'docs\design\L2_00_03_SINGLE_AGENT_USER_ROLE_AUTHORITY_CONVERTER_DETAILED_DESIGN.md',
    'docs\design\L2_01_00_SINGLE_AGENT_KNOWLEDGE_QUERY_FLOW_CONFIGURATION_DETAILED_DESIGN.md',
    'docs\design\L2_01_01_SINGLE_AGENT_KNOWLEDGE_RETRIEVAL_LOCAL_MODEL_DETAILED_DESIGN.md',
    'docs\design\L2_01_02_SINGLE_AGENT_KNOWLEDGE_EVIDENCE_EGRESS_SUMMARY_EFFECTIVENESS_DETAILED_DESIGN.md',
    'docs\design\L2_02_00_SINGLE_AGENT_BUSINESS_QUERY_COMMON_CONSTRAINTS_CONFIGURATION_EGRESS_DETAILED_DESIGN.md',
    'docs\design\L2_02_01_SINGLE_AGENT_EMPLOYEE_ADAPTER_AUTHORIZATION_DETAILED_DESIGN.md',
    'docs\design\L2_02_02_SINGLE_AGENT_TRANSACTION_ADAPTER_AUTHORIZATION_DETAILED_DESIGN.md',
    'docs\plans\P3_00_SINGLE_AGENT_CODE_IMPLEMENTATION_PLAN.md',
    'agent-contracts\openapi\agent-public-v1.yaml',
    'agent-runtime\scripts\run-system-e2e.ps1',
    'agent-runtime\tests\uat\uat_cases.v1.json',
    '.tmp\agent-runtime-venv\Scripts\python.exe'
)

function Test-TcpReady([int]$Port) {
    $client = [Net.Sockets.TcpClient]::new()
    try {
        $connect = $client.ConnectAsync('127.0.0.1', $Port)
        return $connect.Wait(1500) -and $client.Connected
    } catch {
        return $false
    } finally {
        $client.Dispose()
    }
}

function Test-PortFree([int]$Port) {
    $listener = Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue
    return -not [bool]$listener
}

$missingAssets = @(
    $requiredAssets | Where-Object { -not (Test-Path -LiteralPath (Join-Path $repository $_)) }
)
$tools = [ordered]@{
    git = [bool](Get-Command git -ErrorAction SilentlyContinue)
    java = [bool](Get-Command java -ErrorAction SilentlyContinue)
    maven = [bool](Get-Command mvn.cmd -ErrorAction SilentlyContinue)
    powershell = [bool](Get-Command pwsh -ErrorAction SilentlyContinue)
    python = Test-Path -LiteralPath (Join-Path $repository '.tmp\agent-runtime-venv\Scripts\python.exe')
}
$infrastructure = [ordered]@{
    elasticsearch9200 = Test-TcpReady 9200
    embedding8908 = Test-TcpReady 8908
    rerank8909 = Test-TcpReady 8909
}
$ownedPorts = [ordered]@{
    auth8090 = Test-PortFree 8090
    knowledgeProvider9201 = Test-PortFree 9201
    employee9210 = Test-PortFree 9210
    transaction8182 = Test-PortFree 8182
}
$caseCatalogPath = Join-Path $repository 'agent-runtime\tests\uat\uat_cases.v1.json'
$caseCatalogValid = $false
$caseCatalogSha256 = $null
if (Test-Path -LiteralPath $caseCatalogPath) {
    try {
        $catalog = Get-Content -LiteralPath $caseCatalogPath -Raw -Encoding UTF8 | ConvertFrom-Json
        $caseCatalogValid = $catalog.schemaVersion -eq 1 -and
            $catalog.suiteId -eq 'single-agent-uat-v1' -and
            $catalog.executionProfile.modelProvider -eq 'stub' -and
            $catalog.executionProfile.externalModelOutboundMax -eq 0 -and
            @($catalog.cases).Count -eq 16
        $caseCatalogSha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $caseCatalogPath).Hash.ToLowerInvariant()
    } catch {
        $caseCatalogValid = $false
    }
}

$gitHead = (& git -C $repository rev-parse HEAD 2>$null)
$statusLines = @(& git -C $repository status --porcelain=v1 --untracked-files=all 2>$null)
$productionPrefixes = @(
    'agent-runtime/src/',
    'agent-service/src/main/',
    'employee-service/src/main/',
    'mq-procedure-service/src/main/',
    'es-query-service/src/main/',
    'es-query-api/src/main/',
    'common-security/src/main/',
    'gateway-service/src/main/'
)
$dirtyProductionPaths = @()
foreach ($line in $statusLines) {
    if ($line.Length -lt 4) {
        continue
    }
    $path = $line.Substring(3).Replace('\', '/')
    if ($path.Contains(' -> ')) {
        $path = $path.Split(' -> ')[-1]
    }
    if ($productionPrefixes | Where-Object { $path.StartsWith($_, [StringComparison]::OrdinalIgnoreCase) }) {
        $dirtyProductionPaths += $path
    }
}

$conflictingBuildProcessIds = @(
    Get-CimInstance Win32_Process -Filter "Name='java.exe'" -ErrorAction SilentlyContinue |
        Where-Object {
            $commandLine = [string]$_.CommandLine
            $commandLine.IndexOf('org.codehaus.plexus.classworlds.launcher.Launcher', [StringComparison]::OrdinalIgnoreCase) -ge 0 -and
                $commandLine.IndexOf('mq-procedure-service', [StringComparison]::OrdinalIgnoreCase) -ge 0
        } |
        ForEach-Object { [int]$_.ProcessId }
)

$modelProvider = [Environment]::GetEnvironmentVariable('AGENT_MODEL_PROVIDER', 'Process')
$modelProviderSafe = [string]::IsNullOrWhiteSpace($modelProvider) -or $modelProvider -eq 'stub'
$employeeInputPresent = -not [string]::IsNullOrWhiteSpace(
    [Environment]::GetEnvironmentVariable('SYSTEM_E2E_EMPLOYEE_IDENTIFIER', 'Process')
)
$transactionInputPresent = -not [string]::IsNullOrWhiteSpace(
    [Environment]::GetEnvironmentVariable('UAT_TRANSACTION_TYPE', 'Process')
)
$pendingInputs = @()
if (-not $employeeInputPresent) { $pendingInputs += 'SYSTEM_E2E_EMPLOYEE_IDENTIFIER' }
if (-not $transactionInputPresent) { $pendingInputs += 'UAT_TRANSACTION_TYPE' }

$staticReady = $missingAssets.Count -eq 0 -and
    -not ($tools.Values -contains $false) -and
    -not ($infrastructure.Values -contains $false) -and
    -not ($ownedPorts.Values -contains $false) -and
    $caseCatalogValid -and
    $modelProviderSafe -and
    $conflictingBuildProcessIds.Count -eq 0 -and
    $dirtyProductionPaths.Count -eq 0
$executionReady = $staticReady -and $pendingInputs.Count -eq 0
$ready = if ($Mode -eq 'Execution') { $executionReady } else { $staticReady }

$result = [ordered]@{
    schemaVersion = 1
    checkId = 'single-agent-uat-preflight-v1'
    mode = $Mode
    status = if ($ready) { 'ready' } else { 'blocked' }
    gitHead = [string]$gitHead
    dirtyPathCount = $statusLines.Count
    dirtyProductionPaths = @($dirtyProductionPaths | Sort-Object -Unique)
    conflictingBuildProcessIds = @($conflictingBuildProcessIds | Sort-Object -Unique)
    missingAssets = $missingAssets
    tools = $tools
    infrastructure = $infrastructure
    ownedPortsFree = $ownedPorts
    caseCatalogValid = $caseCatalogValid
    caseCatalogSha256 = $caseCatalogSha256
    modelProviderSafe = $modelProviderSafe
    pendingExecutionInputs = $pendingInputs
}
$result | ConvertTo-Json -Depth 6
if (-not $ready) {
    exit 1
}
