package com.dylan.esquery.document;

import com.dylan.esquery.api.model.DocumentCorpusKeyDto;
import com.dylan.esquery.api.model.DocumentTargetBindingDto;
import com.dylan.esquery.service.EsIndexAliasService;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.elasticsearch.client.Request;
import org.elasticsearch.client.Response;
import org.elasticsearch.client.RestClient;

import java.io.IOException;

/** 每次在线请求读取 alias actual、manifest 与 release attestation，不缓存 current target。 */
public final class DocumentIndexTargetResolver {
    private final DocumentCorpusCatalog catalog;
    private final EsIndexAliasService aliases;
    private final RestClient restClient;
    private final ObjectMapper objectMapper;

    public DocumentIndexTargetResolver(
            DocumentCorpusCatalog catalog,
            EsIndexAliasService aliases,
            RestClient restClient,
            ObjectMapper objectMapper) {
        this.catalog = catalog;
        this.aliases = aliases;
        this.restClient = restClient;
        this.objectMapper = objectMapper;
    }

    public ResolvedIndexTargetRef resolve(DocumentCorpusKeyDto key) throws IOException {
        DocumentCorpusDefinition corpus = catalog.require(key);
        var actual = aliases.readCurrent(corpus.readAlias());
        if (actual.targets().isEmpty()) throw new IllegalStateException("document read target is missing");
        if (actual.targets().size() != 1) throw new IllegalStateException("document read target is ambiguous");
        String physicalIndex = actual.targets().getFirst();
        if (!physicalIndex.startsWith("agent-doc-")) {
            throw new IllegalStateException("document alias points to foreign target");
        }
        Request request = new Request("GET", "/" + physicalIndex + "/_mapping");
        Response response = restClient.performRequest(request);
        JsonNode meta = objectMapper.readTree(response.getEntity().getContent())
                .path(physicalIndex).path("mappings").path("_meta").path("agent_document_manifest");
        if (!meta.isObject() || !meta.path("sealed").asBoolean(false)) {
            throw new IllegalStateException("document target manifest is missing or unsealed");
        }
        if (!key.domain().equals(text(meta, "domain"))
                || !key.materialType().equals(text(meta, "materialType"))
                || !corpus.schemaRef().version().equals(text(meta, "schemaVersion"))) {
            throw new IllegalStateException("document target corpus/schema binding mismatch");
        }
        DocumentTargetBindingDto binding = new DocumentTargetBindingDto(
                text(meta, "schemaVersion"), text(meta, "indexContentDigest"),
                text(meta, "manifestDigest"), text(meta, "attestationDigest"));
        return new ResolvedIndexTargetRef(
                key, corpus.readAlias(), physicalIndex, binding, text(meta, "validationReportRef"),
                optionalText(meta, "vectorField"), optionalPositiveInt(meta, "vectorDimension"),
                optionalText(meta, "vectorBindingDigest"));
    }

    private static String text(JsonNode node, String field) {
        String value = node.path(field).asText(null);
        if (value == null || value.isBlank()) throw new IllegalStateException("document manifest missing " + field);
        return value;
    }

    private static String optionalText(JsonNode node,String field){String value=node.path(field).asText(null);return value==null||value.isBlank()?null:value;}
    private static Integer optionalPositiveInt(JsonNode node,String field){JsonNode value=node.path(field);return value.isIntegralNumber()&&value.asInt()>0?value.asInt():null;}
}
