package com.dylan.esquery.document;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.apache.http.entity.ContentType;
import org.apache.http.nio.entity.NStringEntity;
import org.elasticsearch.client.Request;
import org.elasticsearch.client.Response;
import org.elasticsearch.client.ResponseException;
import org.elasticsearch.client.RestClient;

import java.io.IOException;
import java.nio.ByteBuffer;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.time.Instant;
import java.util.ArrayList;
import java.util.HexFormat;
import java.util.List;
import java.util.Map;

/** RestClient document build writer；所有方法都校验 task-issued handle/lease binding。 */
public final class EsIndexBuildWriter implements IndexBuildWriter {
    private final RestClient client;
    private final ObjectMapper mapper;
    private final DocumentIndexDefinitionJsonFactory definitions;
    private final DocumentChunkDocumentMapper chunks;

    public EsIndexBuildWriter(RestClient client, ObjectMapper mapper,
                              DocumentIndexDefinitionJsonFactory definitions, DocumentChunkDocumentMapper chunks) {
        this.client = client; this.mapper = mapper; this.definitions = definitions; this.chunks = chunks;
    }

    @Override
    public IndexBuildTargetHandle open(DocumentRebuildTaskLease lease, DocumentIndexDefinition definition, Instant deadline) {
        requireDeadline(deadline);
        IndexBuildTargetHandle handle = new IndexBuildTargetHandle(lease.taskId(), lease.targetPhysicalIndexSafeRef());
        try {
            if (exists(handle.physicalIndex())) {
                verifyRecoveryBinding(handle);
                return handle;
            }
            Request request = new Request("PUT", "/" + handle.physicalIndex());
            request.setJsonEntity(mapper.writeValueAsString(definitions.createBody(definition, lease.taskId())));
            client.performRequest(request);
            return handle;
        } catch (IOException ex) {
            throw new DocumentRebuildFailure("INDEX_CREATE_FAILED", ex);
        }
    }

    @Override
    public void write(IndexBuildTargetHandle handle, DocumentRebuildTaskLease lease,
                      List<NormalizedDocumentChunk> batch, Instant deadline) {
        requireBinding(handle, lease); requireDeadline(deadline);
        try {
            StringBuilder body = new StringBuilder();
            for (NormalizedDocumentChunk chunk : batch) {
                body.append(mapper.writeValueAsString(Map.of("index", Map.of("_index", handle.physicalIndex(), "_id", chunk.chunkId())))).append('\n');
                body.append(mapper.writeValueAsString(chunks.toDocument(chunk))).append('\n');
            }
            Request request = new Request("POST", "/_bulk");
            request.setEntity(new NStringEntity(body.toString(), ContentType.create("application/x-ndjson", StandardCharsets.UTF_8)));
            JsonNode response = read(client.performRequest(request));
            if (response.path("errors").asBoolean(true)) throw new DocumentRebuildFailure("BULK_PARTIAL_FAILURE");
            if (response.path("items").size() != batch.size()) throw new DocumentRebuildFailure("BULK_RESPONSE_COUNT_MISMATCH");
        } catch (DocumentRebuildFailure failure) {
            throw failure;
        } catch (IOException ex) {
            throw new DocumentRebuildFailure("BULK_TRANSPORT_FAILURE", ex);
        }
    }

    @Override public void refresh(IndexBuildTargetHandle handle, DocumentRebuildTaskLease lease, Instant deadline) {
        performNoBody("POST", "/" + target(handle, lease) + "/_refresh", deadline, "INDEX_REFRESH_FAILED");
    }

    @Override public long count(IndexBuildTargetHandle handle, DocumentRebuildTaskLease lease, Instant deadline) {
        requireBinding(handle, lease); requireDeadline(deadline);
        try { return read(client.performRequest(new Request("GET", "/" + handle.physicalIndex() + "/_count"))).path("count").asLong(-1); }
        catch (IOException ex) { throw new DocumentRebuildFailure("INDEX_COUNT_FAILED", ex); }
    }

    @Override
    public String contentDigest(IndexBuildTargetHandle handle, DocumentRebuildTaskLease lease,
                                DocumentCorpusDefinition corpus, DocumentIndexDefinition schema, Instant deadline) {
        requireBinding(handle, lease); requireDeadline(deadline);
        String scrollId = null;
        try {
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            update(digest, "ICD-1", corpus.corpusKey().domain(), corpus.corpusKey().materialType(),
                    lease.sourceSnapshotRef().canonicalDigest(), schema.schemaRef().canonicalDigest());
            Request first = new Request("POST", "/" + handle.physicalIndex() + "/_search?scroll=1m");
            first.setJsonEntity("{\"size\":1000,\"_source\":[\"chunkId\",\"chunkContentHash\"],\"sort\":[{\"tenantId\":\"asc\"},{\"documentId\":\"asc\"},{\"documentVersion\":\"asc\"},{\"chunkIndex\":\"asc\"}]}");
            JsonNode page = read(client.performRequest(first));
            while (true) {
                scrollId = page.path("_scroll_id").asText(scrollId);
                JsonNode hits = page.path("hits").path("hits");
                if (!hits.isArray() || hits.isEmpty()) break;
                for (JsonNode hit : hits) {
                    JsonNode source = hit.path("_source");
                    String chunkId = required(source, "chunkId");
                    String contentHash = required(source, "chunkContentHash");
                    update(digest, chunkId + ":" + contentHash);
                }
                Request next = new Request("POST", "/_search/scroll");
                next.setJsonEntity(mapper.writeValueAsString(Map.of("scroll", "1m", "scroll_id", scrollId)));
                page = read(client.performRequest(next));
            }
            return HexFormat.of().formatHex(digest.digest());
        } catch (DocumentRebuildFailure failure) {
            throw failure;
        } catch (Exception ex) {
            throw new DocumentRebuildFailure("INDEX_CONTENT_DIGEST_FAILED", ex);
        } finally {
            if (scrollId != null) clearScroll(scrollId);
        }
    }

    private boolean exists(String index) throws IOException {
        try { client.performRequest(new Request("HEAD", "/" + index)); return true; }
        catch (ResponseException ex) { if (ex.getResponse().getStatusLine().getStatusCode() == 404) return false; throw ex; }
    }

    private void verifyRecoveryBinding(IndexBuildTargetHandle handle) throws IOException {
        JsonNode response = read(client.performRequest(new Request("GET", "/" + handle.physicalIndex() + "/_mapping")));
        String taskId = response.path(handle.physicalIndex()).path("mappings").path("_meta")
                .path("agent_document_build").path("taskId").asText(null);
        boolean sealed = response.path(handle.physicalIndex()).path("mappings").path("_meta")
                .path("agent_document_manifest").path("sealed").asBoolean(false);
        if (!handle.taskId().equals(taskId) || sealed) throw new DocumentRebuildFailure("INDEX_RECOVERY_BINDING_CONFLICT");
    }

    private void clearScroll(String scrollId) {
        try { Request request = new Request("DELETE", "/_search/scroll"); request.setJsonEntity("{\"scroll_id\":\"" + scrollId + "\"}"); client.performRequest(request); }
        catch (Exception ignored) { /* scroll TTL 是安全兜底；不改变已计算 digest。 */ }
    }
    private void performNoBody(String method, String endpoint, Instant deadline, String code) {
        requireDeadline(deadline); try { client.performRequest(new Request(method, endpoint)); }
        catch (IOException ex) { throw new DocumentRebuildFailure(code, ex); }
    }
    private String target(IndexBuildTargetHandle handle, DocumentRebuildTaskLease lease) { requireBinding(handle, lease); return handle.physicalIndex(); }
    private static void requireBinding(IndexBuildTargetHandle handle, DocumentRebuildTaskLease lease) {
        if (handle == null || lease == null || !handle.taskId().equals(lease.taskId())
                || !handle.physicalIndex().equals(lease.targetPhysicalIndexSafeRef())) throw new DocumentRebuildFailure("INDEX_BUILD_HANDLE_BINDING_INVALID");
    }
    private static void requireDeadline(Instant deadline) { if (deadline == null || !Instant.now().isBefore(deadline)) throw new DocumentRebuildFailure("INDEX_BUILD_DEADLINE_EXCEEDED"); }
    private JsonNode read(Response response) throws IOException { return mapper.readTree(response.getEntity().getContent()); }
    private static String required(JsonNode node, String field) { String value = node.path(field).asText(null); if (value == null || value.isBlank()) throw new DocumentRebuildFailure("INDEX_DIGEST_SOURCE_INVALID"); return value; }
    private static void update(MessageDigest digest, String... values) { for (String value : values) { byte[] bytes = value.getBytes(StandardCharsets.UTF_8); digest.update(ByteBuffer.allocate(4).putInt(bytes.length).array()); digest.update(bytes); } }
}
