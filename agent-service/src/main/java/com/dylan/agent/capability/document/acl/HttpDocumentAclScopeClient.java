package com.dylan.agent.capability.document.acl;

import com.dylan.agent.adapter.api.document.DocumentAclScope;
import org.springframework.web.client.RestClient;

import java.time.Instant;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Objects;

/** HTTP 文档 ACL scope 客户端，不记录完整 ACL 表达式。 */
public final class HttpDocumentAclScopeClient implements DocumentAclScopePort {

    private final RestClient restClient;

    public HttpDocumentAclScopeClient(RestClient restClient) {
        this.restClient = restClient;
    }

    @Override
    public DocumentAclScope resolve(DocumentAclScopeRequest request) {
        Objects.requireNonNull(request, "document ACL scope request must not be null");
        @SuppressWarnings("unchecked")
        Map<String, Object> response = restClient.post()
                .uri("/internal/document-acl/scope/resolve")
                .body(requestBody(request))
                .retrieve()
                .body(Map.class);
        if (response == null || response.isEmpty()) {
            throw new IllegalStateException("document ACL scope resolver returned empty response");
        }
        validateResponseBinding(request, response);
        return new DocumentAclScope(
                stringValue(response.get("tenantId")),
                stringValue(response.get("userId")),
                stringList(response.get("departmentIds")),
                stringList(response.get("roleIds")),
                stringList(response.get("attributeKeys")),
                stringValue(response.get("aclSnapshotVersion")),
                Instant.parse(stringValue(response.get("expiresAt"))));
    }

    private static void validateResponseBinding(DocumentAclScopeRequest request, Map<String, Object> response) {
        if (response.containsKey("subjectRef")
                && !request.subjectRef().equals(requireNonBlank(stringValue(response.get("subjectRef")), "subjectRef"))) {
            throw new IllegalStateException("document ACL scope response subjectRef mismatch");
        }
        if (response.containsKey("domain")
                && !request.domain().equals(requireNonBlank(stringValue(response.get("domain")), "domain"))) {
            throw new IllegalStateException("document ACL scope response domain mismatch");
        }
    }

    private static Map<String, Object> requestBody(DocumentAclScopeRequest request) {
        Map<String, Object> body = new LinkedHashMap<>();
        body.put("requestId", requireNonBlank(request.invocationId(), "requestId"));
        body.put("subjectRef", requireNonBlank(request.subjectRef(), "subjectRef"));
        body.put("domain", requireNonBlank(request.domain(), "domain"));
        body.put("permissionEvidenceId", requireNonBlank(request.permissionEvidenceId(), "permissionEvidenceId"));
        body.put("permissionVersion", requireNonBlank(request.permissionVersion(), "permissionVersion"));
        body.put("deadline", Objects.requireNonNull(request.deadline(), "deadline must not be null").toString());
        return body;
    }

    private static String requireNonBlank(String value, String name) {
        if (value == null || value.isBlank()) {
            throw new IllegalStateException("document ACL scope request missing " + name);
        }
        return value;
    }

    private static String stringValue(Object value) {
        return value == null ? null : String.valueOf(value);
    }

    private static List<String> stringList(Object value) {
        if (!(value instanceof List<?> values)) {
            return List.of();
        }
        return values.stream()
                .filter(item -> item != null && !String.valueOf(item).isBlank())
                .map(String::valueOf)
                .toList();
    }
}
