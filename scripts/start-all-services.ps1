param(
  [switch]$SkipInstall,
  [switch]$ReuseExisting,
  [int]$StartupDelaySeconds = 6,
  [int]$PortTimeoutSeconds = 90,
  [int]$EurekaTimeoutSeconds = 180
)

$ErrorActionPreference = 'Stop'
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$ServiceCenter = Join-Path $RepoRoot 'serviceCenter'
$RuntimeRoot = Join-Path $RepoRoot 'agent-runtime'
$LogRoot = Join-Path $RepoRoot '.tmp\service-logs'
$Maven = Join-Path $ServiceCenter 'mvnw.cmd'
$RuntimePython = Join-Path $RuntimeRoot '.venv\Scripts\python.exe'

$JavaServices = @(
  @{ Name = 'eureka-service'; Port = 8761; WaitBeforeNext = 8 },
  @{ Name = 'config-service'; Port = 9888; WaitBeforeNext = 8 },
  @{ Name = 'auth-service'; Port = 8090 },
  @{ Name = 'employee-service'; Port = 9210 },
  @{ Name = 'es-query-service'; Port = 9201 },
  @{ Name = 'workflow-service'; Port = 9100 },
  @{ Name = 'mq-procedure-service'; Port = 8182 },
  @{ Name = 'mq-consumer-service'; Port = 8183 },
  @{ Name = 'document-generation-adapter'; Port = 9240 },
  @{ Name = 'agent-service'; Port = 9220 },
  @{ Name = 'm-service-1'; Port = 8180 },
  @{ Name = 'm-service-2'; Port = 8081 },
  @{ Name = 'openfeign-service'; Port = 9000 },
  @{ Name = 'gateway-service'; Port = 8888 }
)

$RuntimeService = @{ Name = 'agent-runtime'; Port = 9230 }
$AllPorts = @($JavaServices | ForEach-Object { $_.Port }) + $RuntimeService.Port

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

function Test-PortOpen {
  param([Parameter(Mandatory)] [int]$Port)
  $connection = Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue
  return $null -ne $connection
}

function Wait-Port {
  param(
    [Parameter(Mandatory)] [string]$ServiceName,
    [Parameter(Mandatory)] [int]$Port,
    [Parameter(Mandatory)] [int]$TimeoutSeconds
  )

  $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
  while ((Get-Date) -lt $deadline) {
    if (Test-PortOpen -Port $Port) {
      Write-Host "READY port $Port $ServiceName"
      return
    }
    Start-Sleep -Seconds 2
  }
  throw "service did not listen on port $Port within $TimeoutSeconds seconds: $ServiceName"
}

function Assert-PortsFree {
  param([Parameter(Mandatory)] [int[]]$Ports)
  $used = @(foreach ($connection in Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue |
        Where-Object { $_.LocalPort -in $Ports } |
        Sort-Object LocalPort) {
      $process = Get-CimInstance Win32_Process -Filter "ProcessId = $($connection.OwningProcess)" -ErrorAction SilentlyContinue
      [pscustomobject]@{
        LocalPort = $connection.LocalPort
        ProcessId = $connection.OwningProcess
        Name = $process.Name
        CommandLine = $process.CommandLine
      }
    })
  if ($used.Count -gt 0) {
    $details = $used | Format-List | Out-String
    throw "project service ports are already in use. Stop existing project services first.`n$details"
  }
}

function Start-JavaService {
  param(
    [Parameter(Mandatory)] [hashtable]$Service,
    [Parameter(Mandatory)] [string]$LogDir
  )

  $name = $Service.Name
  if ($ReuseExisting -and (Test-PortOpen -Port $Service.Port)) {
    Write-Host "REUSE $name port=$($Service.Port)"
    if ($Service.ContainsKey('WaitBeforeNext')) {
      Start-Sleep -Seconds $Service.WaitBeforeNext
    } else {
      Start-Sleep -Seconds $StartupDelaySeconds
    }
    return
  }

  $pom = Join-Path $RepoRoot "$name\pom.xml"
  if (-not (Test-Path -LiteralPath $pom)) {
    throw "pom not found for $name`: $pom"
  }

  $out = Join-Path $LogDir "$name.out.log"
  $err = Join-Path $LogDir "$name.err.log"
  $process = Start-Process -FilePath $Maven `
    -WorkingDirectory $RepoRoot `
    -ArgumentList @('--batch-mode', '-f', $pom, 'spring-boot:run') `
    -RedirectStandardOutput $out `
    -RedirectStandardError $err `
    -WindowStyle Hidden `
    -PassThru

  Write-Host "STARTED $name pid=$($process.Id) log=$out"
  Wait-Port -ServiceName $name -Port $Service.Port -TimeoutSeconds $PortTimeoutSeconds
  if ($Service.ContainsKey('WaitBeforeNext')) {
    Start-Sleep -Seconds $Service.WaitBeforeNext
  } else {
    Start-Sleep -Seconds $StartupDelaySeconds
  }
}

function Start-RuntimeService {
  param([Parameter(Mandatory)] [string]$LogDir)

  if ($ReuseExisting -and (Test-PortOpen -Port $RuntimeService.Port)) {
    Write-Host "REUSE agent-runtime port=$($RuntimeService.Port)"
    Start-Sleep -Seconds $StartupDelaySeconds
    return
  }

  if (-not (Test-Path -LiteralPath $RuntimePython)) {
    throw "agent-runtime python not found: $RuntimePython"
  }
  if (-not (Test-Path -LiteralPath (Join-Path $RuntimeRoot '.env'))) {
    throw "agent-runtime .env not found: $(Join-Path $RuntimeRoot '.env')"
  }

  $out = Join-Path $LogDir 'agent-runtime.out.log'
  $err = Join-Path $LogDir 'agent-runtime.err.log'
  $process = Start-Process -FilePath $RuntimePython `
    -WorkingDirectory $RuntimeRoot `
    -ArgumentList @('-m', 'uvicorn', 'app.main:app', '--host', '0.0.0.0', '--port', "$($RuntimeService.Port)") `
    -RedirectStandardOutput $out `
    -RedirectStandardError $err `
    -WindowStyle Hidden `
    -PassThru

  Write-Host "STARTED agent-runtime pid=$($process.Id) log=$out"
  Wait-Port -ServiceName 'agent-runtime' -Port $RuntimeService.Port -TimeoutSeconds $PortTimeoutSeconds
  Start-Sleep -Seconds $StartupDelaySeconds
}

function Wait-EurekaApplications {
  param([Parameter(Mandatory)] [string[]]$ExpectedNames)

  $deadline = (Get-Date).AddSeconds($EurekaTimeoutSeconds)
  while ((Get-Date) -lt $deadline) {
    try {
      $response = Invoke-WebRequest -UseBasicParsing -Uri 'http://localhost:8761/eureka/apps' -Headers @{ Accept = 'application/json' } -TimeoutSec 8
      $applications = ($response.Content | ConvertFrom-Json).applications.application
      $upNames = @($applications | Where-Object {
          @($_.instance | Where-Object { $_.status -eq 'UP' }).Count -gt 0
        } | ForEach-Object { $_.name })
      $missing = @($ExpectedNames | Where-Object { $_ -notin $upNames })
      if ($missing.Count -eq 0) {
        Write-Host 'EUREKA all expected applications are UP'
        return
      }
      Write-Host "WAITING Eureka missing: $($missing -join ', ')"
    } catch {
      Write-Host "WAITING Eureka query failed: $($_.Exception.Message)"
    }
    Start-Sleep -Seconds 5
  }

  throw "Eureka did not report all expected applications UP within $EurekaTimeoutSeconds seconds"
}

if (-not (Test-Path -LiteralPath $Maven)) {
  throw "Maven wrapper not found: $Maven"
}

New-Item -ItemType Directory -Force -Path $LogRoot | Out-Null
$LogDir = Join-Path $LogRoot ("chain-" + (Get-Date -Format 'yyyyMMdd-HHmmss'))
New-Item -ItemType Directory -Path $LogDir | Out-Null

if (-not $ReuseExisting) {
  Assert-PortsFree -Ports $AllPorts
}

if (-not $SkipInstall) {
  Write-Host 'INSTALL reactor snapshots with -DskipTests'
  Invoke-Checked $ServiceCenter $Maven @('--batch-mode', '-f', (Join-Path $ServiceCenter 'pom.xml'), '-DskipTests', 'install')
}

Start-JavaService -Service $JavaServices[0] -LogDir $LogDir
Start-JavaService -Service $JavaServices[1] -LogDir $LogDir
Start-RuntimeService -LogDir $LogDir

foreach ($service in $JavaServices[2..($JavaServices.Count - 1)]) {
  Start-JavaService -Service $service -LogDir $LogDir
}

Wait-EurekaApplications -ExpectedNames @(
  'AGENT-SERVICE',
  'AUTH-SERVICE',
  'CONFIG-SERVICE',
  'DOCUMENT-GENERATION-ADAPTER',
  'EMPLOYEE-SERVICE',
  'ES-QUERY-SERVICE',
  'GATEWAY-SERVICE',
  'M-SERVICE',
  'MQ-CONSUMER-SERVICE',
  'MQ-PROCEDURE-SERVICE',
  'OPENFEIGN-SERVICE',
  'WORKFLOW-SERVICE'
)

Write-Host "All project services started. Logs: $LogDir"
