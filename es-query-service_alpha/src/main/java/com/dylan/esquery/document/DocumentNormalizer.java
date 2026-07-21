package com.dylan.esquery.document;

import java.net.URI;
import java.text.Normalizer;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashSet;
import java.util.List;
import java.util.Set;

/** 与 ES/Provider/Runtime 解耦的确定性文档规范化器。 */
public final class DocumentNormalizer {
    private static final Set<String> STATUSES = Set.of("ACTIVE", "REVOKED", "DELETED", "EXPIRED", "BLOCKED");
    private static final Set<String> VISIBILITIES = Set.of("TENANT", "USER", "DEPARTMENT", "ROLE", "ATTRIBUTE", "PUBLIC");
    private final int maxContentCodePoints;

    public DocumentNormalizer(int maxContentCodePoints) {
        if (maxContentCodePoints <= 0) throw new IllegalArgumentException("maxContentCodePoints must be positive");
        this.maxContentCodePoints = maxContentCodePoints;
    }

    public NormalizedDocument normalize(SourceDocument source, DocumentCorpusDefinition corpus) {
        if (source == null || corpus == null) throw new IllegalArgumentException("source/corpus must not be null");
        String content = canonicalText(source.content());
        if (content.isBlank() || content.codePointCount(0, content.length()) > maxContentCodePoints) {
            throw new IllegalArgumentException("document content invalid");
        }
        String tenantId = identifier(source.tenantId(), "tenantId");
        String documentId = identifier(source.documentId(), "documentId");
        String documentVersion = identifier(source.documentVersion(), "documentVersion");
        String status = identifier(source.status(), "status");
        String visibility = identifier(source.visibility(), "visibility");
        if (!STATUSES.contains(status)) throw new IllegalArgumentException("document status invalid");
        if (!VISIBILITIES.contains(visibility)) throw new IllegalArgumentException("document visibility invalid");
        List<String> userIds = principals(source.userIds(), "userIds");
        List<String> departmentIds = principals(source.departmentIds(), "departmentIds");
        List<String> roleIds = principals(source.roleIds(), "roleIds");
        List<String> attributeKeys = principals(source.attributeKeys(), "attributeKeys");
        validateAclClosure(visibility, userIds, departmentIds, roleIds, attributeKeys);
        List<DocumentBusinessFieldValue> business = businessFields(source.businessFields(), corpus.indexedBusinessFields());
        if (!source.embedding().isEmpty()) throw new IllegalArgumentException("source document must not supply document-level embedding");
        if (source.page() != null && source.page() < 0) throw new IllegalArgumentException("document page invalid");
        return new NormalizedDocument(tenantId, documentId, documentVersion, content,
                optionalText(source.title()), optionalText(source.section()), source.page(), safeUri(source.sourceUri()),
                source.sourceUpdatedAt(), status, identifier(source.aclRef(), "aclRef"),
                identifier(source.aclVersion(), "aclVersion"), visibility, userIds, departmentIds, roleIds,
                attributeKeys, business);
    }

    private static List<DocumentBusinessFieldValue> businessFields(
            List<DocumentBusinessFieldValue> values, Set<String> allowed) {
        List<DocumentBusinessFieldValue> sorted = new ArrayList<>(values);
        sorted.sort(Comparator.comparing(DocumentBusinessFieldValue::name));
        Set<String> names = new HashSet<>();
        for (DocumentBusinessFieldValue value : sorted) {
            if (!allowed.contains(value.name())) throw new IllegalArgumentException("document business field not allowed: " + value.name());
            if (!names.add(value.name())) throw new IllegalArgumentException("duplicate document business field: " + value.name());
        }
        return List.copyOf(sorted);
    }

    private static void validateAclClosure(String visibility, List<String> users, List<String> departments,
                                           List<String> roles, List<String> attributes) {
        List<List<String>> values = List.of(users, departments, roles, attributes);
        int requiredIndex = switch (visibility) {
            case "USER" -> 0;
            case "DEPARTMENT" -> 1;
            case "ROLE" -> 2;
            case "ATTRIBUTE" -> 3;
            default -> -1;
        };
        for (int index = 0; index < values.size(); index++) {
            if (index == requiredIndex && values.get(index).isEmpty()) throw new IllegalArgumentException("document ACL principals missing");
            if (index != requiredIndex && !values.get(index).isEmpty()) throw new IllegalArgumentException("document ACL contains unrelated principals");
        }
    }

    private static List<String> principals(List<String> input, String field) {
        if (input.size() > 1024) throw new IllegalArgumentException(field + " exceeds limit");
        List<String> values = input.stream().map(value -> identifier(value, field)).sorted().toList();
        if (new HashSet<>(values).size() != values.size()) throw new IllegalArgumentException(field + " contains duplicate values");
        return values;
    }

    private static String canonicalText(String value) {
        if (value == null) return "";
        String normalized = Normalizer.normalize(value.replace("\r\n", "\n").replace('\r', '\n'), Normalizer.Form.NFC);
        StringBuilder result = new StringBuilder();
        for (String line : normalized.split("\n", -1)) {
            String clean = line.replaceAll("[\\t\\x0B\\f ]+", " ").strip();
            if (!result.isEmpty()) result.append('\n');
            result.append(clean);
        }
        return result.toString().strip();
    }

    private static String optionalText(String value) {
        if (value == null) return null;
        String clean = canonicalText(value);
        return clean.isBlank() ? null : clean;
    }

    private static String safeUri(String value) {
        if (value == null || value.isBlank()) return null;
        try {
            URI uri = URI.create(value);
            if (!uri.isAbsolute() || uri.getHost() == null || uri.getUserInfo() != null
                    || !Set.of("http", "https").contains(uri.getScheme().toLowerCase())) {
                throw new IllegalArgumentException("document source URI is not safe");
            }
            return new URI(uri.getScheme().toLowerCase(), null, uri.getHost().toLowerCase(), uri.getPort(),
                    uri.getPath(), null, null).toASCIIString();
        } catch (Exception ex) {
            throw new IllegalArgumentException("document source URI is not safe", ex);
        }
    }

    private static String identifier(String value, String field) {
        if (value == null || value.isBlank() || value.length() > 256 || !value.equals(value.strip())) {
            throw new IllegalArgumentException("document " + field + " invalid");
        }
        return value;
    }
}
