package com.dylan.agent.capability.document.acl;

import com.dylan.agent.adapter.api.document.DocumentAclScope;
import com.dylan.agent.capability.document.provider.DocumentProviderAuthHeaderProvider;
import org.springframework.http.HttpHeaders;
import org.springframework.web.client.RestClient;

import java.time.Instant;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Objects;

/** HTTP 文档 ACL scope 客户端，不记录完整 ACL 表达式。 */
public final class HttpDocumentAclScopeClient implements DocumentAclScopePort {

    private final RestClient restClient;
    private final DocumentProviderAuthHeaderProvider authHeaderProvider;

    public HttpDocumentAclScopeClient(
            RestClient restClient,
            DocumentProviderAuthHeaderProvider authHeaderProvider) {
        this.restClient = Objects.requireNonNull(restClient, "restClient must not be null");
        this.authHeaderProvider = Objects.requireNonNull(authHeaderProvider, "authHeaderProvider must not be null");
    }

    @Override
    public DocumentAclScope resolve(DocumentAclScopeRequest request) {
        Objects.requireNonNull(request, "document ACL scope request must not be null");
        Map<String, Object> body = requestBody(request);
        String requestId = (String) body.get("invocationId");
        String deadline = (String) body.get("deadline");
        @SuppressWarnings("unchecked")
        Map<String, Object> response = restClient.post()
                .uri("/internal/document-acl/scope/resolve")
                .header(HttpHeaders.AUTHORIZATION, authHeaderProvider.authorizationHeader())
                .header("X-Agent-Request-Id", requestId)
                .header("X-Agent-Deadline", deadline)
                .body(body)
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
        if (response.containsKey("materialType")
                && !safeEquals(request.materialType(), requireNonBlank(stringValue(response.get("materialType")), "materialType"))) {
            throw new IllegalStateException("document ACL scope response materialType mismatch");
        }
        if (response.containsKey("retrievalProfile")
                && !safeEquals(request.retrievalProfile(), requireNonBlank(stringValue(response.get("retrievalProfile")), "retrievalProfile"))) {
            throw new IllegalStateException("document ACL scope response retrievalProfile mismatch");
        }
        if (response.containsKey("profileVersion")
                && !safeEquals(request.profileVersion(), requireNonBlank(stringValue(response.get("profileVersion")), "profileVersion"))) {
            throw new IllegalStateException("document ACL scope response profileVersion mismatch");
        }
        if (response.containsKey("indexAlias")
                && !safeEquals(request.indexAlias(), requireNonBlank(stringValue(response.get("indexAlias")), "indexAlias"))) {
            throw new IllegalStateException("document ACL scope response indexAlias mismatch");
        }
    }

    private static Map<String, Object> requestBody(DocumentAclScopeRequest request) {
        Map<String, Object> body = new LinkedHashMap<>();
        body.put("invocationId", requireNonBlank(request.invocationId(), "invocationId"));
        body.put("subjectRef", requireNonBlank(request.subjectRef(), "subjectRef"));
        body.put("domain", requireNonBlank(request.domain(), "domain"));
        body.put("materialType", requireNonBlank(request.materialType(), "materialType"));
        body.put("retrievalProfile", requireNonBlank(request.retrievalProfile(), "retrievalProfile"));
        body.put("profileVersion", requireNonBlank(request.profileVersion(), "profileVersion"));
        body.put("indexAlias", requireNonBlank(request.indexAlias(), "indexAlias"));
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

    private static boolean safeEquals(String left, String right) {
        return Objects.equals(left, right);
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
