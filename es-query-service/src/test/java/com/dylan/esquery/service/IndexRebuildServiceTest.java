package com.dylan.esquery.service;

import com.dylan.esquery.api.model.RebuildRequest;
import com.dylan.esquery.api.model.RebuildTask;
import org.junit.jupiter.api.Test;

import java.util.Map;
import java.util.concurrent.Executor;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyNoInteractions;
import static org.mockito.Mockito.when;

class IndexRebuildServiceTest {

    private static final Executor DO_NOT_RUN = command -> { };

    @Test
    void genericRebuildRejectsDocumentTargets() {
        RebuildTaskRepository repository = mock(RebuildTaskRepository.class);
        IndexRebuildService service = new IndexRebuildService(
                mock(EsDocumentService.class), repository, DO_NOT_RUN);

        assertThatThrownBy(() -> service.submitFullRebuild(
                "agent-doc-policy-read", request("orders-v2")))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("DOCUMENT_SPECIALIZED_ENDPOINT_REQUIRED");
        verifyNoInteractions(repository);
    }

    @Test
    void genericRebuildRejectsReservedSourceParameters() {
        RebuildRequest request = request("orders-v2");
        request.setSourceParams(Map.of("cursor", "caller-controlled"));
        IndexRebuildService service = new IndexRebuildService(
                mock(EsDocumentService.class), mock(RebuildTaskRepository.class), DO_NOT_RUN);

        assertThatThrownBy(() -> service.submitFullRebuild("orders", request))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("reserved parameter");
    }

    @Test
    void genericRebuildKeepsNonDocumentIndexesOnGenericPath() {
        RebuildTaskRepository repository = mock(RebuildTaskRepository.class);
        RebuildTask task = new RebuildTask();
        task.setTaskId("task-1");
        when(repository.create(anyString(), anyString(), anyString(), anyString())).thenReturn(task);
        IndexRebuildService service = new IndexRebuildService(
                mock(EsDocumentService.class), repository, DO_NOT_RUN);

        RebuildTask created = service.submitFullRebuild("orders", request("orders-v2"));

        assertThat(created.getTaskId()).isEqualTo("task-1");
        verify(repository).create(anyString(), org.mockito.ArgumentMatchers.eq("orders"),
                org.mockito.ArgumentMatchers.eq("orders-v2"), org.mockito.ArgumentMatchers.eq("FULL"));
    }

    private static RebuildRequest request(String target) {
        RebuildRequest request = new RebuildRequest();
        request.setSourceUrl("http://document-platform/source");
        request.setTargetIndex(target);
        request.setBatchSize(10);
        return request;
    }
}
