package com.dylan.esquery.security;

import com.dylan.esquery.api.model.DocumentProtectedFilterDto;

import java.util.List;
import java.util.Map;

/** closed wire AST 到 ES fragment 的唯一编译器。 */
public final class DocumentProtectedFilterCompiler {
    public Object compile(DocumentProtectedFilterDto node) {
        return switch (node.kind()) {
            case ALL_OF -> Map.of("bool", Map.of("filter", node.children().stream().map(this::compile).toList()));
            case ANY_OF -> Map.of("bool", Map.of(
                    "should", node.children().stream().map(this::compile).toList(), "minimum_should_match", 1));
            case EXACT -> Map.of("term", Map.of(field(node.field()), node.value()));
            case ANY_TERMS -> Map.of("terms", Map.of(field(node.field()), node.values()));
            case NONE_TERMS -> Map.of("bool", Map.of(
                    "must_not", List.of(Map.of("terms", Map.of(field(node.field()), node.values())))));
        };
    }

    private String field(DocumentProtectedFilterDto.Field field) {
        return switch (field) {
            case TENANT_ID -> "tenantId";
            case STATUS -> "status";
            case VISIBILITY -> "visibility";
            case USER_IDS -> "userIds";
            case DEPARTMENT_IDS -> "departmentIds";
            case ROLE_IDS -> "roleIds";
            case ATTRIBUTE_KEYS -> "attributeKeys";
            case DOCUMENT_ID -> "documentId";
        };
    }
}
