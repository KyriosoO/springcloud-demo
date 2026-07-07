package com.dylan.agent.adapter.document;

import com.dylan.agent.adapter.api.document.DocumentAclScope;

import java.time.Instant;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/** 构建文档检索阶段必须携带的 ACL filter。 */
public class DocumentAclFilterFactory {

    private static final int MAX_VISIBILITY_TERMS = 128;
    private static final int BASE_VISIBILITY_TERMS = 3;

    public Map<String, Object> build(String domain, DocumentAclScope scope) {
        if (domain == null || domain.isBlank()) {
            throw new IllegalArgumentException("document domain must not be blank");
        }
        if (scope == null) {
            throw new IllegalArgumentException("document ACL scope must not be null");
        }
        if (scope.isExpiredAt(Instant.now())) {
            throw new IllegalArgumentException("document ACL scope is expired");
        }
        List<Object> filters = new ArrayList<>();
        filters.add(Map.of("term", Map.of("tenantId", scope.getTenantId())));
        filters.add(Map.of("term", Map.of("corpusId", domain)));
        filters.add(Map.of("term", Map.of("status", "ACTIVE")));
        filters.add(visibilityFilter(scope));
        return Map.of("bool", Map.of("filter", filters));
    }

    public Map<String, Object> merge(Map<String, Object> businessFilter, Map<String, Object> aclFilter) {
        List<Object> filters = new ArrayList<>();
        filters.addAll(filterItems(businessFilter));
        filters.addAll(filterItems(aclFilter));
        if (filters.isEmpty()) {
            throw new IllegalArgumentException("merged document filter must not be empty");
        }
        return Map.of("bool", Map.of("filter", filters));
    }

    private Map<String, Object> visibilityFilter(DocumentAclScope scope) {
        int termCount = BASE_VISIBILITY_TERMS
                + scope.getDepartmentIds().size()
                + scope.getRoleIds().size()
                + scope.getAttributeKeys().size();
        if (termCount > MAX_VISIBILITY_TERMS) {
            throw new IllegalArgumentException("document ACL visibility projection exceeds max terms");
        }
        List<Object> should = new ArrayList<>();
        should.add(Map.of("term", Map.of("visibility", "PUBLIC")));
        should.add(Map.of("term", Map.of("visibility", "TENANT")));
        should.add(Map.of("terms", Map.of("userIds", List.of(scope.getUserId()))));
        addTerms(should, "departmentIds", scope.getDepartmentIds());
        addTerms(should, "roleIds", scope.getRoleIds());
        addTerms(should, "attributeKeys", scope.getAttributeKeys());
        return Map.of("bool", Map.of(
                "should", should,
                "minimum_should_match", 1));
    }

    private static void addTerms(List<Object> should, String field, List<String> values) {
        if (values != null && !values.isEmpty()) {
            should.add(Map.of("terms", Map.of(field, values)));
        }
    }

    @SuppressWarnings("unchecked")
    private static List<Object> filterItems(Map<String, Object> filter) {
        if (filter == null || filter.isEmpty()) {
            return List.of();
        }
        Object bool = filter.get("bool");
        if (!(bool instanceof Map<?, ?> boolMap)) {
            return List.of(filter);
        }
        Object items = boolMap.get("filter");
        if (items instanceof List<?> list) {
            return list.stream().map(item -> (Object) item).toList();
        }
        if (items instanceof Map<?, ?> map) {
            return List.of(new LinkedHashMap<>((Map<String, Object>) map));
        }
        return List.of(filter);
    }
}
