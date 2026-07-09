package com.dylan.esquery.service;

import com.dylan.esquery.config.EsQueryProperties;
import org.junit.jupiter.api.Test;

import java.util.List;
import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class DocumentIndexValidationServiceTest {

    @Test
    void validatesGoldQueryProfileAndMarksTaskPassed() {
        RebuildTaskRepository repository = successfulRepository();
        DocumentIndexValidationService service = service(repository);

        DocumentIndexValidationReport report = service.validateDocumentIndex(request(
                0.9d,
                0,
                true,
                true,
                true));

        var task = repository.findById("task-1");
        assertThat(task.getValidationStatus()).isEqualTo("PASSED");
        assertThat(task.getValidationDigest()).isEqualTo(report.validationDigest());
        assertThat(report.profileVersion()).isEqualTo("profile-v1");
        assertThat(report.goldSetVersion()).isEqualTo("gold-tax-v1");
        assertThat(report.permissionLeakCount()).isZero();
        assertThat(report.rollbackReady()).isTrue();
        assertThat(report.metrics()).containsEntry("recallAtK", 0.9d);
    }

    @Test
    void blocksAliasSwitchWhenGoldQueryFails() {
        RebuildTaskRepository repository = successfulRepository();

        assertThatThrownBy(() -> service(repository).validateDocumentIndex(request(
                0.7d,
                0,
                true,
                true,
                true)))
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("GOLD_QUERY_HIT_RATE_LOW");
        assertThat(repository.findById("task-1").getValidationStatus()).isEqualTo("FAILED");
    }

    @Test
    void blocksAliasSwitchWhenPermissionGoldQueryLeaks() {
        RebuildTaskRepository repository = successfulRepository();

        assertThatThrownBy(() -> service(repository).validateDocumentIndex(request(
                0.9d,
                1,
                true,
                true,
                true)))
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("PERMISSION_LEAK");
        assertThat(repository.findById("task-1").getValidationStatus()).isEqualTo("FAILED");
    }

    @Test
    void rejectsGoldCaseOutsideValidationScope() {
        RebuildTaskRepository repository = successfulRepository();
        DocumentRetrievalValidationRequest request = request(
                0.9d,
                0,
                true,
                true,
                true);
        DocumentGoldQueryCase mismatched = new DocumentGoldQueryCase(
                "case-2",
                "国家税务总局公告",
                "other_domain",
                "policy",
                "tax-v2",
                "profile-v1",
                "gold-tax-v1",
                List.of("doc-1"),
                List.of(),
                List.of(),
                List.of(),
                5,
                "DOCUMENT_NUMBER");
        DocumentRetrievalValidationRequest mismatchedRequest = new DocumentRetrievalValidationRequest(
                request.taskId(),
                request.domain(),
                request.materialType(),
                request.retrievalProfile(),
                request.profileVersion(),
                request.indexAlias(),
                request.indexVersion(),
                request.goldSetVersion(),
                request.schemaValidated(),
                request.aclValidated(),
                request.rollbackDryRunReady(),
                request.minimumTopKHitRate(),
                request.actualTopKHitRate(),
                request.permissionLeakCount(),
                List.of(mismatched),
                request.metrics());

        assertThatThrownBy(() -> service(repository).validateDocumentIndex(mismatchedRequest))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("scope");
    }

    @Test
    void reportIdUsesIndexProfileAndGoldSetVersionWithStableMetricDigest() {
        RebuildTaskRepository firstRepository = successfulRepository("task-1");
        RebuildTaskRepository secondRepository = successfulRepository("task-2");

        Map<String, Double> firstMetrics = new java.util.LinkedHashMap<>();
        firstMetrics.put("channelRecallAtK", 0.91d);
        firstMetrics.put("rerankDeltaAtK", 0.03d);
        Map<String, Double> secondMetrics = new java.util.LinkedHashMap<>();
        secondMetrics.put("rerankDeltaAtK", 0.03d);
        secondMetrics.put("channelRecallAtK", 0.91d);

        DocumentIndexValidationReport firstReport = DocumentIndexValidationReport.passed(
                firstRepository.findById("task-1"),
                "validator-v2",
                request("task-1", 0.9d, 0, true, true, true, firstMetrics));
        DocumentIndexValidationReport secondReport = DocumentIndexValidationReport.passed(
                secondRepository.findById("task-2"),
                "validator-v2",
                request("task-2", 0.9d, 0, true, true, true, secondMetrics));
        DocumentIndexValidationReport sameTaskReport = DocumentIndexValidationReport.passed(
                firstRepository.findById("task-1"),
                "validator-v2",
                request("task-1", 0.9d, 0, true, true, true, secondMetrics));

        assertThat(firstReport.validationReportId()).isEqualTo(secondReport.validationReportId());
        assertThat(firstReport.validationDigest()).isEqualTo(sameTaskReport.validationDigest());
    }

    private DocumentRetrievalValidationRequest request(
            double actualHitRate,
            int permissionLeakCount,
            boolean schemaValidated,
            boolean aclValidated,
            boolean rollbackReady) {
        return request("task-1", actualHitRate, permissionLeakCount, schemaValidated, aclValidated, rollbackReady,
                Map.of("recallAtK", actualHitRate));
    }

    private DocumentRetrievalValidationRequest request(
            String taskId,
            double actualHitRate,
            int permissionLeakCount,
            boolean schemaValidated,
            boolean aclValidated,
            boolean rollbackReady,
            Map<String, Double> metrics) {
        return new DocumentRetrievalValidationRequest(
                taskId,
                "tax_policy",
                "policy",
                "tax-v2",
                "profile-v1",
                "agent-doc-policy",
                "idx-v2",
                "gold-tax-v1",
                schemaValidated,
                aclValidated,
                rollbackReady,
                0.8d,
                actualHitRate,
                permissionLeakCount,
                List.of(new DocumentGoldQueryCase(
                        "case-1",
                        "国家税务总局公告〔2023〕1号",
                        "tax_policy",
                        "policy",
                        "tax-v2",
                        "profile-v1",
                        "gold-tax-v1",
                        List.of("doc-1"),
                        List.of("doc-deny"),
                        List.of("doc-revoked"),
                        List.of(),
                        5,
                        "DOCUMENT_NUMBER")),
                metrics);
    }

    private DocumentIndexValidationService service(RebuildTaskRepository repository) {
        EsQueryProperties properties = new EsQueryProperties();
        properties.setTotalHitsThreshold(10000);
        return new DocumentIndexValidationService(new DocumentIndexPolicy(properties), repository);
    }

    private RebuildTaskRepository successfulRepository() {
        return successfulRepository("task-1");
    }

    private RebuildTaskRepository successfulRepository(String taskId) {
        RebuildTaskRepository repository = new InMemoryRebuildTaskRepository();
        repository.create(taskId, "agent-doc-policy", "agent-doc-policy-v2", "FULL");
        repository.markRunning(taskId);
        repository.markProgress(taskId, 3, "cursor-3");
        repository.markSuccess(taskId);
        return repository;
    }
}
