package com.dylan.esquery.document;

import com.dylan.esquery.service.DocumentIndexDefinitionValidator;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.elasticsearch.client.Request;
import org.elasticsearch.client.RestClient;

import java.time.Instant;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;

/** Seal 后 mapping/count/ACL/vector 技术证据检查；不产生 release approval。 */
public final class EsIndexTechnicalValidationPort implements IndexTechnicalValidationPort {
    private final RestClient client;
    private final ObjectMapper mapper;
    private final DocumentCorpusCatalog catalog;
    private final DocumentIndexDefinitionRegistry schemas;
    private final DocumentIndexDefinitionValidator mappingValidator;

    public EsIndexTechnicalValidationPort(RestClient client, ObjectMapper mapper, DocumentCorpusCatalog catalog,
                                          DocumentIndexDefinitionRegistry schemas,
                                          DocumentIndexDefinitionValidator mappingValidator) {
        this.client = client; this.mapper = mapper; this.catalog = catalog; this.schemas = schemas; this.mappingValidator = mappingValidator;
    }

    @Override
    public IndexTechnicalValidationEvidence validate(IndexBuildTargetHandle handle,
                                                     DocumentPhysicalIndexManifest manifest, Instant deadline) {
        if (deadline == null || !Instant.now().isBefore(deadline)) throw new DocumentRebuildFailure("TECHNICAL_VALIDATION_DEADLINE_EXCEEDED");
        List<String> diagnostics = new ArrayList<>();
        boolean mapping = false; boolean count = false; boolean acl = false; boolean vector = false;
        try {
            DocumentCorpusDefinition corpus = catalog.require(manifest.corpusKey());
            DocumentIndexDefinition schema = schemas.require(manifest.schemaRef());
            Request mappingRequest = new Request("GET", "/" + handle.physicalIndex() + "/_mapping");
            JsonNode mappingRoot = mapper.readTree(client.performRequest(mappingRequest).getEntity().getContent())
                    .path(handle.physicalIndex()).path("mappings");
            Map<String, Object> definition = Map.of("mappings", mapper.convertValue(mappingRoot, new TypeReference<>() { }));
            mappingValidator.validate(corpus, definition, schema.vectorDimension());
            mapping = true;
            long actualCount = count(handle.physicalIndex(), "{\"query\":{\"match_all\":{}}}");
            count = actualCount == manifest.chunkCount();
            if (!count) diagnostics.add("COUNT_MISMATCH");
            long aclViolations = count(handle.physicalIndex(), aclViolationQuery());
            acl = aclViolations == 0;
            if (!acl) diagnostics.add("ACL_CLOSURE_VIOLATION");
            if (schema.vectorEnabled()) {
                long missingVectors = count(handle.physicalIndex(), "{\"query\":{\"bool\":{\"must_not\":{\"exists\":{\"field\":\"embedding\"}}}}}");
                vector = missingVectors == 0;
                if (!vector) diagnostics.add("VECTOR_MISSING");
            } else {
                vector = true;
            }
        } catch (RuntimeException ex) {
            diagnostics.add("TECHNICAL_VALIDATION_EXCEPTION");
        } catch (Exception ex) {
            diagnostics.add("TECHNICAL_VALIDATION_IO_FAILURE");
        }
        return new IndexTechnicalValidationEvidence(manifest, mapping, acl, vector, count, diagnostics);
    }

    private long count(String index, String body) throws Exception {
        Request request = new Request("POST", "/" + index + "/_count"); request.setJsonEntity(body);
        return mapper.readTree(client.performRequest(request).getEntity().getContent()).path("count").asLong(-1);
    }

    private static String aclViolationQuery() {
        return """
                {"query":{"bool":{"should":[
                  {"bool":{"must_not":{"term":{"status":"ACTIVE"}}}},
                  {"bool":{"filter":{"term":{"visibility":"USER"}},"must_not":{"exists":{"field":"userIds"}}}},
                  {"bool":{"filter":{"term":{"visibility":"DEPARTMENT"}},"must_not":{"exists":{"field":"departmentIds"}}}},
                  {"bool":{"filter":{"term":{"visibility":"ROLE"}},"must_not":{"exists":{"field":"roleIds"}}}},
                  {"bool":{"filter":{"term":{"visibility":"ATTRIBUTE"}},"must_not":{"exists":{"field":"attributeKeys"}}}},
                  {"bool":{"filter":{"terms":{"visibility":["TENANT","PUBLIC"]}},"must":{"bool":{"should":[
                    {"exists":{"field":"userIds"}},{"exists":{"field":"departmentIds"}},
                    {"exists":{"field":"roleIds"}},{"exists":{"field":"attributeKeys"}}
                  ],"minimum_should_match":1}}}}
                ],"minimum_should_match":1}}}
                """;
    }
}
