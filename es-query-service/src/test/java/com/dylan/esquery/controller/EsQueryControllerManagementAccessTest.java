package com.dylan.esquery.controller;

import com.dylan.esquery.api.model.DocumentCorpusKeyDto;
import com.dylan.esquery.api.model.DocumentRebuildTaskView;
import com.dylan.esquery.api.model.RebuildRequest;
import com.dylan.esquery.api.model.RebuildTask;
import com.dylan.esquery.api.model.StartDocumentRebuildRequest;
import com.dylan.esquery.config.EsQueryProperties;
import com.dylan.esquery.document.DocumentCorpusCatalog;
import com.dylan.esquery.document.search.DocumentHybridSearchUseCase;
import com.dylan.esquery.document.DocumentIndexAccessGuard;
import com.dylan.esquery.document.DocumentIndexRebuildService;
import com.dylan.esquery.document.DocumentSearchAccessGuard;
import com.dylan.esquery.service.EsDocumentService;
import com.dylan.esquery.service.EsManagementAccessGuard;
import com.dylan.esquery.service.IndexRebuildService;
import com.dylan.esquery.service.RebuildTaskRepository;
import com.dylan.esquery.service.EsIndexAliasService;
import org.junit.jupiter.api.Test;
import org.springframework.http.HttpStatus;
import org.springframework.web.server.ResponseStatusException;

import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyNoInteractions;
import static org.mockito.Mockito.when;

class EsQueryControllerManagementAccessTest {

    @Test
    void rejectsGenericRebuildWithoutManagementServiceToken() {
        IndexRebuildService rebuildService = mock(IndexRebuildService.class);
        EsQueryController controller = controller(rebuildService, mock(DocumentIndexRebuildService.class), "local-token");

        assertThatThrownBy(() -> controller.fullRebuild("orders", new RebuildRequest(), null))
                .isInstanceOfSatisfying(ResponseStatusException.class, ex ->
                        assertThat(ex.getStatusCode()).isEqualTo(HttpStatus.FORBIDDEN));
        verifyNoInteractions(rebuildService);
    }

    @Test
    void acceptsGenericRebuildForNonDocumentTargetWithManagementToken() {
        IndexRebuildService rebuildService = mock(IndexRebuildService.class);
        RebuildRequest request = new RebuildRequest();
        RebuildTask task = new RebuildTask();
        task.setTaskId("task-1");
        when(rebuildService.submitFullRebuild("orders", request)).thenReturn(task);
        EsQueryController controller = controller(rebuildService, mock(DocumentIndexRebuildService.class), "local-token");

        assertThat(controller.fullRebuild("orders", request, "local-token").getTaskId()).isEqualTo("task-1");
        verify(rebuildService).submitFullRebuild("orders", request);
    }

    @Test
    void specializedDocumentRebuildUsesCorpusKeyAndNeverAcceptsCallerTarget() {
        DocumentIndexRebuildService documentService = mock(DocumentIndexRebuildService.class);
        StartDocumentRebuildRequest request = mock(StartDocumentRebuildRequest.class);
        DocumentRebuildTaskView view = mock(DocumentRebuildTaskView.class);
        when(documentService.start(any(), eq(request), eq("document-rebuild"))).thenReturn(view);
        EsQueryController controller = controller(mock(IndexRebuildService.class), documentService, "local-token");

        assertThat(controller.startDocumentRebuild(
                "policy", "document", request, "local-token")).isSameAs(view);
        verify(documentService).start(
                eq(new DocumentCorpusKeyDto("policy", "document")), eq(request), eq("document-rebuild"));
    }

    private static EsQueryController controller(
            IndexRebuildService rebuildService,
            DocumentIndexRebuildService documentService,
            String managementToken) {
        EsQueryProperties properties = new EsQueryProperties();
        properties.setTotalHitsThreshold(10_000);
        properties.setManagementServiceToken(managementToken);
        EsIndexAliasService aliases = mock(EsIndexAliasService.class);
        try {
            when(aliases.readCurrent(any())).thenAnswer(invocation ->
                    new EsIndexAliasService.AliasTargetView(invocation.getArgument(0), List.of()));
        } catch (java.io.IOException impossible) {
            throw new AssertionError(impossible);
        }
        return new EsQueryController(
                mock(EsDocumentService.class),
                rebuildService,
                mock(RebuildTaskRepository.class),
                new EsManagementAccessGuard(properties),
                new DocumentIndexAccessGuard(new DocumentCorpusCatalog(List.of()), aliases),
                documentService,
                mock(DocumentHybridSearchUseCase.class),
                mock(DocumentSearchAccessGuard.class));
    }
}
