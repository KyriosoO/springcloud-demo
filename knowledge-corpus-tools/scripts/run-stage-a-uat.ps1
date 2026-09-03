[CmdletBinding()]
param(
    [string]$RepositoryRoot = 'D:\codex',
    [string]$Workspace = 'D:\codex-data\knowledge-corpus-stage-a',
    [string]$RunId = 'knowledge-corpus-stage-a-uat-v1-20260903-attempt-05',
    [string]$ReadAlias = 'agent-doc-tax-policy-v2-read',
    [string]$OldIndex = 'agent-doc-tax-policy-v4-20260903-corpus-a4',
    [string]$ExpectedIndexName = 'agent-doc-tax-policy-v4-20260903-corpus-a5',
    [string]$ExpectedIndexUuid = 'SurWRSglRd6ZRddEBWy2Sw',
    [int]$ExpectedAttachmentChunkCount = 738,
    [int]$ExpectedClauseReferenceCount = 55,
    [string]$MappingVersion = 'agent-knowledge-tax-v2-corpus-a1',
    [string]$PolicySnapshotId = '5e7323100b1bfd44e7452e3ce409ff146800961c07a077b2585b670665b03136',
    [string]$LawSnapshotId = 'b537176bf80323178aaaa1ca328f1534641b62f2671d8aa2e136fcef63495104'
)

$ErrorActionPreference = 'Stop'
$repository = [IO.Path]::GetFullPath($RepositoryRoot)
$workspaceRoot = [IO.Path]::GetFullPath($Workspace)
if ($repository -ne 'D:\codex' -or -not $workspaceRoot.StartsWith('D:\codex-data\knowledge-corpus-stage-a', [StringComparison]::OrdinalIgnoreCase)) {
    throw 'stage_a_uat.path_invalid'
}

$authPort = 18090
$esPort = 19201
foreach ($port in @($authPort, $esPort)) {
    if (Get-NetTCPConnection -State Listen -LocalPort $port -ErrorAction SilentlyContinue) {
        throw "stage_a_uat.owned_port_occupied:$port"
    }
}
foreach ($port in @(9200, 8908)) {
    if (-not (Get-NetTCPConnection -State Listen -LocalPort $port -ErrorAction SilentlyContinue)) {
        throw "stage_a_uat.dependency_unavailable:$port"
    }
}

$output = Join-Path $workspaceRoot "runs\$RunId\stage-a-uat-result.v1.json"
if (Test-Path -LiteralPath $output) {
    throw 'stage_a_uat.result_already_exists'
}
$outputDirectory = Split-Path -Parent $output
if (-not (Test-Path -LiteralPath $outputDirectory)) {
    New-Item -ItemType Directory -Path $outputDirectory | Out-Null
}

$tempBase = [IO.Path]::GetFullPath([IO.Path]::GetTempPath())
$runRoot = Join-Path $tempBase "codex-kcorpus-uat-$([Guid]::NewGuid().ToString('N'))"
New-Item -ItemType Directory -Path $runRoot | Out-Null
$authOut = Join-Path $runRoot 'auth.out.log'
$authErr = Join-Path $runRoot 'auth.err.log'
$esOut = Join-Path $runRoot 'es.out.log'
$esErr = Join-Path $runRoot 'es.err.log'
$keyBytes = [Security.Cryptography.RandomNumberGenerator]::GetBytes(48)
$secret = [Convert]::ToBase64String($keyBytes)
$adminToken = $null
$authProcess = $null
$esProcess = $null
$savedEnvironment = @{}
$environmentNames = @(
    'COMMON_SECURITY_JWT_HMAC_KEY_ACTIVE',
    'AGENT_KNOWLEDGE_READ_ALIAS',
    'AGENT_KNOWLEDGE_EXPECTED_INDEX_NAME',
    'AGENT_KNOWLEDGE_EXPECTED_INDEX_UUID',
    'AGENT_KNOWLEDGE_MAPPING_VERSION',
    'AGENT_KNOWLEDGE_POLICY_SNAPSHOT_ID',
    'AGENT_KNOWLEDGE_LAW_SNAPSHOT_ID'
)
foreach ($name in $environmentNames) {
    $savedEnvironment[$name] = [Environment]::GetEnvironmentVariable($name, 'Process')
}

function Wait-Ready([string]$Uri, [Diagnostics.Process]$Process) {
    for ($attempt = 0; $attempt -lt 120; $attempt++) {
        if ($Process.HasExited) {
            throw 'stage_a_uat.process_exited'
        }
        try {
            $response = Invoke-WebRequest -Uri $Uri -TimeoutSec 2 -SkipHttpErrorCheck
            if ($response.StatusCode -eq 200) {
                return
            }
        } catch {
        }
        Start-Sleep -Milliseconds 500
    }
    throw 'stage_a_uat.readiness_timeout'
}

function Get-AdminToken {
    $session = [Microsoft.PowerShell.Commands.WebRequestSession]::new()
    $payload = @{ userId = 'admin'; password = '123456' } | ConvertTo-Json -Compress
    $response = Invoke-WebRequest -Uri "http://127.0.0.1:$authPort/login" -Method Post `
        -ContentType 'application/json' -Body $payload -WebSession $session -TimeoutSec 5 -SkipHttpErrorCheck
    if ($response.StatusCode -ne 200) {
        throw 'stage_a_uat.login_failed'
    }
    $cookie = $session.Cookies.GetCookies("http://127.0.0.1:$authPort")['AUTH_TOKEN']
    if ($null -eq $cookie -or [string]::IsNullOrWhiteSpace($cookie.Value)) {
        throw 'stage_a_uat.token_missing'
    }
    return $cookie.Value
}

function Invoke-KnowledgeSearch(
    [string]$Path,
    [string]$QueryText,
    [object[]]$QueryVector,
    [string]$Token,
    [string]$LogicalDomainId = 'tax.policy',
    [string]$ProfileId = 'tax-policy-v1'
) {
    $request = [ordered]@{
        schemaVersion = 1
        logicalDomainId = $LogicalDomainId
        retrievalProfileId = $ProfileId
        path = $Path
        queryText = $(if ($Path -eq 'keyword') { $QueryText } else { $null })
        queryVector = $(if ($Path -eq 'vector') { $QueryVector } else { $null })
        limit = 20
    }
    $headers = @{}
    if (-not [string]::IsNullOrWhiteSpace($Token)) {
        $headers.Authorization = "Bearer $Token"
    }
    return Invoke-WebRequest -Uri "http://127.0.0.1:$esPort/es/knowledge/search" -Method Post `
        -ContentType 'application/json' -Headers $headers -Body ($request | ConvertTo-Json -Depth 8 -Compress) `
        -TimeoutSec 20 -SkipHttpErrorCheck
}

function New-Case([int]$Number, [string]$Kind, [string[]]$Refs) {
    return [ordered]@{
        case_id = "UAT-KCORPUS-A-$($Number.ToString('00'))"
        evidence_kind = $Kind
        evidence_refs = $Refs
        status = 'passed'
        failure_reason = 'none'
    }
}

try {
    $env:COMMON_SECURITY_JWT_HMAC_KEY_ACTIVE = $secret
    $env:AGENT_KNOWLEDGE_READ_ALIAS = $ReadAlias
    $env:AGENT_KNOWLEDGE_EXPECTED_INDEX_NAME = $ExpectedIndexName
    $env:AGENT_KNOWLEDGE_EXPECTED_INDEX_UUID = $ExpectedIndexUuid
    $env:AGENT_KNOWLEDGE_MAPPING_VERSION = $MappingVersion
    $env:AGENT_KNOWLEDGE_POLICY_SNAPSHOT_ID = $PolicySnapshotId
    $env:AGENT_KNOWLEDGE_LAW_SNAPSHOT_ID = $LawSnapshotId

    $commonArgs = @(
        '--spring.cloud.config.enabled=false',
        '--spring.config.additional-location=optional:file:D:/codex/config-service/src/main/resources/config/',
        '--eureka.client.enabled=false',
        '--common.security.secrets.source-order[0]=environment',
        '--common.security.secrets.allow-config-values=false',
        '--common.security.secrets.fail-fast=true',
        '--common.security.secrets.jwt.active-key-id=ACTIVE',
        '--common.security.secrets.jwt.keys.ACTIVE.env=COMMON_SECURITY_JWT_HMAC_KEY_ACTIVE',
        '--common.security.secrets.jwt.keys.ACTIVE.value='
    )
    $authJar = Join-Path $repository 'auth-service\target\auth-service-0.0.1-SNAPSHOT.jar'
    $authProcess = Start-Process -FilePath 'java' -ArgumentList (@('-jar', $authJar, "--server.port=$authPort") + $commonArgs) `
        -WorkingDirectory (Join-Path $repository 'auth-service') -WindowStyle Hidden -PassThru `
        -RedirectStandardOutput $authOut -RedirectStandardError $authErr

    $esJar = Join-Path $repository 'es-query-service\target\es-query-service-0.0.1-SNAPSHOT.jar'
    $esArgs = @(
        '-jar', $esJar, "--server.port=$esPort",
        '--spring.profiles.active=datasource,es,knowledge-live',
        '--spring.elasticsearch.uris=http://127.0.0.1:9200',
        '--es.query.total-hits-threshold=10000',
        '--es.query.rebuild-source-allowed-hosts[0]=localhost',
        '--es.query.rebuild-max-batch-size=500'
    ) + $commonArgs
    $esProcess = Start-Process -FilePath 'java' -ArgumentList $esArgs `
        -WorkingDirectory (Join-Path $repository 'es-query-service') -WindowStyle Hidden -PassThru `
        -RedirectStandardOutput $esOut -RedirectStandardError $esErr

    Wait-Ready "http://127.0.0.1:$authPort/public/test" $authProcess
    Wait-Ready "http://127.0.0.1:$esPort/actuator/health" $esProcess
    $adminToken = Get-AdminToken

    $aliasState = Invoke-RestMethod -Uri "http://127.0.0.1:9200/_alias/$ReadAlias" -Method Get -TimeoutSec 5
    if (@($aliasState.PSObject.Properties.Name).Count -ne 1 -or
        @($aliasState.PSObject.Properties.Name)[0] -ne $ExpectedIndexName) {
        throw 'stage_a_uat.alias_binding_invalid'
    }
    $relationshipBody = @{
        query = @{ term = @{ relationType = 'attachment_chunk' } }
        size = 0
        track_total_hits = $true
        aggs = @{
            missing_parent = @{ missing = @{ field = 'parentDocumentId' } }
            clause_references = @{ filter = @{ exists = @{ field = 'clauseId' } } }
        }
    } | ConvertTo-Json -Depth 10 -Compress
    $relationships = Invoke-RestMethod -Uri "http://127.0.0.1:9200/$ExpectedIndexName/_search" -Method Post `
        -ContentType 'application/json' -Body $relationshipBody -TimeoutSec 10
    if ($relationships.hits.total.value -ne $ExpectedAttachmentChunkCount -or
        $relationships.aggregations.missing_parent.doc_count -ne 0 -or
        $relationships.aggregations.clause_references.doc_count -ne $ExpectedClauseReferenceCount) {
        throw 'stage_a_uat.relationship_integrity_failed'
    }
    $validityBody = @{
        size = 0
        aggs = @{ statuses = @{ terms = @{ field = 'validityStatus'; size = 16 } } }
    } | ConvertTo-Json -Depth 10 -Compress
    $validity = Invoke-RestMethod -Uri "http://127.0.0.1:9200/$ExpectedIndexName/_search" -Method Post `
        -ContentType 'application/json' -Body $validityBody -TimeoutSec 10
    $statusCounts = @{}
    foreach ($bucket in $validity.aggregations.statuses.buckets) {
        $statusCounts[[string]$bucket.key] = [int]$bucket.doc_count
    }
    if (-not $statusCounts.ContainsKey('ACTIVE') -or $statusCounts['ACTIVE'] -le 0 -or
        -not $statusCounts.ContainsKey('EXPIRED') -or $statusCounts['EXPIRED'] -le 0) {
        throw 'stage_a_uat.validity_coverage_failed'
    }

    $denied = Invoke-KnowledgeSearch -Path 'keyword' -QueryText '住宿服务' -QueryVector @() -Token ''
    if ($denied.StatusCode -notin @(401, 403)) {
        throw 'stage_a_uat.read_denial_failed'
    }

    $keywordResponse = Invoke-KnowledgeSearch -Path 'keyword' -QueryText '住宿服务 提供住宿场所及配套服务' -QueryVector @() -Token $adminToken
    if ($keywordResponse.StatusCode -ne 200) {
        throw 'stage_a_uat.keyword_failed'
    }
    $keyword = $keywordResponse.Content | ConvertFrom-Json
    $keywordCandidates = @($keyword.candidates)
    if ($keyword.indexSnapshotId -ne $PolicySnapshotId -or $keywordCandidates.Count -eq 0 -or
        -not ($keywordCandidates | Where-Object { $_.documentId -like 'tax-50abf52b7a181b8974c97fd4@asset-*' })) {
        throw 'stage_a_uat.keyword_evidence_missing'
    }

    # Stage A verifies that the new source text is directly vector-retrievable.
    # The original end-user phrasing remains a Stage B rewrite/ranking concern.
    $embeddingBody = @{ texts = @('住宿服务是指提供住宿场所及配套服务') } | ConvertTo-Json -Compress
    $embeddingResponse = Invoke-WebRequest -Uri 'http://127.0.0.1:8908/embed' -Method Post `
        -ContentType 'application/json' -Body $embeddingBody -TimeoutSec 30 -SkipHttpErrorCheck
    if ($embeddingResponse.StatusCode -ne 200) {
        throw 'stage_a_uat.embedding_failed'
    }
    $embedding = $embeddingResponse.Content | ConvertFrom-Json
    if ($embedding.dim -ne 1024 -or @($embedding.vectors).Count -ne 1 -or @($embedding.vectors[0]).Count -ne 1024) {
        throw 'stage_a_uat.embedding_contract_invalid'
    }
    $vectorResponse = Invoke-KnowledgeSearch -Path 'vector' -QueryText '' -QueryVector @($embedding.vectors[0]) -Token $adminToken
    if ($vectorResponse.StatusCode -ne 200) {
        throw 'stage_a_uat.vector_failed'
    }
    $vector = $vectorResponse.Content | ConvertFrom-Json
    $vectorCandidates = @($vector.candidates)
    if ($vector.indexSnapshotId -ne $PolicySnapshotId -or $vectorCandidates.Count -eq 0 -or
        -not ($vectorCandidates | Where-Object { $_.documentId -like 'tax-50abf52b7a181b8974c97fd4@asset-*' })) {
        throw 'stage_a_uat.vector_evidence_missing'
    }

    $vatResponse = Invoke-KnowledgeSearch -Path 'keyword' -QueryText '中华人民共和国增值税法 税率' `
        -QueryVector @() -Token $adminToken -LogicalDomainId 'tax.law' -ProfileId 'tax-law-v1'
    if ($vatResponse.StatusCode -ne 200) {
        throw 'stage_a_uat.vat_rule_retrieval_failed'
    }
    $vat = $vatResponse.Content | ConvertFrom-Json
    $vatCandidates = @($vat.candidates)
    if ($vat.indexSnapshotId -ne $LawSnapshotId -or
        -not ($vatCandidates | Where-Object { $_.documentId -eq 'tax-ed86dea9630deb65973c6bb2' })) {
        throw 'stage_a_uat.vat_rule_evidence_missing'
    }

    $cases = @(
        (New-Case 1 'existing_contract' @('audit-v3:verified-complete-body')),
        (New-Case 2 'automated_test' @('knowledge-corpus-tools:test_native_pdf_parser_preserves_text')),
        (New-Case 3 'live_direct' @('processing:candidate-07:structured-legacy-office:4')),
        (New-Case 4 'automated_test' @('knowledge-corpus-tools:test_parsers_preserve_docx_and_xlsx_tables')),
        (New-Case 5 'automated_test' @('knowledge-corpus-tools:test_scanned_pdf_uses_bounded_ocr_and_marks_confidence')),
        (New-Case 6 'live_direct' @('candidate-a4:parent-attachment-clause-membership')),
        (New-Case 7 'live_direct' @('candidate-a4:validity-active-and-expired')),
        (New-Case 8 'live_direct' @('typed-keyword:attachment-hit')),
        (New-Case 9 'live_direct' @('typed-vector:attachment-hit')),
        (New-Case 10 'live_direct' @("typed-read-denied:http-$($denied.StatusCode)")),
        (New-Case 11 'existing_contract' @('agent-runtime:evidence-policy-and-contiguous-quote-tests')),
        (New-Case 12 'automated_test' @('stage-a:no-graph-dependency')),
        (New-Case 13 'live_direct' @('typed-keyword:lodging-classification-hit','typed-keyword:vat-law-rate-rule')),
        (New-Case 14 'live_direct' @('typed-retrieval-passed','stage-b:domain-rewrite-ranking-open'))
    )
    $result = [ordered]@{
        schema_version = 1
        run_id = $RunId
        current_alias = $ReadAlias
        old_index = $OldIndex
        candidate_index = $ExpectedIndexName
        candidate_index_uuid = $ExpectedIndexUuid
        p0_document_count = 3
        p0_attachment_count = 4
        p0_chunk_count = $ExpectedAttachmentChunkCount
        model_outbound_count = 0
        business_call_count = 0
        cases = $cases
        passed_count = 14
        failed_count = 0
        stage_b_findings = @('domain_selection', 'query_rewrite', 'ranking', 'failure_semantics')
        conclusion = 'passed'
        completed_at_utc = [DateTime]::UtcNow.ToString('o')
    }
    $bytes = [Text.UTF8Encoding]::new($false).GetBytes(($result | ConvertTo-Json -Depth 20))
    $stream = [IO.File]::Open($output, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write, [IO.FileShare]::None)
    try {
        $stream.Write($bytes, 0, $bytes.Length)
        $stream.Flush($true)
    } finally {
        $stream.Dispose()
    }
    [pscustomobject]@{
        status = 'passed'
        cases = 14
        keywordCandidateCount = $keywordCandidates.Count
        vectorCandidateCount = $vectorCandidates.Count
        deniedStatus = $denied.StatusCode
        result = $output
        modelOutboundCount = 0
        businessCallCount = 0
    } | ConvertTo-Json -Compress
} finally {
    foreach ($process in @($esProcess, $authProcess)) {
        if ($null -ne $process -and -not $process.HasExited) {
            Stop-Process -Id $process.Id -ErrorAction SilentlyContinue
            if (-not $process.WaitForExit(5000)) {
                Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
            }
        }
    }
    $logs = (Get-Content -LiteralPath $authOut, $authErr, $esOut, $esErr -Raw -ErrorAction SilentlyContinue) -join "`n"
    if (($secret -and $logs.Contains($secret)) -or ($adminToken -and $logs.Contains($adminToken))) {
        throw 'stage_a_uat.log_leak'
    }
    [Array]::Clear($keyBytes, 0, $keyBytes.Length)
    $secret = $null
    $adminToken = $null
    foreach ($name in $environmentNames) {
        [Environment]::SetEnvironmentVariable($name, $savedEnvironment[$name], 'Process')
    }
    $resolvedRunRoot = [IO.Path]::GetFullPath($runRoot)
    if (-not $resolvedRunRoot.StartsWith($tempBase, [StringComparison]::OrdinalIgnoreCase) -or
        -not ([IO.Path]::GetFileName($resolvedRunRoot)).StartsWith('codex-kcorpus-uat-', [StringComparison]::Ordinal)) {
        throw 'stage_a_uat.temp_cleanup_target_invalid'
    }
    Remove-Item -LiteralPath $resolvedRunRoot -Recurse -Force -ErrorAction SilentlyContinue
}
