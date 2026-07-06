package com.dylan.esquery.service;

import com.dylan.esquery.api.model.RebuildRequest;
import com.dylan.esquery.config.EsQueryProperties;
import org.junit.jupiter.api.Test;

import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class IndexRebuildServiceTest {

    @Test
    void rejectsDocumentFullRebuildWithoutIdFieldOrIndexDefinitionBeforeSubmittingTask() {
        IndexRebuildService service = service();
        RebuildRequest missingIdField = request();

        assertThatThrownBy(() -> service.submitFullRebuild("agent-doc-policy", missingIdField))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("idField");

        RebuildRequest missingIndexDefinition = request();
        missingIndexDefinition.setIdField("chunkId");

        assertThatThrownBy(() -> service.submitFullRebuild("agent-doc-policy", missingIndexDefinition))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("indexDefinition");
    }

    @Test
    void rejectsInvalidBatchSizeBeforeSubmittingTask() {
        RebuildRequest request = request();
        request.setBatchSize(0);

        assertThatThrownBy(() -> service().submitIncrementalRebuild("orders", request))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("batchSize");
    }

    @Test
    void localValidationWritesDigestForSuccessfulDocumentTask() {
        EsQueryProperties properties = new EsQueryProperties();
        properties.setTotalHitsThreshold(10000);
        DocumentIndexPolicy policy = new DocumentIndexPolicy(properties);
        RebuildTaskRepository repository = new RebuildTaskRepository();
        repository.create("task-1", "agent-doc-policy", "agent-doc-policy-v2", "FULL");
        repository.markRunning("task-1");
        repository.markProgress("task-1", 3, "cursor-3");
        repository.markSuccess("task-1");

        new DocumentIndexValidationService(policy, repository).validateSuccessfulTask("task-1");

        var task = repository.findById("task-1");
        assertThat(task.getValidationStatus()).isEqualTo("PASSED");
        assertThat(task.getValidationDigest()).isNotBlank();
        assertThat(task.getValidatedAt()).isNotNull();
    }

    private IndexRebuildService service() {
        EsQueryProperties properties = new EsQueryProperties();
        properties.setTotalHitsThreshold(10000);
        return new IndexRebuildService(
                null,
                new RebuildTaskRepository(),
                new DocumentIndexPolicy(properties),
                Runnable::run);
    }

    private RebuildRequest request() {
        RebuildRequest request = new RebuildRequest();
        request.setSourceUrl("http://document-platform/internal/chunks");
        request.setIndexDefinition(Map.of());
        return request;
    }
}
