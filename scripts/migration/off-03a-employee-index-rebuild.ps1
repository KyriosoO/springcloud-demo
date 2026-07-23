[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidatePattern('^employee-off03a-[a-z0-9-]+$')]
    [string]$TargetIndex,

    [string]$EmployeeSourceUrl = 'http://127.0.0.1:9210/internal/es/employees',

    [string]$EsManagementUrl = 'http://127.0.0.1:9201/es',

    [string]$ElasticsearchUrl = 'http://127.0.0.1:9200',

    [int]$BatchSize = 500,

    [string]$ManagementToken = $env:ES_QUERY_MANAGEMENT_SERVICE_TOKEN,

    [string]$EvidencePath = (
        Join-Path $PSScriptRoot (
            '..\..\artifacts\off-03a\{0}-{1}.json' -f
            $TargetIndex,
            (Get-Date -Format 'yyyyMMdd-HHmmss')
        )
    ),

    [int]$PollIntervalSeconds = 2,

    [int]$TimeoutSeconds = 600
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

if ($BatchSize -lt 1 -or $BatchSize -gt 500) {
    throw 'BatchSize must be between 1 and 500.'
}
if ([string]::IsNullOrWhiteSpace($ManagementToken)) {
    throw 'ES_QUERY_MANAGEMENT_SERVICE_TOKEN or -ManagementToken is required.'
}
if ($PollIntervalSeconds -lt 1 -or $TimeoutSeconds -lt 1) {
    throw 'PollIntervalSeconds and TimeoutSeconds must be positive.'
}

function Invoke-JsonRequest {
    param(
        [Parameter(Mandatory = $true)]
        [Microsoft.PowerShell.Commands.WebRequestMethod]$Method,
        [Parameter(Mandatory = $true)]
        [string]$Uri,
        [object]$Body,
        [hashtable]$Headers = @{}
    )

    $parameters = @{
        Method      = $Method
        Uri         = $Uri
        Headers     = $Headers
        TimeoutSec  = 15
        ErrorAction = 'Stop'
    }
    if ($null -ne $Body) {
        $parameters.ContentType = 'application/json'
        $parameters.Body = $Body | ConvertTo-Json -Depth 20 -Compress
    }
    return Invoke-RestMethod @parameters
}

function Get-IndexMetadata {
    param([Parameter(Mandatory = $true)][string]$Index)

    try {
        $metadata = Invoke-JsonRequest -Method Get -Uri (
            '{0}/{1}' -f $ElasticsearchUrl.TrimEnd('/'), $Index
        )
        return $metadata.$Index
    }
    catch {
        $response = $_.Exception.Response
        if ($null -ne $response -and [int]$response.StatusCode -eq 404) {
            return $null
        }
        throw
    }
}

$cluster = Invoke-JsonRequest -Method Get -Uri (
    '{0}/_cluster/health?wait_for_status=yellow&timeout=10s' -f
    $ElasticsearchUrl.TrimEnd('/')
)
if ($cluster.timed_out -or $cluster.status -eq 'red') {
    throw 'Elasticsearch cluster is not ready for OFF-03A.'
}

$sourceProbe = Invoke-JsonRequest -Method Get -Uri (
    '{0}?batchSize=1' -f $EmployeeSourceUrl
)
if ($null -eq $sourceProbe.documents) {
    throw 'Employee source endpoint returned an invalid page.'
}

$existingTarget = Get-IndexMetadata -Index $TargetIndex
if ($null -ne $existingTarget) {
    throw "Target index '$TargetIndex' already exists; refusing destructive overwrite."
}

$currentIndex = Get-IndexMetadata -Index 'employee'
$currentUuid = if ($null -eq $currentIndex) { $null } else { $currentIndex.settings.index.uuid }
$currentCount = if ($null -eq $currentIndex) {
    0
}
else {
    (Invoke-JsonRequest -Method Get -Uri (
        '{0}/employee/_count' -f $ElasticsearchUrl.TrimEnd('/')
    )).count
}

$indexDefinition = @{
    settings = @{
        number_of_shards   = 1
        number_of_replicas = 1
    }
    mappings = @{
        dynamic    = 'strict'
        properties = @{
            idCardNo      = @{ type = 'keyword' }
            memberNo      = @{ type = 'keyword' }
            phoneNo       = @{ type = 'keyword' }
            email         = @{ type = 'keyword' }
            chineseName   = @{
                type            = 'text'
                analyzer        = 'ik_max_word'
                search_analyzer = 'ik_smart'
                fields          = @{ keyword = @{ type = 'keyword' } }
            }
            contactAddress = @{
                type            = 'text'
                analyzer        = 'ik_max_word'
                search_analyzer = 'ik_smart'
                fields          = @{ keyword = @{ type = 'keyword' } }
            }
            position       = @{
                type            = 'text'
                analyzer        = 'ik_max_word'
                search_analyzer = 'ik_smart'
                fields          = @{ keyword = @{ type = 'keyword' } }
            }
            workBaseSi     = @{ type = 'keyword' }
            operTime       = @{ type = 'date'; ignore_malformed = $true }
            embeddingText  = @{
                type            = 'text'
                analyzer        = 'ik_max_word'
                search_analyzer = 'ik_smart'
                fields          = @{ keyword = @{ type = 'keyword' } }
            }
        }
    }
}

$headers = @{ 'X-Es-Management-Token' = $ManagementToken }
$task = Invoke-JsonRequest -Method Post -Uri (
    '{0}/indexes/employee/rebuild/full' -f $EsManagementUrl.TrimEnd('/')
) -Headers $headers -Body @{
    sourceUrl      = $EmployeeSourceUrl
    idField        = 'idCardNo'
    targetIndex    = $TargetIndex
    batchSize      = $BatchSize
    indexDefinition = $indexDefinition
}
if ([string]::IsNullOrWhiteSpace($task.taskId)) {
    throw 'Rebuild endpoint returned no taskId.'
}

$deadline = (Get-Date).AddSeconds($TimeoutSeconds)
do {
    Start-Sleep -Seconds $PollIntervalSeconds
    $task = Invoke-JsonRequest -Method Get -Uri (
        '{0}/rebuild/tasks/{1}' -f $EsManagementUrl.TrimEnd('/'), $task.taskId
    ) -Headers $headers
    if ($task.status -in @('SUCCESS', 'FAILED')) {
        break
    }
} while ((Get-Date) -lt $deadline)

if ($task.status -ne 'SUCCESS') {
    throw "OFF-03A rebuild did not complete successfully; status=$($task.status)."
}

$targetMetadata = Get-IndexMetadata -Index $TargetIndex
if ($null -eq $targetMetadata) {
    throw 'Successful rebuild task did not create the target index.'
}
$workBaseMapping = $targetMetadata.mappings.properties.workBaseSi
if ($workBaseMapping.type -ne 'keyword') {
    throw 'Target workBaseSi mapping is not keyword.'
}

$targetCount = (Invoke-JsonRequest -Method Get -Uri (
    '{0}/{1}/_count' -f $ElasticsearchUrl.TrimEnd('/'), $TargetIndex
)).count
if ($targetCount -ne $task.totalIndexed) {
    throw 'Target document count does not match rebuild task totalIndexed.'
}

$fieldCounts = Invoke-JsonRequest -Method Post -Uri (
    '{0}/{1}/_search' -f $ElasticsearchUrl.TrimEnd('/'), $TargetIndex
) -Body @{
    size = 0
    aggs = @{
        withWorkBase = @{ filter = @{ exists = @{ field = 'workBaseSi' } } }
        missingWorkBase = @{ missing = @{ field = 'workBaseSi' } }
    }
}
$samples = Invoke-JsonRequest -Method Post -Uri (
    '{0}/{1}/_search' -f $ElasticsearchUrl.TrimEnd('/'), $TargetIndex
) -Body @{
    size = 5
    query = @{ exists = @{ field = 'workBaseSi' } }
    _source = @('position', 'workBaseSi')
}

$evidence = [ordered]@{
    evidenceType = 'OFF-03A_EMPLOYEE_INDEX_REBUILD'
    recordedAt = (Get-Date).ToUniversalTime().ToString('o')
    migrationTool = 'legacy-es-rebuild-endpoint'
    targetRuntimeAuthority = 'not-asserted'
    sourceUrl = $EmployeeSourceUrl
    sourceIndex = @{
        name = 'employee'
        uuid = $currentUuid
        documentCount = $currentCount
    }
    targetIndex = @{
        name = $TargetIndex
        uuid = $targetMetadata.settings.index.uuid
        documentCount = $targetCount
        workBaseMapping = $workBaseMapping.type
        withWorkBaseCount = $fieldCounts.aggregations.withWorkBase.doc_count
        missingWorkBaseCount = $fieldCounts.aggregations.missingWorkBase.doc_count
        samples = @($samples.hits.hits | ForEach-Object { $_._source })
    }
    rebuildTask = @{
        taskId = $task.taskId
        status = $task.status
        totalIndexed = $task.totalIndexed
    }
    cutoverPerformed = $false
    rollback = @{
        action = 'Keep employee reads on the original employee index.'
        destructiveCleanupAuthorized = $false
        targetDeletionRequired = $false
    }
}

$resolvedEvidencePath = [System.IO.Path]::GetFullPath($EvidencePath)
$evidenceDirectory = Split-Path -Parent $resolvedEvidencePath
New-Item -ItemType Directory -Path $evidenceDirectory -Force | Out-Null
$evidence | ConvertTo-Json -Depth 20 | Set-Content -LiteralPath $resolvedEvidencePath -Encoding utf8
$evidence | ConvertTo-Json -Depth 20
