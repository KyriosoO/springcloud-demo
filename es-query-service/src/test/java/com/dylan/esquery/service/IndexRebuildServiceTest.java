package com.dylan.esquery.service;

import com.dylan.esquery.api.model.RebuildRequest;
import com.dylan.esquery.config.EsQueryProperties;
import org.junit.jupiter.api.Test;
import org.springframework.http.MediaType;
import org.springframework.test.web.client.MockRestServiceServer;
import org.springframework.web.client.RestTemplate;

import java.util.Map;
import java.util.concurrent.Executor;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.requestTo;
import static org.springframework.test.web.client.response.MockRestResponseCreators.withSuccess;

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
    void rejectsBatchSizeAboveConfiguredMaximumBeforeSubmittingTask() {
        RebuildRequest request = request();
        request.setBatchSize(501);

        assertThatThrownBy(() -> service().submitIncrementalRebuild("orders", request))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("rebuildMaxBatchSize");
    }

    @Test
    void rejectsSourceParamsOverridingReservedParamsBeforeSubmittingTask() {
        RebuildRequest request = request();
        request.setSourceParams(Map.of("cursor", "override"));

        assertThatThrownBy(() -> service().submitIncrementalRebuild("orders", request))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("reserved parameter");
    }

    @Test
    void rejectsEmptyPageWithHasMoreDuringRebuild() {
        RestTemplate restTemplate = new RestTemplate();
        MockRestServiceServer server = MockRestServiceServer.bindTo(restTemplate).build();
        server.expect(requestTo("http://document-platform/internal/chunks?batchSize=500"))
                .andRespond(withSuccess("{\"documents\":[],\"hasMore\":true}", MediaType.APPLICATION_JSON));
        RebuildTaskRepository repository = new InMemoryRebuildTaskRepository();
        RebuildRequest request = request();
        request.setIdField("chunkId");

        var task = service(repository, restTemplate).submitIncrementalRebuild("agent-doc-policy", request);

        assertThat(task.getStatus()).isEqualTo("FAILED");
        assertThat(task.getErrorMessage()).contains("must not be empty when hasMore is true");
        server.verify();
    }

    @Test
    void createsDocumentRebuildTaskWithPendingStatusBeforeExecution() {
        RebuildRequest request = request();
        request.setIdField("chunkId");
        RebuildTaskRepository repository = new InMemoryRebuildTaskRepository();

        var task = service(repository, new RestTemplate(), command -> { }).submitIncrementalRebuild("agent-doc-policy", request);

        assertThat(task.getStatus()).isEqualTo("PENDING");
    }

    @Test
    void rejectsActiveDocumentRebuildForSameIndexBeforeSubmittingTask() {
        RebuildTaskRepository repository = new InMemoryRebuildTaskRepository();
        repository.create("task-1", "agent-doc-policy", "agent-doc-policy-v2", "FULL");
        RebuildRequest request = request();
        request.setIdField("chunkId");

        assertThatThrownBy(() -> service(repository, new RestTemplate()).submitIncrementalRebuild("agent-doc-policy", request))
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("active document rebuild");
    }

    @Test
    void localValidationWritesDigestForSuccessfulDocumentTask() {
        EsQueryProperties properties = new EsQueryProperties();
        properties.setTotalHitsThreshold(10000);
        DocumentIndexPolicy policy = new DocumentIndexPolicy(properties);
        RebuildTaskRepository repository = new InMemoryRebuildTaskRepository();
        repository.create("task-1", "agent-doc-policy", "agent-doc-policy-v2", "FULL");
        repository.markRunning("task-1");
        repository.markProgress("task-1", 3, "cursor-3");
        repository.markSuccess("task-1");

        new DocumentIndexValidationService(policy, repository).validateSuccessfulTask("task-1");

        var task = repository.findById("task-1");
        assertThat(task.getValidationStatus()).isEqualTo("PASSED");
        assertThat(task.getValidationDigest()).isNotBlank();
        assertThat(task.getValidationMessage()).isEqualTo("LOCAL_DOCUMENT_INDEX_VALIDATION_V2");
        assertThat(task.getValidatedAt()).isNotNull();
    }

    @Test
    void localValidationDigestChangesWhenValidationFactsChange() {
        RebuildTaskRepository repository = new InMemoryRebuildTaskRepository();
        repository.create("task-1", "agent-doc-policy", "agent-doc-policy-v2", "FULL");
        repository.markRunning("task-1");
        repository.markProgress("task-1", 3, "cursor-3");
        repository.markSuccess("task-1");
        RebuildTaskRepository changedRepository = new InMemoryRebuildTaskRepository();
        changedRepository.create("task-1", "agent-doc-policy", "agent-doc-policy-v2", "FULL");
        changedRepository.markRunning("task-1");
        changedRepository.markProgress("task-1", 4, "cursor-4");
        changedRepository.markSuccess("task-1");
        EsQueryProperties properties = new EsQueryProperties();
        properties.setTotalHitsThreshold(10000);
        DocumentIndexPolicy policy = new DocumentIndexPolicy(properties);

        new DocumentIndexValidationService(policy, repository).validateSuccessfulTask("task-1");
        new DocumentIndexValidationService(policy, changedRepository).validateSuccessfulTask("task-1");

        assertThat(repository.findById("task-1").getValidationDigest())
                .isNotEqualTo(changedRepository.findById("task-1").getValidationDigest());
    }

    private IndexRebuildService service() {
        return service(new InMemoryRebuildTaskRepository(), new RestTemplate());
    }

    private IndexRebuildService service(RebuildTaskRepository repository, RestTemplate restTemplate) {
        return service(repository, restTemplate, Runnable::run);
    }

    private IndexRebuildService service(RebuildTaskRepository repository, RestTemplate restTemplate, Executor executor) {
        EsQueryProperties properties = new EsQueryProperties();
        properties.setTotalHitsThreshold(10000);
        properties.setDocumentSourceAllowedHosts(java.util.List.of("document-platform"));
        properties.setRebuildMaxBatchSize(500);
        DocumentIndexPolicy policy = new DocumentIndexPolicy(properties);
        return new IndexRebuildService(
                null,
                repository,
                policy,
                new DocumentIndexValidationService(policy, repository),
                new DocumentSourceUrlPolicy(properties),
                properties,
                restTemplate,
                executor);
    }

    private RebuildRequest request() {
        RebuildRequest request = new RebuildRequest();
        request.setSourceUrl("http://document-platform/internal/chunks");
        request.setIndexDefinition(Map.of());
        return request;
    }
}
