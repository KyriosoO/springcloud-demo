package com.dylan.esquery.service;

import com.dylan.esquery.api.model.DocumentCorpusKeyDto;
import com.dylan.esquery.api.model.DocumentSchemaRefDto;
import com.dylan.esquery.document.DocumentCorpusDefinition;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;

import java.util.List;
import java.util.Map;
import java.util.Set;

import static org.assertj.core.api.Assertions.assertThatCode;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class DocumentIndexDefinitionValidatorTest {
    private final ObjectMapper objectMapper = new ObjectMapper();
    private final DocumentIndexDefinitionValidator validator = new DocumentIndexDefinitionValidator();

    @Test
    void acceptsStrictSchemaV3Mapping() throws Exception {
        assertThatCode(() -> validator.validate("ignored", validMapping())).doesNotThrowAnyException();
    }

    @Test
    void rejectsDynamicOrLegacyProfileField() throws Exception {
        Map<String,Object> dynamic = validMapping();mappings(dynamic).put("dynamic", true);
        assertThatThrownBy(() -> validator.validate("ignored", dynamic)).hasMessageContaining("dynamic");
        Map<String,Object> legacy = validMapping();properties(legacy).put("retrievalProfile", Map.of("type", "keyword"));
        assertThatThrownBy(() -> validator.validate("ignored", legacy)).hasMessageContaining("prohibited");
    }

    @Test
    void validatesFrozenVectorDimensionAndSourceExclusion() throws Exception {
        Map<String,Object> mapping = validMapping();
        mappings(mapping).put("_source", Map.of("excludes", List.of("embedding")));
        properties(mapping).put("embedding", Map.of("type", "dense_vector", "dims", 3));
        assertThatCode(() -> validator.validate(corpus(), mapping, 3)).doesNotThrowAnyException();
        properties(mapping).put("embedding", Map.of("type", "dense_vector", "dims", 2));
        assertThatThrownBy(() -> validator.validate(corpus(), mapping, 3)).hasMessageContaining("dims mismatch");
    }

    private DocumentCorpusDefinition corpus(){return new DocumentCorpusDefinition(new DocumentCorpusKeyDto("policy","document"),
            "agent-doc-policy-read",new DocumentSchemaRefDto("document","v3","1".repeat(64)),"standard","vector-v1","chunk-v1","source-1",Set.of());}
    private Map<String,Object> validMapping() throws Exception {return objectMapper.readValue(getClass().getResourceAsStream("/fixtures/document/valid-document-index-definition.json"),new TypeReference<>(){});}
    @SuppressWarnings("unchecked") private Map<String,Object> mappings(Map<String,Object> value){return (Map<String,Object>)value.get("mappings");}
    @SuppressWarnings("unchecked") private Map<String,Object> properties(Map<String,Object> value){return (Map<String,Object>)mappings(value).get("properties");}
}
