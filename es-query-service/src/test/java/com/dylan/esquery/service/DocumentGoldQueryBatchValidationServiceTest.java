package com.dylan.esquery.service;

import com.dylan.esquery.api.model.AliasSwitchRequest;
import com.dylan.esquery.api.model.HybridSearchRequest;
import com.dylan.esquery.config.EsQueryProperties;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.elasticsearch.client.RestClient;
import org.junit.jupiter.api.Test;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

class DocumentGoldQueryBatchValidationServiceTest {

    @Test
    void validatesGoldQueriesAclProbesAndRollbackDryRun() throws Exception {
        RecordingExecutor executor = new RecordingExecutor(Map.of(
                "查询增值税优惠", List.of("doc-1"),
                "无权限政策", List.of()));
        RebuildTaskRepository repository = successfulRepository();
        EsIndexAliasService aliasService = mock(EsIndexAliasService.class);
        when(aliasService.rollbackReadAliasDryRun(any(), any()))
                .thenReturn(new AliasRollbackDryRunResult(
                        "agent-doc-policy",
                        List.of("agent-doc-policy-v2"),
                        "agent-doc-policy-v1",
                        "agent-doc-policy-v2",
                        true));
        DocumentGoldQueryBatchValidationService service = service(executor, repository, aliasService);

        DocumentIndexValidationReport report = service.validate(request());

        assertThat(report.status()).isEqualTo("PASSED");
        assertThat(report.actualTopKHitRate()).isEqualTo(1.0d);
        assertThat(report.permissionLeakCount()).isZero();
        assertThat(report.metrics()).containsEntry("acl.probeCount", 2.0d);
        assertThat(report.metrics()).containsEntry("rollback.dryRunReady", 1.0d);
        assertThat(repository.findById("task-1").getValidationStatus()).isEqualTo("PASSED");
        assertThat(executor.requests).hasSize(2);
        assertThat(executor.requests.get(0).getChannels()).extracting(channel -> channel.getChannel())
                .containsExactly("BM25", "EXACT", "PHRASE", "DENSE_VECTOR");
        assertThat(executor.requests.get(1).getChannels()).extracting(channel -> channel.getChannel())
                .containsExactly("BM25", "EXACT", "PHRASE");
        assertThat(executor.requests.get(0).getFilters().toString()).contains("tenantId", "tenant-1");
    }

    @Test
    void failsValidationWhenDeniedDocumentIsReturned() throws Exception {
        RecordingExecutor executor = new RecordingExecutor(Map.of(
                "查询增值税优惠", List.of("doc-1"),
                "无权限政策", List.of("doc-deny")));
        EsIndexAliasService aliasService = mock(EsIndexAliasService.class);
        when(aliasService.rollbackReadAliasDryRun(any(), any()))
                .thenReturn(new AliasRollbackDryRunResult(
                        "agent-doc-policy",
                        List.of("agent-doc-policy-v2"),
                        "agent-doc-policy-v1",
                        "agent-doc-policy-v2",
                        true));
        DocumentGoldQueryBatchValidationService service =
                service(executor, successfulRepository(), aliasService);

        assertThatThrownBy(() -> service.validate(request()))
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("PERMISSION_LEAK");
    }

    @Test
    void failsValidationWhenRollbackDryRunRequestIsMissing() {
        DocumentGoldQueryBatchValidationRequest request = new DocumentGoldQueryBatchValidationRequest(
                request().taskId(),
                request().domain(),
                request().materialType(),
                request().retrievalProfile(),
                request().profileVersion(),
                request().indexAlias(),
                request().indexVersion(),
                request().goldSetVersion(),
                request().schemaValidated(),
                request().minimumTopKHitRate(),
                request().filters(),
                request().permissionEvidenceId(),
                request().permissionVersion(),
                request().filterDigest(),
                request().embeddingField(),
                request().channelWeights(),
                null,
                request().goldQueryCases());
        DocumentGoldQueryBatchValidationService service =
                service(new RecordingExecutor(Map.of("查询增值税优惠", List.of("doc-1"), "无权限政策", List.of())),
                        successfulRepository(),
                        mock(EsIndexAliasService.class));

        assertThatThrownBy(() -> service.validate(request))
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("ROLLBACK_DRY_RUN_FAILED");
    }

    private DocumentGoldQueryBatchValidationService service(
            DocumentGoldQuerySearchExecutor executor,
            RebuildTaskRepository repository,
            EsIndexAliasService aliasService) {
        return new DocumentGoldQueryBatchValidationService(
                executor,
                new DocumentIndexValidationService(policy(), repository),
                aliasService);
    }

    private DocumentGoldQueryBatchValidationRequest request() {
        return new DocumentGoldQueryBatchValidationRequest(
                "task-1",
                "tax_policy",
                "policy",
                "tax-v2",
                "profile-v1",
                "agent-doc-policy",
                "idx-v2",
                "gold-tax-v1",
                true,
                0.8d,
                Map.of("bool", Map.of("filter", List.of(Map.of("term", Map.of("tenantId", "tenant-1"))))),
                "permission-evidence",
                "permission-v1",
                "sha256:filter",
                "embedding_v2",
                Map.of("BM25", 2.0d),
                rollbackRequest(),
                List.of(
                        new DocumentGoldQueryCase(
                                "case-1",
                                "查询增值税优惠",
                                "tax_policy",
                                "policy",
                                "tax-v2",
                                "profile-v1",
                                "gold-tax-v1",
                                List.of("doc-1"),
                                List.of(),
                                List.of("doc-revoked"),
                                List.of(0.1d, 0.2d),
                                5,
                                "BUSINESS_SEMANTIC"),
                        new DocumentGoldQueryCase(
                                "case-2",
                                "无权限政策",
                                "tax_policy",
                                "policy",
                                "tax-v2",
                                "profile-v1",
                                "gold-tax-v1",
                                List.of(),
                                List.of("doc-deny"),
                                List.of(),
                                List.of(),
                                5,
                                "ACL_DENY")));
    }

    private AliasSwitchRequest rollbackRequest() {
        AliasSwitchRequest request = new AliasSwitchRequest();
        request.setTaskId("task-rollback");
        request.setTargetIndex("agent-doc-policy-v1");
        request.setExpectedPreviousIndex("agent-doc-policy-v2");
        request.setValidationDigest("digest-rollback");
        request.setOperatorRef("operator-1");
        request.setDomain("tax_policy");
        request.setMaterialType("policy");
        request.setProfileVersion("profile-v1");
        request.setIndexVersion("idx-v2");
        request.setGoldSetVersion("gold-tax-v1");
        request.setValidationReportId("report-v2");
        return request;
    }

    private RebuildTaskRepository successfulRepository() {
        RebuildTaskRepository repository = new InMemoryRebuildTaskRepository();
        repository.create("task-1", "agent-doc-policy", "agent-doc-policy-v2", "FULL");
        repository.markRunning("task-1");
        repository.markProgress("task-1", 3, "cursor-3");
        repository.markSuccess("task-1");
        return repository;
    }

    private DocumentIndexPolicy policy() {
        EsQueryProperties properties = new EsQueryProperties();
        properties.setTotalHitsThreshold(10000);
        return new DocumentIndexPolicy(properties);
    }

    private static final class RecordingExecutor implements DocumentGoldQuerySearchExecutor {
        private final Map<String, List<String>> results;
        private final List<HybridSearchRequest> requests = new ArrayList<>();

        private RecordingExecutor(Map<String, List<String>> results) {
            this.results = results;
        }

        @Override
        public List<String> searchDocumentIds(String indexAlias, HybridSearchRequest request) {
            requests.add(request);
            return results.getOrDefault(request.getQueryText(), List.of());
        }
    }
}
