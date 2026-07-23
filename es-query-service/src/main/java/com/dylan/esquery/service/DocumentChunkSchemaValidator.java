package com.dylan.esquery.service;

import com.dylan.esquery.document.DocumentCorpusDefinition;
import com.dylan.esquery.document.DocumentBusinessFieldValue;
import com.dylan.esquery.document.DocumentChunkCanonicalizer;
import com.dylan.esquery.document.DocumentIndexDefinition;
import com.dylan.esquery.document.DocumentBusinessFieldDefinition;
import org.springframework.stereotype.Component;

import java.net.URI;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.time.Instant;
import java.util.ArrayList;
import java.util.HashSet;
import java.util.HexFormat;
import java.util.List;
import java.util.Map;
import java.util.Set;

/** Schema v3 chunk gate：无版本猜测、Profile重复字段或隐式ACL继承。 */
@Component
public final class DocumentChunkSchemaValidator {
    private static final Set<String> REQUIRED = Set.of("tenantId", "documentId", "documentVersion", "chunkId",
            "chunkIndex", "charStart", "charEnd", "content", "chunkContentHash", "status", "aclRef", "aclVersion", "visibility");
    private static final Set<String> OPTIONAL = Set.of("title", "section", "page", "safeSourceUri", "sourceUpdatedAt",
            "userIds", "departmentIds", "roleIds", "attributeKeys", "embedding");
    private static final Set<String> PROHIBITED = Set.of("retrievalProfile", "schemaVersion", "indexVersion", "embeddingModel",
            "embeddingDimension", "snippet", "contextBefore", "contextAfter", "chunkAclOverride", "aclExpression",
            "token", "originalBinary", "providerRequest", "providerResponse");
    private static final Set<String> STATUSES = Set.of("ACTIVE", "REVOKED", "DELETED", "EXPIRED", "BLOCKED");
    private static final Set<String> VISIBILITIES = Set.of("TENANT", "USER", "DEPARTMENT", "ROLE", "ATTRIBUTE", "PUBLIC");

    public void validate(String ignoredIndex, Map<String, Object> document) {
        validate(document, Set.of(), null, Map.of());
    }

    public void validate(DocumentCorpusDefinition corpus, Map<String, Object> document, Integer vectorDimension) {
        if (corpus == null) throw new IllegalArgumentException("document corpus definition required");
        validate(document, corpus.indexedBusinessFields(), vectorDimension, Map.of());
    }

    public void validate(DocumentCorpusDefinition corpus, DocumentIndexDefinition schema, Map<String, Object> document) {
        if (corpus == null || schema == null || !corpus.schemaRef().equals(schema.schemaRef())) {
            throw new IllegalArgumentException("document corpus/schema binding required");
        }
        Map<String, DocumentBusinessFieldDefinition.Type> types = schema.businessFields().stream()
                .collect(java.util.stream.Collectors.toUnmodifiableMap(
                        DocumentBusinessFieldDefinition::name, DocumentBusinessFieldDefinition::type));
        validate(document, corpus.indexedBusinessFields(), schema.vectorDimension(), types);
    }

    private void validate(Map<String, Object> document, Set<String> businessFields, Integer vectorDimension,
                          Map<String, DocumentBusinessFieldDefinition.Type> businessTypes) {
        if (document == null || document.isEmpty()) throw new IllegalArgumentException("document chunk must not be empty");
        PROHIBITED.forEach(field -> { if (document.containsKey(field)) throw new IllegalArgumentException("document chunk contains prohibited field: " + field); });
        Set<String> allowed = new HashSet<>(REQUIRED);allowed.addAll(OPTIONAL);allowed.addAll(businessFields);
        document.keySet().forEach(field -> { if (!allowed.contains(field)) throw new IllegalArgumentException("document chunk contains unknown field: " + field); });
        REQUIRED.forEach(field -> requirePresent(document, field));
        for (String field : List.of("tenantId", "documentId", "documentVersion", "chunkId", "aclRef", "aclVersion")) requireText(document, field, 256);
        int chunkIndex = requireInteger(document, "chunkIndex", 0);int start = requireInteger(document, "charStart", 0);int end = requireInteger(document, "charEnd", 1);
        if (start >= end) throw new IllegalArgumentException("document chunk offsets invalid");
        String content = requireText(document, "content", 1_000_000);
        List<DocumentBusinessFieldValue> canonicalBusinessFields = businessFields.stream().filter(document::containsKey)
                .sorted().map(field -> businessValue(field, document.get(field), businessTypes.get(field))).toList();
        String expectedHash = DocumentChunkCanonicalizer.contentHash(content,
                document.get("title") instanceof String title ? title : null,
                document.get("section") instanceof String section ? section : null,
                canonicalBusinessFields);
        if (!expectedHash.equals(document.get("chunkContentHash"))) throw new IllegalArgumentException("document chunk content hash mismatch");
        if (!STATUSES.contains(document.get("status"))) throw new IllegalArgumentException("document chunk status invalid");
        String visibility = String.valueOf(document.get("visibility"));if (!VISIBILITIES.contains(visibility)) throw new IllegalArgumentException("document chunk visibility invalid");
        validatePrincipals(document, visibility);
        optionalText(document, "title", 4096);optionalText(document, "section", 4096);
        if (document.containsKey("page")) requireInteger(document, "page", 0);
        if (document.containsKey("sourceUpdatedAt")) Instant.parse(requireText(document, "sourceUpdatedAt", 128));
        if (document.containsKey("safeSourceUri")) safeUri(requireText(document, "safeSourceUri", 4096));
        Object embedding = document.get("embedding");
        if (vectorDimension == null && embedding != null) throw new IllegalArgumentException("document embedding not enabled by schema");
        if (vectorDimension != null) validateVector(embedding, vectorDimension);
        if (chunkIndex < 0) throw new IllegalArgumentException("document chunkIndex invalid");
    }

    private static void validatePrincipals(Map<String, Object> document, String visibility) {
        Map<String,String> byVisibility = Map.of("USER","userIds","DEPARTMENT","departmentIds","ROLE","roleIds","ATTRIBUTE","attributeKeys");
        for (String field : List.of("userIds", "departmentIds", "roleIds", "attributeKeys")) {
            List<String> values = strings(document.get(field), field);
            boolean required = field.equals(byVisibility.get(visibility));
            if (required && values.isEmpty()) throw new IllegalArgumentException("document ACL requires " + field);
            if (!required && !values.isEmpty()) throw new IllegalArgumentException("document ACL forbids unrelated " + field);
            if (values.size() > 1024 || new HashSet<>(values).size() != values.size()) throw new IllegalArgumentException("document ACL principals invalid");
            List<String> sorted = new ArrayList<>(values);sorted.sort(String::compareTo);
            if (!sorted.equals(values)) throw new IllegalArgumentException("document ACL principals must be sorted");
        }
    }

    private static DocumentBusinessFieldValue businessValue(String field, Object value,
                                                             DocumentBusinessFieldDefinition.Type type) {
        if (type == DocumentBusinessFieldDefinition.Type.KEYWORD) return new DocumentBusinessFieldValue.Keyword(field, requireBusinessText(field, value));
        if (type == DocumentBusinessFieldDefinition.Type.TEXT) return new DocumentBusinessFieldValue.Text(field, requireBusinessText(field, value));
        if (type == DocumentBusinessFieldDefinition.Type.DATE) {
            Instant instant = value instanceof Instant parsed ? parsed : Instant.parse(requireBusinessText(field, value));
            return new DocumentBusinessFieldValue.DateValue(field, instant);
        }
        if (type == DocumentBusinessFieldDefinition.Type.INTEGER) {
            if (!(value instanceof Number number) || number.doubleValue() != number.longValue()) throw new IllegalArgumentException("document business field value invalid: " + field);
            return new DocumentBusinessFieldValue.IntegerValue(field, number.longValue());
        }
        if (type == DocumentBusinessFieldDefinition.Type.BOOLEAN) {
            if (!(value instanceof Boolean booleanValue)) throw new IllegalArgumentException("document business field value invalid: " + field);
            return new DocumentBusinessFieldValue.BooleanValue(field, booleanValue);
        }
        if (value instanceof Boolean booleanValue) return new DocumentBusinessFieldValue.BooleanValue(field, booleanValue);
        if (value instanceof Byte || value instanceof Short || value instanceof Integer || value instanceof Long) {
            return new DocumentBusinessFieldValue.IntegerValue(field, ((Number) value).longValue());
        }
        if (value instanceof String text) return new DocumentBusinessFieldValue.Text(field, text);
        throw new IllegalArgumentException("document business field value invalid: " + field);
    }
    private static String requireBusinessText(String field, Object value) { if (!(value instanceof String text) || text.isBlank()) throw new IllegalArgumentException("document business field value invalid: " + field); return text; }

    private static List<String> strings(Object value, String field) {
        if (value == null) return List.of();if (!(value instanceof List<?> raw)) throw new IllegalArgumentException(field + " must be a list");
        List<String> values = new ArrayList<>();for (Object item : raw) { if (!(item instanceof String text) || text.isBlank()) throw new IllegalArgumentException(field + " invalid");values.add(text); }
        return List.copyOf(values);
    }
    private static void validateVector(Object value, int dimension) {if (!(value instanceof List<?> vector)||vector.size()!=dimension)throw new IllegalArgumentException("document embedding dimension mismatch");for(Object item:vector){if(!(item instanceof Number n)||!Double.isFinite(n.doubleValue()))throw new IllegalArgumentException("document embedding value invalid");}}
    private static void safeUri(String value) {URI uri=URI.create(value);if(!uri.isAbsolute()||uri.getUserInfo()!=null||uri.getQuery()!=null||uri.getFragment()!=null||!Set.of("http","https").contains(uri.getScheme().toLowerCase()))throw new IllegalArgumentException("document safeSourceUri invalid");}
    private static void optionalText(Map<String,Object> value,String field,int max){if(value.containsKey(field)&&value.get(field)!=null)requireText(value,field,max);}
    private static void requirePresent(Map<String,Object> value,String field){if(!value.containsKey(field)||value.get(field)==null)throw new IllegalArgumentException("document chunk missing required field: "+field);}
    private static String requireText(Map<String,Object> value,String field,int max){Object raw=value.get(field);if(!(raw instanceof String text)||text.isBlank()||text.codePointCount(0,text.length())>max)throw new IllegalArgumentException("document chunk field invalid: "+field);return text;}
    private static int requireInteger(Map<String,Object> value,String field,int min){Object raw=value.get(field);if(!(raw instanceof Number n)||n.doubleValue()!=n.intValue()||n.intValue()<min)throw new IllegalArgumentException("document chunk integer invalid: "+field);return n.intValue();}
}
