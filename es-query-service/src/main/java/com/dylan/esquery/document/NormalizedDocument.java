package com.dylan.esquery.document;

import java.time.Instant;
import java.util.List;

/** 已 canonicalize 且 ACL 闭合的文档；不携带 Profile 或自由 metadata。 */
public record NormalizedDocument(
        String tenantId,
        String documentId,
        String documentVersion,
        String content,
        String title,
        String section,
        Integer page,
        String safeSourceUri,
        Instant sourceUpdatedAt,
        String status,
        String aclRef,
        String aclVersion,
        String visibility,
        List<String> userIds,
        List<String> departmentIds,
        List<String> roleIds,
        List<String> attributeKeys,
        List<DocumentBusinessFieldValue> businessFields) {
    public NormalizedDocument {
        userIds = List.copyOf(userIds);
        departmentIds = List.copyOf(departmentIds);
        roleIds = List.copyOf(roleIds);
        attributeKeys = List.copyOf(attributeKeys);
        businessFields = List.copyOf(businessFields);
    }
}
