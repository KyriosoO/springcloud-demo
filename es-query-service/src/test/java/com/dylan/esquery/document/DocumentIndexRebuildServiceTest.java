package com.dylan.esquery.document;

import com.dylan.esquery.api.model.DocumentCorpusKeyDto;
import com.dylan.esquery.api.model.DocumentRebuildTaskView;
import com.dylan.esquery.api.model.DocumentSchemaRefDto;
import com.dylan.esquery.api.model.SourceSnapshotRef;
import com.dylan.esquery.api.model.StartDocumentRebuildRequest;
import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;

import java.util.List;
import java.util.Set;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

class DocumentIndexRebuildServiceTest {

    private static final DocumentCorpusKeyDto KEY = new DocumentCorpusKeyDto("policy", "document");
    private static final DocumentSchemaRefDto SCHEMA =
            new DocumentSchemaRefDto("document", "3", "a".repeat(64));

    @Test
    void rejectsSchemaAssertionConflictBeforeCreatingTask() {
        DocumentRebuildTaskRepository repository = mock(DocumentRebuildTaskRepository.class);
        DocumentIndexRebuildService service = new DocumentIndexRebuildService(catalog(), repository);

        assertThatThrownBy(() -> service.start(KEY, request(
                new DocumentSchemaRefDto("document", "4", "b".repeat(64))), "management"))
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("SCHEMA_ASSERTION_CONFLICT");
        org.mockito.Mockito.verifyNoInteractions(repository);
    }

    @Test
    void derivesPhysicalTargetAndOpaqueIdempotencyDigestsServerSide() {
        DocumentRebuildTaskRepository repository = mock(DocumentRebuildTaskRepository.class);
        DocumentRebuildTaskView view = mock(DocumentRebuildTaskView.class);
        when(repository.createOrGet(any(), any(), any(), any(), any())).thenReturn(view);
        DocumentIndexRebuildService service = new DocumentIndexRebuildService(catalog(), repository);

        assertThat(service.start(KEY, request(SCHEMA), "management")).isSameAs(view);

        ArgumentCaptor<String> target = ArgumentCaptor.forClass(String.class);
        ArgumentCaptor<String> idempotency = ArgumentCaptor.forClass(String.class);
        ArgumentCaptor<String> semantic = ArgumentCaptor.forClass(String.class);
        verify(repository).createOrGet(
                org.mockito.ArgumentMatchers.argThat(definition -> KEY.equals(definition.corpusKey())), any(), target.capture(),
                idempotency.capture(), semantic.capture());
        assertThat(target.getValue()).matches("agent-doc-policy-document-s3-[0-9a-f]{12}");
        assertThat(idempotency.getValue()).matches("[0-9a-f]{64}");
        assertThat(semantic.getValue()).matches("[0-9a-f]{64}");
    }

    private static DocumentCorpusCatalog catalog() {
        return new DocumentCorpusCatalog(List.of(new DocumentCorpusDefinition(
                KEY, "agent-doc-policy-document-read", SCHEMA,
                "ik-v1", "vector-v1", "chunk-v1", "connector-v1", Set.of("title"))));
    }

    private static StartDocumentRebuildRequest request(DocumentSchemaRefDto schema) {
        return new StartDocumentRebuildRequest(
                "req-1", "idem-1",
                new SourceSnapshotRef("snapshot-1", "v1", "c".repeat(64)),
                schema, 10L);
    }
}
