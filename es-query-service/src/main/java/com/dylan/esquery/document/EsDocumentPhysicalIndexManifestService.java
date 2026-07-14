package com.dylan.esquery.document;

import com.dylan.esquery.api.model.DocumentCorpusKeyDto;
import com.dylan.esquery.api.model.DocumentSchemaRefDto;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.elasticsearch.client.Request;
import org.elasticsearch.client.Response;
import org.elasticsearch.client.ResponseException;
import org.elasticsearch.client.RestClient;

import java.io.IOException;
import java.nio.ByteBuffer;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.time.Instant;
import java.util.HexFormat;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.Optional;

/** Manifest 一次 seal、write block 与 readback 的 ES 实现。 */
public final class EsDocumentPhysicalIndexManifestService implements DocumentPhysicalIndexManifestService {
    private final RestClient client;
    private final ObjectMapper mapper;

    public EsDocumentPhysicalIndexManifestService(RestClient client, ObjectMapper mapper) {
        this.client = client; this.mapper = mapper;
    }

    @Override
    public DocumentPhysicalIndexManifest seal(IndexBuildTargetHandle handle, DocumentRebuildTaskLease lease,
                                              DocumentCorpusDefinition corpus, DocumentIndexDefinition schema,
                                              long documentCount, long chunkCount, String indexContentDigest, Instant now) {
        requireBinding(handle, lease);
        String sourceRef = lease.sourceSnapshotRef().snapshotId() + ":" + lease.sourceSnapshotRef().version();
        DocumentPhysicalIndexManifest unsigned = new DocumentPhysicalIndexManifest(handle.physicalIndex(),
                corpus.corpusKey(), schema.schemaRef(), corpus.analyzerRef(), corpus.vectorPolicyRef(),
                corpus.chunkStrategyRef(), sourceRef, lease.sourceSnapshotRef().canonicalDigest(), lease.taskId(),
                documentCount, chunkCount, indexContentDigest, now, "0".repeat(64));
        DocumentPhysicalIndexManifest manifest = new DocumentPhysicalIndexManifest(handle.physicalIndex(),
                corpus.corpusKey(), schema.schemaRef(), corpus.analyzerRef(), corpus.vectorPolicyRef(),
                corpus.chunkStrategyRef(), sourceRef, lease.sourceSnapshotRef().canonicalDigest(), lease.taskId(),
                documentCount, chunkCount, indexContentDigest, now, manifestDigest(unsigned));
        Map<String, Object> meta = toMeta(manifest, schema);
        try {
            Request mapping = new Request("PUT", "/" + handle.physicalIndex() + "/_mapping");
            mapping.setJsonEntity(mapper.writeValueAsString(Map.of("_meta", Map.of(
                    "agent_document_build", Map.of("taskId", lease.taskId(), "sealed", true),
                    "agent_document_manifest", meta))));
            client.performRequest(mapping);
            Request block = new Request("PUT", "/" + handle.physicalIndex() + "/_settings");
            block.setJsonEntity("{\"index.blocks.write\":true}");
            client.performRequest(block);
            DocumentPhysicalIndexManifest reread = requireSealed(handle, now.plusSeconds(30));
            if (!manifest.equals(reread)) throw new DocumentRebuildFailure("MANIFEST_READBACK_MISMATCH");
            return manifest;
        } catch (DocumentRebuildFailure failure) {
            throw failure;
        } catch (IOException ex) {
            throw new DocumentRebuildFailure("MANIFEST_SEAL_FAILED", ex);
        }
    }

    @Override
    public DocumentPhysicalIndexManifest requireSealed(IndexBuildTargetHandle handle, Instant deadline) {
        return findSealed(handle, deadline)
                .orElseThrow(() -> new DocumentRebuildFailure("MANIFEST_NOT_SEALED"));
    }

    @Override
    public Optional<DocumentPhysicalIndexManifest> findSealed(IndexBuildTargetHandle handle, Instant deadline) {
        if (handle == null || deadline == null || !Instant.now().isBefore(deadline)) throw new DocumentRebuildFailure("MANIFEST_READ_DEADLINE_EXCEEDED");
        try {
            Response response = client.performRequest(new Request("GET", "/" + handle.physicalIndex() + "/_mapping"));
            JsonNode meta = mapper.readTree(response.getEntity().getContent()).path(handle.physicalIndex())
                    .path("mappings").path("_meta").path("agent_document_manifest");
            if (!meta.isObject() || !meta.path("sealed").asBoolean(false)) return Optional.empty();
            JsonNode settings = mapper.readTree(client.performRequest(new Request("GET", "/" + handle.physicalIndex()
                    + "/_settings?flat_settings=true")).getEntity().getContent());
            if (!"true".equals(settings.path(handle.physicalIndex()).path("settings")
                    .path("index.blocks.write").asText(null))) throw new DocumentRebuildFailure("MANIFEST_WRITE_BLOCK_MISSING");
            String taskId = text(meta, "taskId");
            if (!handle.taskId().equals(taskId)) throw new DocumentRebuildFailure("MANIFEST_TASK_BINDING_MISMATCH");
            DocumentPhysicalIndexManifest manifest = new DocumentPhysicalIndexManifest(handle.physicalIndex(),
                    new DocumentCorpusKeyDto(text(meta, "domain"), text(meta, "materialType")),
                    new DocumentSchemaRefDto(text(meta, "schemaName"), text(meta, "schemaVersion"), text(meta, "schemaDigest")),
                    text(meta, "analyzerRef"), text(meta, "vectorPolicyRef"), text(meta, "chunkStrategyRef"),
                    text(meta, "sourceSnapshotRef"), text(meta, "sourceSnapshotDigest"), taskId,
                    positiveOrZero(meta, "documentCount"), positiveOrZero(meta, "chunkCount"),
                    text(meta, "indexContentDigest"), Instant.parse(text(meta, "sealedAt")), text(meta, "manifestDigest"));
            if (!manifest.manifestDigest().equals(manifestDigest(manifest))) {
                throw new DocumentRebuildFailure("MANIFEST_DIGEST_MISMATCH");
            }
            return Optional.of(manifest);
        } catch (DocumentRebuildFailure failure) {
            throw failure;
        } catch (ResponseException ex) {
            if (ex.getResponse().getStatusLine().getStatusCode() == 404) return Optional.empty();
            throw new DocumentRebuildFailure("MANIFEST_READ_FAILED", ex);
        } catch (IOException ex) {
            throw new DocumentRebuildFailure("MANIFEST_READ_FAILED", ex);
        } catch (RuntimeException ex) {
            throw new DocumentRebuildFailure("MANIFEST_FIELD_INVALID", ex);
        }
    }

    private static Map<String, Object> toMeta(DocumentPhysicalIndexManifest manifest, DocumentIndexDefinition schema) {
        Map<String, Object> value = new LinkedHashMap<>();
        value.put("sealed", true); value.put("domain", manifest.corpusKey().domain());
        value.put("materialType", manifest.corpusKey().materialType()); value.put("schemaName", manifest.schemaRef().name());
        value.put("schemaVersion", manifest.schemaRef().version()); value.put("schemaDigest", manifest.schemaRef().canonicalDigest());
        value.put("analyzerRef", manifest.analyzerRef()); value.put("vectorPolicyRef", manifest.vectorPolicyRef());
        value.put("chunkStrategyRef", manifest.chunkStrategyRef()); value.put("sourceSnapshotRef", manifest.sourceSnapshotRef());
        value.put("sourceSnapshotDigest", manifest.sourceSnapshotDigest()); value.put("taskId", manifest.taskId());
        value.put("documentCount", manifest.documentCount()); value.put("chunkCount", manifest.chunkCount());
        value.put("indexContentDigest", manifest.indexContentDigest()); value.put("sealedAt", manifest.sealedAt().toString());
        value.put("manifestDigest", manifest.manifestDigest());
        if (schema.vectorEnabled()) {
            value.put("vectorField", "embedding"); value.put("vectorDimension", schema.vectorDimension());
            value.put("vectorBindingDigest", digest("VECTOR-1", manifest.vectorPolicyRef(), schema.schemaRef().canonicalDigest(),
                    Integer.toString(schema.vectorDimension()), schema.vectorSimilarity()));
        }
        return Map.copyOf(value);
    }

    private static void requireBinding(IndexBuildTargetHandle handle, DocumentRebuildTaskLease lease) {
        if (handle == null || lease == null || !handle.taskId().equals(lease.taskId())
                || !handle.physicalIndex().equals(lease.targetPhysicalIndexSafeRef())) throw new DocumentRebuildFailure("MANIFEST_HANDLE_BINDING_INVALID");
    }
    private static String text(JsonNode node, String field) { String value = node.path(field).asText(null); if (value == null || value.isBlank()) throw new DocumentRebuildFailure("MANIFEST_FIELD_INVALID"); return value; }
    private static long positiveOrZero(JsonNode node, String field) { long value = node.path(field).asLong(-1); if (value < 0) throw new DocumentRebuildFailure("MANIFEST_COUNT_INVALID"); return value; }
    private static String manifestDigest(DocumentPhysicalIndexManifest manifest) {
        return digest("MANIFEST-1", manifest.physicalIndex(), manifest.corpusKey().domain(),
                manifest.corpusKey().materialType(), manifest.schemaRef().name(), manifest.schemaRef().version(),
                manifest.schemaRef().canonicalDigest(), manifest.analyzerRef(), manifest.vectorPolicyRef(),
                manifest.chunkStrategyRef(), manifest.sourceSnapshotRef(), manifest.sourceSnapshotDigest(),
                manifest.taskId(), Long.toString(manifest.documentCount()), Long.toString(manifest.chunkCount()),
                manifest.indexContentDigest(), manifest.sealedAt().toString());
    }
    private static String digest(String... values) {
        try { MessageDigest digest = MessageDigest.getInstance("SHA-256"); for (String value : values) { byte[] bytes = value.getBytes(StandardCharsets.UTF_8); digest.update(ByteBuffer.allocate(4).putInt(bytes.length).array()); digest.update(bytes); } return HexFormat.of().formatHex(digest.digest()); }
        catch (Exception ex) { throw new IllegalStateException("SHA-256 unavailable", ex); }
    }
}
