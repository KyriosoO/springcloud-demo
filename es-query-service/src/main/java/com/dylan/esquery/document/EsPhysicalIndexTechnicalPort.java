package com.dylan.esquery.document;

import com.dylan.esquery.api.model.DocumentCorpusKeyDto;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.elasticsearch.client.Request;
import org.elasticsearch.client.ResponseException;
import org.elasticsearch.client.RestClient;
import org.springframework.jdbc.core.JdbcTemplate;

import java.time.Instant;
import java.util.ArrayList;
import java.util.List;

/** 仅提供技术事实与授权删除；不运行自动 retention job。 */
public final class EsPhysicalIndexTechnicalPort implements PhysicalIndexTechnicalPort {
    private final RestClient client;
    private final ObjectMapper mapper;
    private final JdbcTemplate jdbc;

    public EsPhysicalIndexTechnicalPort(RestClient client, ObjectMapper mapper, JdbcTemplate jdbc) {
        this.client = client; this.mapper = mapper; this.jdbc = jdbc;
    }

    @Override
    public List<String> listPhysicalIndexCandidates(DocumentCorpusKeyDto corpusKey) {
        String pattern = "agent-doc-" + corpusKey.domain().replace('.', '-') + "-" + corpusKey.materialType().replace('.', '-') + "-s*-*";
        try {
            Request request = new Request("GET", "/_cat/indices/" + pattern + "?format=json&h=index");
            JsonNode response = mapper.readTree(client.performRequest(request).getEntity().getContent());
            List<String> values = new ArrayList<>();
            response.forEach(item -> { String value = item.path("index").asText(null); if (value != null) values.add(value); });
            values.sort(String::compareTo);
            return List.copyOf(values);
        } catch (Exception ex) { throw new IllegalStateException("document physical index listing failed", ex); }
    }

    @Override
    public PhysicalIndexReferenceInspection inspectReferences(String physicalIndex) {
        if (physicalIndex == null || !physicalIndex.startsWith("agent-doc-")) throw new IllegalArgumentException("document physical index invalid");
        try {
            List<String> aliases = new ArrayList<>();
            try {
                JsonNode aliasRoot = mapper.readTree(client.performRequest(new Request("GET", "/" + physicalIndex + "/_alias"))
                        .getEntity().getContent()).path(physicalIndex).path("aliases");
                aliasRoot.fieldNames().forEachRemaining(aliases::add);
            } catch (ResponseException ex) {
                if (ex.getResponse().getStatusLine().getStatusCode() != 404) throw ex;
            }
            aliases.sort(String::compareTo);
            int unfinished = jdbc.queryForObject("SELECT COUNT(*) FROM document_index_rebuild_task WHERE target_physical_index_safe_ref=? AND status IN ('PENDING','RUNNING')",
                    Integer.class, physicalIndex);
            JsonNode manifest = mapper.readTree(client.performRequest(new Request("GET", "/" + physicalIndex + "/_mapping"))
                    .getEntity().getContent()).path(physicalIndex).path("mappings").path("_meta").path("agent_document_manifest");
            return new PhysicalIndexReferenceInspection(physicalIndex, aliases, unfinished > 0,
                    manifest.path("manifestDigest").asText(null), manifest.path("attestationDigest").asText(null));
        } catch (Exception ex) { throw new IllegalStateException("document physical index reference inspection failed", ex); }
    }

    @Override
    public void deletePhysicalIndex(AuthorizedIndexDeletionCommand command) {
        if (!Instant.now().isBefore(command.deadline())) throw new IllegalStateException("authorized index deletion deadline reached");
        String expectedPrefix = "agent-doc-" + command.corpusKey().domain().replace('.', '-') + "-"
                + command.corpusKey().materialType().replace('.', '-') + "-s";
        if (!command.physicalIndex().startsWith(expectedPrefix)) throw new IllegalArgumentException("index deletion corpus binding mismatch");
        PhysicalIndexReferenceInspection inspection = inspectReferences(command.physicalIndex());
        if (!inspection.deletionSafe() || !command.expectedManifestDigest().equals(inspection.manifestDigest())) {
            throw new IllegalStateException("document physical index is still referenced or binding changed");
        }
        try { client.performRequest(new Request("DELETE", "/" + command.physicalIndex())); }
        catch (Exception ex) { throw new IllegalStateException("authorized document physical index deletion failed", ex); }
    }
}
