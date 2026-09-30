[CmdletBinding()]
param(
    [string]$RepositoryRoot = (Split-Path -Parent (Split-Path -Parent $PSScriptRoot)),
    [Parameter(ParameterSetName = 'Run', Mandatory = $true)][string]$ManifestPath,
    [Parameter(ParameterSetName = 'Run', Mandatory = $true)][string]$AuthorizationPath,
    [Parameter(ParameterSetName = 'Run', Mandatory = $true)][string]$ExpectedManifestSha256,
    [Parameter(ParameterSetName = 'Startup', Mandatory = $true)][switch]$StartupPreflightOnly,
    [Parameter(ParameterSetName = 'Startup', Mandatory = $true)][string]$BuildAttestationPath
)

$ErrorActionPreference = 'Stop'
$startup = $PSCmdlet.ParameterSetName -eq 'Startup'
$repository = [IO.Path]::GetFullPath($RepositoryRoot)
$runtimeRoot = Join-Path $repository 'agent-runtime'
$manifestFull = $null
$authorizationFull = $null
$runtimePython = Join-Path $runtimeRoot '.venv\Scripts\python.exe'
$corpusPython = Join-Path $repository 'knowledge-corpus-tools\.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $runtimePython -PathType Leaf) -or
    -not (Test-Path -LiteralPath $corpusPython -PathType Leaf)) {
    throw 'knowledge.measure.isolated_python_missing'
}
$tempBase = [IO.Path]::GetFullPath([IO.Path]::GetTempPath())
$startupStage = 'startup_input'
$runRoot = Join-Path $tempBase $(if ($startup) {
        "codex-knowledge-measure-startup-$([Guid]::NewGuid().ToString('N'))"
    } else {
        "codex-knowledge-measure-$([Guid]::NewGuid().ToString('N'))"
    })
if ($startup) {
    $buildFull = [IO.Path]::GetFullPath($BuildAttestationPath)
    if ([IO.Path]::GetFileName($buildFull) -cne 'build-attestation.json' -or
        -not (Test-Path -LiteralPath $buildFull -PathType Leaf)) {
        throw 'knowledge.measure.startup_build_attestation_invalid'
    }
    New-Item -ItemType Directory -Path $runRoot | Out-Null
    try {
        $manifestFull = Join-Path $runRoot 'startup-input.json'
        $preparation = Start-Process -FilePath $runtimePython -ArgumentList @(
            '-m', 'tests.uat.knowledge_rebuild_measure_prepare', 'startup-input',
            '--repository', $repository, '--run-dir', (Split-Path -Parent $buildFull),
            '--output', $manifestFull) -WorkingDirectory $runtimeRoot -WindowStyle Hidden -Wait -PassThru `
            -Environment @{ LLM_API_KEY = '' }
        if ($preparation.ExitCode -ne 0 -or -not (Test-Path -LiteralPath $manifestFull -PathType Leaf)) {
            throw 'knowledge.measure.startup_input_invalid'
        }
    } catch {
        $metadataAttempts = 0
        $attemptPath = Join-Path $runRoot 'startup-metadata-attempts.jsonl'
        if (Test-Path -LiteralPath $attemptPath -PathType Leaf) {
            $attemptLines = @(Get-Content -LiteralPath $attemptPath -Encoding UTF8)
            $metadataAttempts = if ($attemptLines.Count -in @(1, 2)) { $attemptLines.Count } else { $null }
            for ($i = 0; $i -lt $attemptLines.Count; $i++) {
                if ($attemptLines[$i] -cne ('{"attempt":' + ($i + 1) + '}')) { $metadataAttempts = $null }
            }
        }
        $failure = [Text.Encoding]::UTF8.GetBytes((ConvertTo-Json -Compress ([ordered]@{
            schemaVersion = 1; status = 'startup_preflight_failed'; stage = 'startup_input'; exitCode = 1
            startupId = [IO.Path]::GetFileName($runRoot)
            buildAttestationSha256 = (Get-FileHash -LiteralPath $buildFull -Algorithm SHA256).Hash.ToLowerInvariant()
            reason = 'startup_input_invalid'; runtimeKeyRead = $false
            metadataEsHttp = $metadataAttempts
            modelHttp = 0; typedSearchEsHttp = 0; embeddingHttp = 0; rerankHttp = 0
            ownedProcessesStopped = $true
        })) + "`n")
        $stream = [IO.FileStream]::new((Join-Path $runRoot 'startup-result.json'),
            [IO.FileMode]::CreateNew, [IO.FileAccess]::Write, [IO.FileShare]::None)
        try { $stream.Write($failure, 0, $failure.Length); $stream.Flush($true) } finally { $stream.Dispose() }
        throw
    }
    $ExpectedManifestSha256 = (Get-FileHash -LiteralPath $manifestFull -Algorithm SHA256).Hash.ToLowerInvariant()
} else {
    $manifestFull = [IO.Path]::GetFullPath($ManifestPath)
    $authorizationFull = [IO.Path]::GetFullPath($AuthorizationPath)
}
try {
if ($ExpectedManifestSha256 -notmatch '^[0-9a-f]{64}$' -or
    (Get-FileHash -LiteralPath $manifestFull -Algorithm SHA256).Hash.ToLowerInvariant() -ne $ExpectedManifestSha256) {
    throw 'knowledge.measure.manifest_hash_invalid'
}
$manifest = Get-Content -LiteralPath $manifestFull -Raw -Encoding UTF8 | ConvertFrom-Json
if ($startup) {
    if ($manifest.schemaVersion -ne 1 -or $manifest.status -cne 'startup_input' -or
        $manifest.branch -cne 'codex_0915' -or $manifest.maximumStartupMetadataEsHttp -ne 48 -or
        $manifest.bindingMetadataEsHttp -ne 2 -or $manifest.subject.userId -cne 'viewer_t' -or
        $manifest.subject.role -cne 'VIEWER') {
        throw 'knowledge.measure.startup_binding_invalid'
    }
} elseif ($manifest.schemaVersion -ne 1 -or $manifest.branch -ne 'codex_0915' -or
    $manifest.model -ne 'deepseek-flash' -or $manifest.springBaseUrl -ne 'http://127.0.0.1:19202' -or
    $manifest.runtimePort -ne 19203 -or $manifest.budgets.model -ne 36 -or
    $manifest.budgets.search -ne 48 -or $manifest.budgets.embedding -ne 12 -or
    $manifest.budgets.rerank -ne 24 -or $manifest.budgets.cases -ne 12 -or
    $manifest.subject.userId -cne 'viewer_t' -or $manifest.subject.role -cne 'VIEWER') {
    throw 'knowledge.measure.manifest_binding_invalid'
}
$runId = if ($startup) { [string]$manifest.startupId } else { [string]$manifest.runId }
if ($runId -cnotmatch '^[a-z0-9][a-z0-9-]{5,100}$') {
    throw 'knowledge.measure.run_id_invalid'
}
$outputParent = [IO.Path]::GetFullPath((Join-Path $runtimeRoot 'tests\uat\results'))
$outputRoot = if ($startup) { $null } else { [IO.Path]::GetFullPath((Join-Path $outputParent $runId)) }
$reviewParent = Join-Path $repository '.tmp\knowledge-measure-review'
$reviewParent = [IO.Path]::GetFullPath($reviewParent)
$reviewRoot = if ($startup) { $null } else { [IO.Path]::GetFullPath((Join-Path $reviewParent $runId)) }
if (-not $startup -and ([IO.Path]::GetDirectoryName($outputRoot) -ne $outputParent -or
    [IO.Path]::GetDirectoryName($reviewRoot) -ne $reviewParent)) {
    throw 'knowledge.measure.run_path_invalid'
}
$runtimeEnvProperties = @($manifest.runtimeEnv.PSObject.Properties)
if ($null -eq $manifest.runtimeEnv -or $manifest.runtimeEnv -isnot [pscustomobject] -or
    $runtimeEnvProperties.Count -lt 1) {
    throw 'knowledge.measure.runtime_env_invalid'
}
foreach ($property in $runtimeEnvProperties) {
    if (($property.Name -notmatch '^(AGENT_KNOWLEDGE_|AGENT_MODEL_|AGENT_RUNTIME_)' -and
         $property.Name -notin @('AGENT_EMPLOYEE_BASE_URL', 'AGENT_TRANSACTION_BASE_URL')) -or
        $property.Name -match '(KEY|TOKEN|SECRET|JWT)' -or
        $property.Value -isnot [string]) {
        throw 'knowledge.measure.runtime_env_invalid'
    }
}
if (-not $startup -and (Test-Path -LiteralPath $outputRoot)) {
    throw 'knowledge.measure.run_already_exists'
}
if (-not $startup -and (Test-Path -LiteralPath $reviewRoot)) {
    throw 'knowledge.measure.review_already_exists'
}

$ownedPorts = @(18090, 19201, 19202, 19203, 19313)
$dependencyPorts = @(9200, 8908, 8909)
foreach ($port in $ownedPorts) {
    if (Get-NetTCPConnection -State Listen -LocalPort $port -ErrorAction SilentlyContinue) {
        throw "knowledge.measure.owned_port_occupied:$port"
    }
}
foreach ($port in $dependencyPorts) {
    if (-not (Get-NetTCPConnection -State Listen -LocalPort $port -ErrorAction SilentlyContinue)) {
        throw "knowledge.measure.dependency_missing:$port"
    }
}
} catch {
    if ($startup -and (Test-Path -LiteralPath $runRoot -PathType Container) -and
        -not (Test-Path -LiteralPath (Join-Path $runRoot 'startup-result.json'))) {
        $failure = [Text.Encoding]::UTF8.GetBytes((ConvertTo-Json -Compress ([ordered]@{
            schemaVersion = 1; status = 'startup_preflight_failed'; stage = 'startup_static'; exitCode = 1
            reason = 'startup_static_invalid'; runtimeKeyRead = $false
            metadataEsHttp = 2; modelHttp = 0; typedSearchEsHttp = 0
            embeddingHttp = 0; rerankHttp = 0; ownedProcessesStopped = $true
        })) + "`n")
        $stream = [IO.FileStream]::new((Join-Path $runRoot 'startup-result.json'),
            [IO.FileMode]::CreateNew, [IO.FileAccess]::Write, [IO.FileShare]::None)
        try { $stream.Write($failure, 0, $failure.Length); $stream.Flush($true) } finally { $stream.Dispose() }
    }
    throw
}

$environmentSnapshot = @{}
$frozenNames = @(Get-ChildItem Env: | Where-Object {
    $_.Name -match '^(AGENT_|AUTH_|ES_QUERY_|SPRING_|EUREKA_|MANAGEMENT_|SERVER_|COMMON_)' -or
    $_.Name -in @('JAVA_TOOL_OPTIONS', 'JDK_JAVA_OPTIONS', '_JAVA_OPTIONS', 'JAVA_OPTS')
} | ForEach-Object { $_.Name })
foreach ($name in ($frozenNames + @('COMMON_SECURITY_JWT_HMAC_KEY_ACTIVE',
            'KNOWLEDGE_MEASURE_USER_JWT', 'KNOWLEDGE_MEASURE_LAUNCHER_ATTESTED',
            'KNOWLEDGE_MEASURE_OWNED_ES_PID', 'KNOWLEDGE_MEASURE_OWNED_AGENT_PID',
            'KNOWLEDGE_MEASURE_OWNED_PROXY_PID',
            'PYTHONPATH') | Select-Object -Unique)) {
    $environmentSnapshot[$name] = [Environment]::GetEnvironmentVariable($name, 'Process')
}
foreach ($name in $frozenNames) {
    [Environment]::SetEnvironmentVariable($name, $null, 'Process')
}
foreach ($property in $runtimeEnvProperties) {
    [Environment]::SetEnvironmentVariable($property.Name, [string]$property.Value, 'Process')
}
$env:PYTHONPATH = 'src'
$runArgs = if ($startup) { @() } else { @('--repository', $repository, '--manifest', $manifestFull,
             '--authorization', $authorizationFull, '--output', $outputRoot) }

$snapshotPath = Join-Path $runRoot 'snapshot-attestation.json'
$postSnapshotPath = Join-Path $runRoot 'snapshot-post-attestation.json'
$authOut = Join-Path $runRoot 'auth.out.log'
$authErr = Join-Path $runRoot 'auth.err.log'
$esOut = Join-Path $runRoot 'es.out.log'
$esErr = Join-Path $runRoot 'es.err.log'
$agentOut = Join-Path $runRoot 'agent.out.log'
$agentErr = Join-Path $runRoot 'agent.err.log'
$proxyOut = Join-Path $runRoot 'proxy.out.log'
$proxyErr = Join-Path $runRoot 'proxy.err.log'
$runtimeOut = Join-Path $runRoot 'runtime.out.log'
$runtimeErr = Join-Path $runRoot 'runtime.err.log'
$runtimeViolation = Join-Path $runRoot 'runtime-outbound-violation.marker'
$runtimeStopMarker = Join-Path $runRoot 'runtime-stop.marker'
$runtimeClosedMarker = Join-Path $runRoot 'runtime-closed.marker'
$authProcess = $null
$esProcess = $null
$agentProcess = $null
$proxyProcess = $null
$runtimeProcess = $null
$secret = $null
$userToken = $null
$apiKey = $null
$leakDetected = $false
$runnerExit = $null
$proxyCounts = $null
$launcherFailure = $null
$runRootCreated = $false
$staticPreflightPassed = $false

function Wait-Ready([string]$Uri, [Diagnostics.Process]$Process, [int]$MaximumAttempts = 120) {
    $port = ([uri]$Uri).Port
    for ($attempt = 0; $attempt -lt $MaximumAttempts; $attempt++) {
        if ($Process.HasExited) { throw 'knowledge.measure.owned_process_exited' }
        $ready = $false
        try {
            $response = Invoke-WebRequest -Uri $Uri -Method Get -TimeoutSec 2 -SkipHttpErrorCheck
            $ready = $response.StatusCode -eq 200
        } catch {}
        if ($ready) {
            $listeners = @(Get-NetTCPConnection -State Listen -LocalPort $port -ErrorAction SilentlyContinue)
            if ($listeners.Count -eq 0 -or
                @($listeners | Where-Object { $_.OwningProcess -ne $Process.Id }).Count -gt 0) {
                throw 'knowledge.measure.port_owner_mismatch'
            }
            return
        }
        Start-Sleep -Milliseconds 500
    }
    throw 'knowledge.measure.readiness_timeout'
}

function Wait-OwnedPort([int]$Port, [Diagnostics.Process]$Process) {
    for ($attempt = 0; $attempt -lt 120; $attempt++) {
        if ($Process.HasExited) { throw 'knowledge.measure.owned_process_exited' }
        $listener = Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue
        if ($listener) {
            if (@($listener | Where-Object { $_.OwningProcess -ne $Process.Id }).Count -gt 0) {
                throw 'knowledge.measure.port_owner_mismatch'
            }
            return
        }
        Start-Sleep -Milliseconds 500
    }
    throw 'knowledge.measure.readiness_timeout'
}

function Get-ProxyCounts([switch]$AllowViolations) {
    if ($null -eq $proxyProcess -or $proxyProcess.HasExited) {
        throw 'knowledge.measure.proxy_exited'
    }
    Wait-OwnedPort 19313 $proxyProcess
    $response = Invoke-WebRequest -Uri 'http://127.0.0.1:19313/__counts' -Method Get `
        -TimeoutSec 2 -SkipHttpErrorCheck
    if ($response.StatusCode -ne 200 -or $response.RawContentLength -gt 4096) {
        throw 'knowledge.measure.proxy_counts_invalid'
    }
    $value = $response.Content | ConvertFrom-Json
    if ($null -eq $value -or @($value.PSObject.Properties).Count -ne 8) {
        throw 'knowledge.measure.proxy_counts_invalid'
    }
    foreach ($name in @('metadataEsHttp', 'searchEsHttp', 'proxyViolations',
            'healthEsHttp', 'aliasEsHttp', 'settingsEsHttp', 'mappingEsHttp', 'definitionEsHttp')) {
        if ($value.$name -isnot [long] -or $value.$name -lt 0) {
            throw 'knowledge.measure.proxy_counts_invalid'
        }
    }
    if ($value.metadataEsHttp -ne ($value.healthEsHttp + $value.aliasEsHttp +
            $value.settingsEsHttp + $value.mappingEsHttp + $value.definitionEsHttp) -or
        (-not $AllowViolations -and $value.proxyViolations -ne 0)) {
        throw 'knowledge.measure.proxy_counts_invalid'
    }
    return $value
}

function Get-LocalPassword([string]$User) {
    $path = Join-Path $repository 'auth-service\src\main\resources\auth-users.yml'
    $value = Get-Content -LiteralPath $path -Raw -Encoding UTF8
    $match = [regex]::Match($value, "(?ms)^\s{4}${User}:\s*\r?\n\s+password:\s*([^\r\n]+)")
    if (-not $match.Success) { throw 'knowledge.measure.auth_fixture_missing' }
    $stored = $match.Groups[1].Value.Trim().Trim('"').Trim("'")
    if (-not $stored.StartsWith('{noop}')) { throw 'knowledge.measure.auth_fixture_not_local' }
    return $stored.Substring(6)
}

function Get-LoginToken([string]$User) {
    $session = [Microsoft.PowerShell.Commands.WebRequestSession]::new()
    $body = @{ userId = $User; password = (Get-LocalPassword $User) } | ConvertTo-Json -Compress
    $response = Invoke-WebRequest -Uri 'http://127.0.0.1:18090/login' -Method Post `
        -ContentType 'application/json' -Body $body -WebSession $session -TimeoutSec 5 -SkipHttpErrorCheck
    if ($response.StatusCode -ne 200) { throw 'knowledge.measure.login_failed' }
    $cookie = $session.Cookies.GetCookies('http://127.0.0.1:18090')['AUTH_TOKEN']
    if ($null -eq $cookie -or [string]::IsNullOrWhiteSpace($cookie.Value)) {
        throw 'knowledge.measure.token_missing'
    }
    try {
        $segments = $cookie.Value.Split('.')
        if ($segments.Length -ne 3) { throw 'invalid_jwt' }
        $payload = $segments[1].Replace('-', '+').Replace('_', '/')
        $payload = $payload.PadRight($payload.Length + ((4 - $payload.Length % 4) % 4), '=')
        $claims = [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($payload)) |
            ConvertFrom-Json -AsHashtable
        if ($claims.sub -isnot [string] -or $claims.sub -cne $User -or
            $claims.token_type -isnot [string] -or $claims.token_type -cne 'user' -or
            $claims.role -isnot [array] -or $claims.role.Count -ne 1 -or
            $claims.role[0] -isnot [string] -or $claims.role[0] -cne 'VIEWER') {
            throw 'unexpected_role'
        }
    } catch {
        throw 'knowledge.measure.token_subject_or_role_invalid'
    }
    return $cookie.Value
}

function Test-LogLeak {
    $logs = (Get-Content -LiteralPath $authOut, $authErr, $esOut, $esErr, $agentOut, $agentErr, `
        $proxyOut, $proxyErr, $runtimeOut, $runtimeErr `
        -Raw -ErrorAction SilentlyContinue) -join "`n"
    foreach ($item in @($secret, $userToken, $apiKey)) {
        if ($item -and $logs.Contains([string]$item)) { return $true }
    }
    foreach ($case in $manifest.cases) {
        if ($case.question -and $logs.Contains([string]$case.question)) { return $true }
    }
    return $false
}

function Test-EvidenceLeak {
    if ($startup) { return $false }
    $reviewFile = Join-Path $reviewRoot 'public-review.jsonl'
    $evidenceFiles = @(Get-ChildItem -LiteralPath $outputRoot -File -ErrorAction SilentlyContinue | Select-Object -ExpandProperty FullName)
    if (Test-Path -LiteralPath $reviewFile) { $evidenceFiles += $reviewFile }
    foreach ($file in $evidenceFiles) {
        $body = Get-Content -LiteralPath $file -Raw -Encoding UTF8
        foreach ($item in @($secret, $userToken, $apiKey)) {
            if ($item -and $body.Contains([string]$item)) { return $true }
        }
        if ($body -match '(?i)LLM_API_KEY|COMMON_SECURITY_JWT_HMAC_KEY_ACTIVE|Bearer\s+eyJ') { return $true }
    }
    return $false
}

function Write-ExclusiveJson([string]$Path, [object]$Value) {
    $bytes = [Text.Encoding]::UTF8.GetBytes((ConvertTo-Json -InputObject $Value -Depth 16 -Compress) + "`n")
    $stream = [IO.FileStream]::new($Path, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write, [IO.FileShare]::None)
    try { $stream.Write($bytes, 0, $bytes.Length); $stream.Flush($true) } finally { $stream.Dispose() }
}

function Assert-FrozenConfig {
    $prefix = 'config-service/src/main/resources/config/'
    $expected = if ($startup) { @($manifest.configSha256.PSObject.Properties) } else {
        @($manifest.assetSha256.PSObject.Properties | Where-Object { $_.Name.StartsWith($prefix) })
    }
    $configRoot = [IO.Path]::GetFullPath((Join-Path $repository $prefix))
    $actual = @(Get-ChildItem -LiteralPath $configRoot -File -Recurse |
        Where-Object { $_.Extension.ToLowerInvariant() -in @('.yml', '.yaml', '.properties') })
    if ($expected.Count -lt 1 -or $expected.Count -gt 64 -or $actual.Count -ne $expected.Count) {
        throw 'knowledge.measure.config_hash_drift'
    }
    foreach ($file in $actual) {
        $relative = [IO.Path]::GetRelativePath($repository, $file.FullName) -replace '\\', '/'
        $entry = @($expected | Where-Object { $_.Name -ceq $relative })
        if ($file.LinkType -or $entry.Count -ne 1 -or $entry[0].Value -cnotmatch '^[0-9a-f]{64}$' -or
            (Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash.ToLowerInvariant() -cne $entry[0].Value) {
            throw 'knowledge.measure.config_hash_drift'
        }
    }
}

function Assert-FrozenAssets {
    $expected = @($manifest.assetSha256.PSObject.Properties)
    if ($startup) {
        $expected += @($manifest.jarSha256.PSObject.Properties)
        $expected += @($manifest.dependencyJarSha256.PSObject.Properties)
    }
    $expected += [pscustomobject]@{ Name = [string]$manifest.buildAttestationPath; Value = [string]$manifest.buildAttestationSha256 }
    if ($expected.Count -lt 1 -or $expected.Count -gt 128) { throw 'knowledge.measure.asset_hash_drift' }
    $boundary = $repository.TrimEnd('\', '/') + [IO.Path]::DirectorySeparatorChar
    foreach ($entry in $expected) {
        $path = [IO.Path]::GetFullPath((Join-Path $repository $entry.Name))
        if (-not $path.StartsWith($boundary, [StringComparison]::OrdinalIgnoreCase) -or
            $entry.Value -cnotmatch '^[0-9a-f]{64}$' -or
            -not (Test-Path -LiteralPath $path -PathType Leaf) -or
            (Get-Item -LiteralPath $path).LinkType -or
            (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant() -cne $entry.Value) {
            throw 'knowledge.measure.asset_hash_drift'
        }
    }
    $expectedHead = if ($startup) { [string]$manifest.head } else { [string]$manifest.frozenHead }
    $actualHead = (& git -C $repository rev-parse HEAD | Out-String).Trim()
    if ($LASTEXITCODE -ne 0 -or $actualHead -cne $expectedHead) { throw 'knowledge.measure.git_binding_drift' }
    $actualBranch = (& git -C $repository branch --show-current | Out-String).Trim()
    if ($LASTEXITCODE -ne 0 -or $actualBranch -cne 'codex_0915') { throw 'knowledge.measure.git_binding_drift' }
    $trackedChanges = (& git -C $repository status --porcelain --untracked-files=no | Out-String).Trim()
    if ($LASTEXITCODE -ne 0 -or $trackedChanges) { throw 'knowledge.measure.git_binding_drift' }
}

function Stop-OwnedProcesses {
    foreach ($process in @($runtimeProcess, $agentProcess, $esProcess, $authProcess, $proxyProcess)) {
        if ($null -ne $process -and -not $process.HasExited) {
            Stop-Process -Id $process.Id -ErrorAction SilentlyContinue
            if (-not $process.WaitForExit(5000)) { Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue }
        }
    }
}

try {
    if (-not $startup) { New-Item -ItemType Directory -Path $runRoot | Out-Null }
    $runRootCreated = $true
    if (-not $startup) {
        Push-Location $runtimeRoot
        try {
            & $runtimePython -m tests.uat.knowledge_rebuild_measure_runner @runArgs --phase static
            if ($LASTEXITCODE -ne 0) { throw 'knowledge.measure.static_preflight_failed' }
            $staticPreflightPassed = $true
        } finally { Pop-Location }
    }

    Push-Location (Join-Path $repository 'knowledge-corpus-tools')
    try {
        & $corpusPython -c 'import bs4, httpx, knowledge_corpus_tools.b_id_mapping_v1'
        if ($LASTEXITCODE -ne 0) { throw 'knowledge.measure.corpus_environment_invalid' }
    } finally { Pop-Location }

    $keyBytes = [Security.Cryptography.RandomNumberGenerator]::GetBytes(48)
    $secret = [Convert]::ToBase64String($keyBytes)
    [Array]::Clear($keyBytes, 0, $keyBytes.Length)
    $env:COMMON_SECURITY_JWT_HMAC_KEY_ACTIVE = $secret
    $binding = $manifest.indexBindings.'tax.policy'
    if ($null -eq $binding -or $manifest.indexBindings.'tax.law'.indexUuid -cne $binding.indexUuid -or
        $manifest.indexBindings.'tax.law'.indexName -cne $binding.indexName) {
        throw 'knowledge.measure.profile_binding_invalid'
    }
    $javaExe = Join-Path ([string]$env:JAVA_HOME) 'bin\java.exe'
    if (-not (Test-Path -LiteralPath $javaExe -PathType Leaf)) {
        throw 'knowledge.measure.java25_missing'
    }
    $javaVersion = (& $javaExe -version 2>&1 | Out-String)
    if ($LASTEXITCODE -ne 0 -or $javaVersion -notmatch '(?:openjdk|java) version "25(?:\.|\")') {
        throw 'knowledge.measure.java25_invalid'
    }
    Assert-FrozenConfig
    Assert-FrozenAssets
    $configPath = (Join-Path $repository 'config-service\src\main\resources\config') -replace '\\', '/'
    $commonArgs = @('--spring.cloud.config.enabled=false', '--eureka.client.enabled=false',
        "--spring.config.additional-location=optional:file:$configPath/",
        '--common.security.secrets.source-order[0]=environment',
        '--common.security.secrets.allow-config-values=false', '--common.security.secrets.fail-fast=true',
        '--common.security.secrets.jwt.active-key-id=ACTIVE',
        '--common.security.secrets.jwt.keys.ACTIVE.env=COMMON_SECURITY_JWT_HMAC_KEY_ACTIVE',
        '--common.security.secrets.jwt.keys.ACTIVE.value=')
    $childEnv = @{ LLM_API_KEY = '' }
    $esChildEnv = @{
        LLM_API_KEY = ''
        AGENT_KNOWLEDGE_READ_ALIAS = [string]$binding.readAlias
        AGENT_KNOWLEDGE_EXPECTED_INDEX_NAME = [string]$binding.indexName
        AGENT_KNOWLEDGE_EXPECTED_INDEX_UUID = [string]$binding.indexUuid
        AGENT_KNOWLEDGE_MAPPING_VERSION = [string]$binding.mappingVersion
        AGENT_KNOWLEDGE_POLICY_SNAPSHOT_ID = [string]$manifest.indexBindings.'tax.policy'.snapshotId
        AGENT_KNOWLEDGE_LAW_SNAPSHOT_ID = [string]$manifest.indexBindings.'tax.law'.snapshotId
    }
    $authJar = Join-Path $repository 'auth-service\target\auth-service-0.0.1-SNAPSHOT.jar'
    $esJar = Join-Path $repository 'es-query-service\target\es-query-service-0.0.1-SNAPSHOT.jar'
    $agentJar = Join-Path $repository 'agent-service\target\agent-service-0.0.1-SNAPSHOT.jar'
    $proxyMetadataLimit = if ($startup) { 46 } else { 72 }
    $proxySearchLimit = if ($startup) { 0 } else { 48 }
    $proxyProcess = Start-Process -FilePath $runtimePython -ArgumentList @(
        '-m', 'tests.uat.knowledge_rebuild_measure_startup', 'proxy',
        '--index-name', [string]$binding.indexName, '--read-alias', [string]$binding.readAlias,
        '--port', '19313', '--metadata-limit', [string]$proxyMetadataLimit,
        '--search-limit', [string]$proxySearchLimit) -WorkingDirectory $runtimeRoot `
        -WindowStyle Hidden -PassThru -Environment @{ LLM_API_KEY = '' } `
        -RedirectStandardOutput $proxyOut -RedirectStandardError $proxyErr
    $startupStage = 'proxy_start'
    Wait-OwnedPort 19313 $proxyProcess
    $authProcess = Start-Process -FilePath $javaExe -ArgumentList (@('-jar', $authJar, '--server.port=18090') + $commonArgs) `
        -WorkingDirectory (Join-Path $repository 'auth-service') -WindowStyle Hidden -PassThru -Environment $childEnv `
        -RedirectStandardOutput $authOut -RedirectStandardError $authErr
    $startupStage = 'auth_ready'
    Wait-Ready 'http://127.0.0.1:18090/public/test' $authProcess
    $esProcess = Start-Process -FilePath $javaExe -ArgumentList (@('-jar', $esJar,
        '--server.port=19201', '--spring.profiles.active=datasource,es,knowledge-live',
        '--management.endpoint.health.probes.enabled=true',
        '--management.endpoint.health.group.knowledge-validation.include=readinessState,elasticsearch',
        '--spring.elasticsearch.uris=http://127.0.0.1:19313') + $commonArgs) `
        -WorkingDirectory (Join-Path $repository 'es-query-service') -WindowStyle Hidden -PassThru -Environment $esChildEnv `
        -RedirectStandardOutput $esOut -RedirectStandardError $esErr
    $startupStage = 'es_ready'
    # This read-only Knowledge run does not exercise the separate MySQL rebuild
    # repository. Keep ES and application readiness mandatory in its own group.
    Wait-OwnedPort 19201 $esProcess
    $esHealthLimit = if ($startup) { 40 } else { 18 }
    Wait-Ready 'http://127.0.0.1:19201/actuator/health/knowledge-validation' $esProcess $esHealthLimit
    $beforeCases = Get-ProxyCounts
    $beforeCasesLimit = if ($startup) { 46 } else { 24 }
    if ($beforeCases.metadataEsHttp -gt $beforeCasesLimit -or $beforeCases.searchEsHttp -ne 0 -or
        $beforeCases.aliasEsHttp -ne 2 -or $beforeCases.settingsEsHttp -ne 2 -or
        $beforeCases.mappingEsHttp -ne 2 -or $beforeCases.definitionEsHttp -ne 0 -or
        $beforeCases.healthEsHttp -lt 1 -or $beforeCases.healthEsHttp -gt $esHealthLimit) {
        throw 'knowledge.measure.startup_es_budget_exhausted'
    }
    $agentProcess = Start-Process -FilePath $javaExe -ArgumentList (@('-jar', $agentJar,
        '--server.port=19202', '--agent.runtime.base-url=http://127.0.0.1:19203',
        '--agent.runtime.contract-version=1', '--agent.inspection.enabled=false') + $commonArgs) `
        -WorkingDirectory (Join-Path $repository 'agent-service') -WindowStyle Hidden -PassThru -Environment $childEnv `
        -RedirectStandardOutput $agentOut -RedirectStandardError $agentErr
    $startupStage = 'agent_ready'
    Wait-OwnedPort 19202 $agentProcess
    Wait-OwnedPort 18090 $authProcess
    $startupStage = 'login'
    $userToken = Get-LoginToken ([string]$manifest.subject.userId)
    Assert-FrozenConfig
    Assert-FrozenAssets
    if ($startup) {
        $startupStage = 'runtime_ready'
        $runtimeProcess = Start-Process -FilePath $runtimePython -ArgumentList @(
            '-m', 'tests.uat.knowledge_rebuild_measure_startup', 'runtime',
            '--startup-input', $manifestFull, '--violation-marker', $runtimeViolation,
            '--expected-sha256', $ExpectedManifestSha256,
            '--stop-marker', $runtimeStopMarker, '--closed-marker', $runtimeClosedMarker) `
            -WorkingDirectory $runtimeRoot -WindowStyle Hidden -PassThru `
            -Environment @{ LLM_API_KEY = '' } `
            -RedirectStandardOutput $runtimeOut -RedirectStandardError $runtimeErr
        Wait-Ready 'http://127.0.0.1:19203/internal/health/ready' $runtimeProcess
        if (Test-Path -LiteralPath $runtimeViolation) {
            throw 'knowledge.measure.startup_outbound_attempted'
        }
        $startupCounts = Get-ProxyCounts
        if ($startupCounts.metadataEsHttp + 2 -gt 48 -or $startupCounts.searchEsHttp -ne 0) {
            throw 'knowledge.measure.startup_es_budget_exhausted'
        }
        $startupStage = 'cleanup'
        [IO.File]::WriteAllText($runtimeStopMarker, "stop`n", [Text.Encoding]::UTF8)
        if (-not $runtimeProcess.WaitForExit(15000) -or
            -not (Test-Path -LiteralPath $runtimeClosedMarker -PathType Leaf)) {
            throw 'knowledge.measure.startup_runtime_close_failed'
        }
        Stop-OwnedProcesses
        if (@($runtimeProcess, $agentProcess, $esProcess, $authProcess, $proxyProcess |
                Where-Object { $null -ne $_ -and -not $_.HasExited }).Count -gt 0) {
            throw 'knowledge.measure.startup_cleanup_failed'
        }
        $leakDetected = Test-LogLeak
        if ($leakDetected) { throw 'knowledge.measure.log_leak' }
        Assert-FrozenConfig
        Assert-FrozenAssets
        Write-ExclusiveJson (Join-Path $runRoot 'startup-result.json') ([ordered]@{
            schemaVersion = 1; status = 'startup_preflight_passed'; startupId = $runId; exitCode = 0
            head = [string]$manifest.head; sourceRunId = [string]$manifest.sourceRunId
            startupInputSha256 = $ExpectedManifestSha256
            buildAttestationSha256 = [string]$manifest.buildAttestationSha256
            metadataEsHttp = [int]($startupCounts.metadataEsHttp + 2)
            healthEsHttp = [int]$startupCounts.healthEsHttp
            profileEsHttp = [int]($startupCounts.aliasEsHttp +
                $startupCounts.settingsEsHttp + $startupCounts.mappingEsHttp)
            typedSearchEsHttp = [int]$startupCounts.searchEsHttp
            modelHttp = 0; embeddingHttp = 0; rerankHttp = 0
            loginRequests = 1; runtimeKeyRead = $false; stage = 'complete'
            ownedProcessesStopped = $true; outboundViolations = 0
        })
        [pscustomobject]@{ status = 'startup_preflight_passed'; evidence = (Join-Path $runRoot 'startup-result.json') }
        return
    }
    # The snapshot attestation expires after 120 seconds. Create it only after
    # the owned services are ready, but still before reading the model key.
    Push-Location (Join-Path $repository 'knowledge-corpus-tools')
    try {
        $env:PYTHONPATH = (Join-Path $repository 'knowledge-corpus-tools\src')
        & $corpusPython (Join-Path $runtimeRoot 'tests\uat\knowledge_rebuild_snapshot_preflight.py') `
            --manifest $manifestFull --manifest-sha256 $ExpectedManifestSha256 --output $snapshotPath
        if ($LASTEXITCODE -ne 0) { throw 'knowledge.measure.snapshot_preflight_failed' }
    } finally { Pop-Location }
    Assert-FrozenConfig
    Assert-FrozenAssets
    $apiKey = [Environment]::GetEnvironmentVariable('LLM_API_KEY', 'Process')
    if ([string]::IsNullOrWhiteSpace($apiKey)) { throw 'knowledge.measure.api_key_missing' }
    $env:KNOWLEDGE_MEASURE_USER_JWT = $userToken
    $env:KNOWLEDGE_MEASURE_LAUNCHER_ATTESTED = $ExpectedManifestSha256
    if (-not (Test-Path -LiteralPath $reviewParent)) {
        New-Item -ItemType Directory -Path $reviewParent | Out-Null
    }
    $env:PYTHONPATH = 'src'
    Wait-OwnedPort 18090 $authProcess
    Wait-OwnedPort 19201 $esProcess
    Wait-OwnedPort 19202 $agentProcess
    Wait-OwnedPort 19313 $proxyProcess
    $env:KNOWLEDGE_MEASURE_OWNED_ES_PID = [string]$esProcess.Id
    $env:KNOWLEDGE_MEASURE_OWNED_AGENT_PID = [string]$agentProcess.Id
    $env:KNOWLEDGE_MEASURE_OWNED_PROXY_PID = [string]$proxyProcess.Id
    Push-Location $runtimeRoot
    try {
        & $runtimePython -m tests.uat.knowledge_rebuild_measure_runner @runArgs `
            --phase run --snapshot-attestation $snapshotPath --review-dir $reviewRoot
        $runnerExit = $LASTEXITCODE
    } finally { Pop-Location }
    $leakDetected = (Test-LogLeak) -or (Test-EvidenceLeak)
    Assert-FrozenConfig
    Assert-FrozenAssets
    if ($leakDetected) { throw 'knowledge.measure.log_leak' }
    if ($runnerExit -ne 0) { throw 'knowledge.measure.runner_failed' }
    $measurementPath = Join-Path $outputRoot 'measurement.json'
    if (-not (Test-Path -LiteralPath $measurementPath)) {
        throw 'knowledge.measure.measurement_missing'
    }
    $measurement = Get-Content -LiteralPath $measurementPath -Raw -Encoding UTF8 | ConvertFrom-Json
    $proxyCounts = Get-ProxyCounts
    if ($measurement.aliasChecks -isnot [long] -or $measurement.aliasChecks -ne 24 -or
        $proxyCounts.metadataEsHttp -gt 72 -or
        $proxyCounts.metadataEsHttp -ne $beforeCases.metadataEsHttp + 2 * $measurement.aliasChecks -or
        $proxyCounts.healthEsHttp -ne $beforeCases.healthEsHttp -or
        $proxyCounts.settingsEsHttp -ne 2 -or $proxyCounts.mappingEsHttp -ne 2 -or
        $proxyCounts.aliasEsHttp -ne 2 + $measurement.aliasChecks -or
        $proxyCounts.definitionEsHttp -ne $measurement.aliasChecks -or
        $proxyCounts.searchEsHttp -gt 48 -or $proxyCounts.searchEsHttp -ne $measurement.counts.search) {
        throw 'knowledge.measure.es_http_budget_or_witness_invalid'
    }
    Push-Location (Join-Path $repository 'knowledge-corpus-tools')
    try {
        $env:PYTHONPATH = (Join-Path $repository 'knowledge-corpus-tools\src')
        & $corpusPython (Join-Path $runtimeRoot 'tests\uat\knowledge_rebuild_snapshot_preflight.py') `
            --manifest $manifestFull --manifest-sha256 $ExpectedManifestSha256 --output $postSnapshotPath
        if ($LASTEXITCODE -ne 0) { throw 'knowledge.measure.snapshot_postflight_failed' }
    } finally { Pop-Location }
    Copy-Item -LiteralPath $snapshotPath -Destination (Join-Path $outputRoot 'snapshot-preflight.json')
    Copy-Item -LiteralPath $postSnapshotPath -Destination (Join-Path $outputRoot 'snapshot-postflight.json')
    Stop-OwnedProcesses
    $env:PYTHONPATH = 'src'
    Push-Location $runtimeRoot
    try {
        & $runtimePython -m tests.uat.knowledge_rebuild_measure_runner @runArgs --phase postflight
        if ($LASTEXITCODE -ne 0) { throw 'knowledge.measure.static_postflight_failed' }
    } finally { Pop-Location }
    $leakDetected = (Test-LogLeak) -or (Test-EvidenceLeak)
    if ($leakDetected) { throw 'knowledge.measure.log_leak' }
    $measurement = Get-Content -LiteralPath $measurementPath -Raw -Encoding UTF8 | ConvertFrom-Json
    if ($measurement.status -ne 'completed_pending_postflight' -or $measurement.caseCount -ne 12) {
        throw 'knowledge.measure.measurement_incomplete'
    }
    $qualityState = if ($measurement.publicStatusMismatches -eq 0) { 'not_assessed' } else { 'observed_below_frozen_expectation' }
    Write-ExclusiveJson (Join-Path $outputRoot 'result.json') ([ordered]@{
        schemaVersion = 1; runId = $runId; status = 'measured_pending_human_rubric'
        qualityStatus = $qualityState; caseCount = 12; counts = $measurement.counts
        publicStatusMismatches = $measurement.publicStatusMismatches
        measurementSha256 = (Get-FileHash -LiteralPath $measurementPath -Algorithm SHA256).Hash.ToLowerInvariant()
        snapshotPreflightSha256 = (Get-FileHash -LiteralPath (Join-Path $outputRoot 'snapshot-preflight.json') -Algorithm SHA256).Hash.ToLowerInvariant()
        snapshotPostflightSha256 = (Get-FileHash -LiteralPath (Join-Path $outputRoot 'snapshot-postflight.json') -Algorithm SHA256).Hash.ToLowerInvariant()
        javaEsHttp = [ordered]@{ metadata = [int]$proxyCounts.metadataEsHttp
            typedSearch = [int]$proxyCounts.searchEsHttp
            completedAliasChecks = [int]$measurement.aliasChecks
            health = [int]$proxyCounts.healthEsHttp; alias = [int]$proxyCounts.aliasEsHttp
            indexDefinition = [int]$proxyCounts.definitionEsHttp
            settings = [int]$proxyCounts.settingsEsHttp; mapping = [int]$proxyCounts.mappingEsHttp
            proxyViolations = [int]$proxyCounts.proxyViolations }
        humanRubric = 'not_assessed'
    })
    [pscustomobject]@{ status = 'measured_pending_human_rubric'; runId = $runId;
        output = $outputRoot; review = (Join-Path $reviewRoot 'public-review.jsonl') }
} catch {
    $launcherFailure = 'launcher_validation_or_runtime_failure'
    if ($leakDetected) { $launcherFailure = 'sensitive_output_detected' }
    $partialCounts = $null
    try { if ($null -ne $proxyProcess -and -not $proxyProcess.HasExited) { $partialCounts = Get-ProxyCounts -AllowViolations } } catch {}
    if ($null -eq $partialCounts -and $null -ne $proxyCounts) { $partialCounts = $proxyCounts }
    if ($startup) {
        Stop-OwnedProcesses
        if (-not (Test-Path -LiteralPath (Join-Path $runRoot 'startup-result.json'))) {
            Write-ExclusiveJson (Join-Path $runRoot 'startup-result.json') ([ordered]@{
                schemaVersion = 1; status = 'startup_preflight_failed'; startupId = $runId; exitCode = 1
                reason = $launcherFailure; stage = $startupStage
                startupInputSha256 = $ExpectedManifestSha256
                metadataEsHttp = if ($null -eq $partialCounts) { $null } else { [int]($partialCounts.metadataEsHttp + 2) }
                typedSearchEsHttp = if ($null -eq $partialCounts) { $null } else { [int]$partialCounts.searchEsHttp }
                proxyViolations = if ($null -eq $partialCounts) { $null } else { [int]$partialCounts.proxyViolations }
                modelHttp = 0; embeddingHttp = 0; rerankHttp = 0; runtimeKeyRead = $false
                ownedProcessesStopped = @($runtimeProcess, $agentProcess, $esProcess, $authProcess, $proxyProcess |
                    Where-Object { $null -ne $_ -and -not $_.HasExited }).Count -eq 0
            })
        }
    } elseif ($staticPreflightPassed -and -not (Test-Path -LiteralPath $outputRoot)) {
        # The ledger may fail before creating outputRoot. Preserve a finite
        # terminal beside the already validated freeze, never alter its files.
        Write-ExclusiveJson (Join-Path (Split-Path -Parent $manifestFull) 'launcher-failure.json') ([ordered]@{
            schemaVersion = 1; runId = $runId; status = 'invalid_run'; reason = $launcherFailure
            evidenceLocation = 'frozen_asset_directory'; authorizationConsumption = 'not_observed'
            callCounts = $null
        })
    }
    if (-not $startup -and $staticPreflightPassed) {
        $witnessParent = if (Test-Path -LiteralPath $outputRoot -PathType Container) {
            $outputRoot
        } else {
            Split-Path -Parent $manifestFull
        }
        Write-ExclusiveJson (Join-Path $witnessParent 'es-proxy-witness.json') ([ordered]@{
            schemaVersion = 1; runId = $runId; status = 'failed_observation'
            metadataEsHttp = if ($null -eq $partialCounts) { $null } else { [int]$partialCounts.metadataEsHttp }
            typedSearchEsHttp = if ($null -eq $partialCounts) { $null } else { [int]$partialCounts.searchEsHttp }
            healthEsHttp = if ($null -eq $partialCounts) { $null } else { [int]$partialCounts.healthEsHttp }
            aliasEsHttp = if ($null -eq $partialCounts) { $null } else { [int]$partialCounts.aliasEsHttp }
            indexDefinitionEsHttp = if ($null -eq $partialCounts) { $null } else { [int]$partialCounts.definitionEsHttp }
            proxyViolations = if ($null -eq $partialCounts) { $null } else { [int]$partialCounts.proxyViolations }
        })
    }
    if (-not $startup -and (Test-Path -LiteralPath $outputRoot -PathType Container) -and
        -not (Test-Path -LiteralPath (Join-Path $outputRoot 'result.json')) -and
        -not (Test-Path -LiteralPath (Join-Path $outputRoot 'failure.json')) -and
        -not (Test-Path -LiteralPath (Join-Path $outputRoot 'launcher-failure.json'))) {
        Write-ExclusiveJson (Join-Path $outputRoot 'launcher-failure.json') ([ordered]@{
            schemaVersion = 1; runId = $runId; status = 'invalid_run'; reason = $launcherFailure
            consumed = (Test-Path -LiteralPath (Join-Path $outputRoot 'authorization.consumed.json'))
        })
    }
    throw
} finally {
    Stop-OwnedProcesses
    if (-not $leakDetected) { $leakDetected = (Test-LogLeak) -or (Test-EvidenceLeak) }
    $secret = $null; $userToken = $null; $apiKey = $null
    foreach ($name in $environmentSnapshot.Keys) {
        [Environment]::SetEnvironmentVariable($name, $environmentSnapshot[$name], 'Process')
    }
    foreach ($property in $manifest.runtimeEnv.PSObject.Properties) {
        if (-not $environmentSnapshot.ContainsKey($property.Name)) {
            [Environment]::SetEnvironmentVariable($property.Name, $null, 'Process')
        }
    }
    foreach ($name in @('AGENT_KNOWLEDGE_READ_ALIAS', 'AGENT_KNOWLEDGE_EXPECTED_INDEX_NAME',
        'AGENT_KNOWLEDGE_EXPECTED_INDEX_UUID', 'AGENT_KNOWLEDGE_MAPPING_VERSION',
        'AGENT_KNOWLEDGE_POLICY_SNAPSHOT_ID', 'AGENT_KNOWLEDGE_LAW_SNAPSHOT_ID')) {
        if (-not $environmentSnapshot.ContainsKey($name)) {
            [Environment]::SetEnvironmentVariable($name, $null, 'Process')
        }
    }
    $resolvedRunRoot = [IO.Path]::GetFullPath($runRoot)
    if ($runRootCreated -and -not $startup -and
        [IO.Path]::GetFileName($resolvedRunRoot) -match '^codex-knowledge-measure-[0-9a-f]{32}$' -and
        $resolvedRunRoot.StartsWith(($tempBase.TrimEnd('\') + '\'), [StringComparison]::OrdinalIgnoreCase) -and
        (Test-Path -LiteralPath $resolvedRunRoot)) {
        Remove-Item -LiteralPath $resolvedRunRoot -Recurse -Force
    }
    if ($startup -and $runRootCreated -and
        [IO.Path]::GetFileName($resolvedRunRoot) -match '^codex-knowledge-measure-startup-[0-9a-f]{32}$' -and
        $resolvedRunRoot.StartsWith(($tempBase.TrimEnd('\') + '\'), [StringComparison]::OrdinalIgnoreCase)) {
        foreach ($log in @($authOut, $authErr, $esOut, $esErr, $agentOut, $agentErr,
                           $proxyOut, $proxyErr, $runtimeOut, $runtimeErr)) {
            if (Test-Path -LiteralPath $log -PathType Leaf) { Remove-Item -LiteralPath $log -Force }
        }
    }
    if ($leakDetected) { throw 'knowledge.measure.log_leak' }
}
