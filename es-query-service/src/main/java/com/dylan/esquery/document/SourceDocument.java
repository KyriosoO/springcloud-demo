package com.dylan.esquery.document;

import java.time.Instant;
import java.util.List;

/** Source connector 输出的封闭文档合同。 */
public record SourceDocument(
        String tenantId,
        String documentId,
        String documentVersion,
        String content,
        String title,
        String section,
        Integer page,
        String sourceUri,
        Instant sourceUpdatedAt,
        String status,
        String aclRef,
        String aclVersion,
        String visibility,
        List<String> userIds,
        List<String> departmentIds,
        List<String> roleIds,
        List<String> attributeKeys,
        List<DocumentBusinessFieldValue> businessFields,
        List<Double> embedding) {
    public SourceDocument {
        userIds = immutable(userIds);
        departmentIds = immutable(departmentIds);
        roleIds = immutable(roleIds);
        attributeKeys = immutable(attributeKeys);
        businessFields = List.copyOf(businessFields == null ? List.of() : businessFields);
        embedding = List.copyOf(embedding == null ? List.of() : embedding);
    }

    private static List<String> immutable(List<String> values) {
        return List.copyOf(values == null ? List.of() : values);
    }
}
