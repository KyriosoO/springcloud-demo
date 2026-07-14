package com.dylan.esquery.document;

import com.dylan.esquery.api.model.DocumentCorpusKeyDto;
import com.dylan.esquery.api.model.DocumentRebuildTaskView;
import com.dylan.esquery.api.model.StartDocumentRebuildRequest;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.HexFormat;

/** Document FULL_SNAPSHOT rebuild 的专用入口。 */
public final class DocumentIndexRebuildService {
    private final DocumentCorpusCatalog catalog;
    private final DocumentRebuildTaskRepository repository;
    public DocumentIndexRebuildService(DocumentCorpusCatalog catalog, DocumentRebuildTaskRepository repository) { this.catalog = catalog; this.repository = repository; }

    public DocumentRebuildTaskView start(DocumentCorpusKeyDto key, StartDocumentRebuildRequest request, String managementScope) {
        DocumentCorpusDefinition definition = catalog.require(key);
        if (!definition.schemaRef().equals(request.expectedSchemaRef())) throw new IllegalStateException("SCHEMA_ASSERTION_CONFLICT");
        String idempotency = digest("IDEMKEY-1", managementScope, request.idempotencyKey());
        String semantic = digest("IDEMREQ-1", key.domain(), key.materialType(), request.sourceSnapshotRef().canonicalDigest(), request.expectedSchemaRef().canonicalDigest(), String.valueOf(request.expectedDocumentCount()));
        String buildId = semantic.substring(0, 12);
        String safeTarget = "agent-doc-" + key.domain().replace('.', '-') + "-" + key.materialType().replace('.', '-') + "-s3-" + buildId;
        return repository.createOrGet(definition, request, safeTarget, idempotency, semantic);
    }

    private static String digest(String... parts) {
        try {
            MessageDigest md = MessageDigest.getInstance("SHA-256");
            for (String part : parts) { byte[] bytes = String.valueOf(part).getBytes(StandardCharsets.UTF_8); md.update(java.nio.ByteBuffer.allocate(4).putInt(bytes.length).array()); md.update(bytes); }
            return HexFormat.of().formatHex(md.digest());
        } catch (Exception ex) { throw new IllegalStateException("SHA-256 unavailable", ex); }
    }
}
