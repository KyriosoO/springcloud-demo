package com.dylan.agent.capability.document.acl;

import com.dylan.agent.adapter.api.operation.*;
import com.fasterxml.jackson.databind.DeserializationFeature;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.http.HttpHeaders;
import org.springframework.web.client.RestClient;

import java.time.Clock;
import java.time.Duration;
import java.time.Instant;
import java.util.Optional;
import java.util.Set;
import java.util.UUID;

/** strict typed、one-attempt、fail-closed 的 ACL authority HTTP client。 */
public final class HttpDocumentAclScopeClient implements DocumentAclScopePort {
    private static final String PATH = "/internal/document-acl/scope/resolve";

    private final RestClient restClient;
    private final DocumentAclAuthorityCredentialProvider credentialProvider;
    private final ObjectMapper objectMapper;
    private final Clock clock;
    private final DocumentAclCompilerLimits limits;
    private final DocumentAclScopeCanonicalizer scopeCanonicalizer = new DocumentAclScopeCanonicalizer();

    public HttpDocumentAclScopeClient(
            RestClient restClient,
            DocumentAclAuthorityCredentialProvider credentialProvider,
            ObjectMapper objectMapper,
            Clock clock,
            DocumentAclCompilerLimits limits) {
        this.restClient = java.util.Objects.requireNonNull(restClient);
        this.credentialProvider = java.util.Objects.requireNonNull(credentialProvider);
        this.objectMapper = java.util.Objects.requireNonNull(objectMapper).copy()
                .enable(DeserializationFeature.FAIL_ON_UNKNOWN_PROPERTIES);
        this.clock = java.util.Objects.requireNonNull(clock);
        this.limits = java.util.Objects.requireNonNull(limits);
    }

    @Override
    public DocumentAclScopeResolution resolve(DocumentAclScopeRequest request) {
        java.util.Objects.requireNonNull(request, "document ACL scope request must not be null");
        CapabilityOperationContext context = request.operationContext();
        long started = System.nanoTime();
        if (context.cancellation().isCancelled()) {
            return failed(request, DocumentAclFailureCode.CANCELLED, 0,
                    CapabilityOperationTermination.CANCELLED, started);
        }
        if (!context.absoluteDeadline().isAfter(clock.instant())) {
            return failed(request, DocumentAclFailureCode.DEADLINE_EXCEEDED, 0,
                    CapabilityOperationTermination.DEADLINE_EXCEEDED, started);
        }
        try {
            AuthorityRequest body = AuthorityRequest.from(request);
            byte[] wire = restClient.post()
                    .uri(PATH)
                    .header(HttpHeaders.AUTHORIZATION, credentialProvider.authorizationHeader())
                    .header("X-Agent-Request-Id", context.requestCorrelationId())
                    .header("X-Agent-Operation-Id", context.operationId())
                    .header("X-Agent-Deadline", context.absoluteDeadline().toString())
                    .body(body)
                    .retrieve()
                    .body(byte[].class);
            if (context.cancellation().isCancelled()) {
                return failed(request, DocumentAclFailureCode.CANCELLED, 1,
                        CapabilityOperationTermination.CANCELLED, started);
            }
            if (!context.absoluteDeadline().isAfter(clock.instant())) {
                return failed(request, DocumentAclFailureCode.DEADLINE_EXCEEDED, 1,
                        CapabilityOperationTermination.DEADLINE_EXCEEDED, started);
            }
            if (wire == null || wire.length == 0) {
                return failed(request, DocumentAclFailureCode.INVALID_RESPONSE, 1,
                        CapabilityOperationTermination.FAILED, started);
            }
            if (wire.length > limits.maxWireBytes()) {
                return failed(request, DocumentAclFailureCode.RESPONSE_TOO_LARGE, 1,
                        CapabilityOperationTermination.FAILED, started);
            }
            AuthorityResponse response = objectMapper.readValue(wire, AuthorityResponse.class);
            if (!response.matches(request)) {
                return failed(request, DocumentAclFailureCode.BINDING_MISMATCH, 1,
                        CapabilityOperationTermination.REJECTED, started);
            }
            return mapResponse(request, response, started);
        } catch (Exception ex) {
            return failed(request, DocumentAclFailureCode.AUTHORITY_UNAVAILABLE, 1,
                    CapabilityOperationTermination.FAILED, started);
        }
    }

    private DocumentAclScopeResolution mapResponse(
            DocumentAclScopeRequest request,
            AuthorityResponse response,
            long started) {
        if ("DENIED".equals(response.outcome())) {
            try {
                return new DocumentAclScopeDenied(
                        DocumentAclDenyReason.valueOf(response.reason()), response.decisionEvidenceRef(),
                        metadata(request, 1, CapabilityOperationTermination.REJECTED, diagnostic(response), started));
            } catch (RuntimeException ex) {
                return failed(request, DocumentAclFailureCode.INVALID_RESPONSE, 1,
                        CapabilityOperationTermination.FAILED, started);
            }
        }
        if ("FAILED".equals(response.outcome())) {
            try {
                return new DocumentAclScopeFailed(
                        DocumentAclFailureCode.valueOf(response.failureCode()), diagnostic(response),
                        metadata(request, 1, CapabilityOperationTermination.FAILED, diagnostic(response), started));
            } catch (RuntimeException ex) {
                return failed(request, DocumentAclFailureCode.INVALID_RESPONSE, 1,
                        CapabilityOperationTermination.FAILED, started);
            }
        }
        if (!"ALLOWED".equals(response.outcome())) {
            return failed(request, DocumentAclFailureCode.INVALID_RESPONSE, 1,
                    CapabilityOperationTermination.FAILED, started);
        }
        try {
            DocumentIdConstraint constraint = switch (response.documentIdConstraint()) {
                case "ALL_PRINCIPAL_VISIBLE" -> new AllPrincipalVisibleDocuments();
                case "ONLY_DOCUMENT_IDS" -> new OnlyDocumentIds(requiredSet(response.allowedDocumentIds()));
                default -> throw new IllegalArgumentException("unknown documentIdConstraint");
            };
            Instant issuedAt = Instant.parse(response.issuedAt());
            Instant expiresAt = Instant.parse(response.expiresAt());
            String localDigest = scopeCanonicalizer.digest(
                    response.tenantId(), response.subjectPrincipalId(), requiredSet(response.departmentIds()),
                    requiredSet(response.roleIds()), requiredSet(response.attributeKeys()), constraint,
                    requiredSet(response.deniedDocumentIds()), response.authorityVersion(),
                    response.permissionVersion(), response.issuedAt(), response.expiresAt(),
                    response.authorityEvidenceRef());
            if (response.declaredCanonicalDigest() != null
                    && !response.declaredCanonicalDigest().equals(localDigest)) {
                throw new IllegalArgumentException("authority declared digest mismatch");
            }
            DocumentAclScopeSnapshot scope = new DocumentAclScopeSnapshot(
                    response.tenantId(), response.subjectPrincipalId(), requiredSet(response.departmentIds()),
                    requiredSet(response.roleIds()), requiredSet(response.attributeKeys()), constraint,
                    requiredSet(response.deniedDocumentIds()), response.authorityVersion(),
                    response.permissionVersion(), issuedAt, expiresAt, response.authorityEvidenceRef(), localDigest);
            if (!scope.permissionVersion().equals(request.permissionEvidence().permissionVersion())
                    || !scope.isCurrentAt(clock.instant())) {
                throw new IllegalArgumentException("ACL scope is stale or permission changed");
            }
            limits.validateScope(scope);
            CapabilityOperationMetadata metadata = metadata(
                    request, 1, CapabilityOperationTermination.SUCCEEDED, diagnostic(response), started);
            return new DocumentAclScopeAllowed(scope, metadata);
        } catch (RuntimeException ex) {
            return failed(request, DocumentAclFailureCode.INVALID_RESPONSE, 1,
                    CapabilityOperationTermination.FAILED, started);
        }
    }

    private DocumentAclScopeFailed failed(
            DocumentAclScopeRequest request,
            DocumentAclFailureCode code,
            int attempts,
            CapabilityOperationTermination termination,
            long started) {
        String diagnosticId = diagnosticId();
        return new DocumentAclScopeFailed(
                code, diagnosticId, metadata(request, attempts, termination, diagnosticId, started));
    }

    private CapabilityOperationMetadata metadata(
            DocumentAclScopeRequest request,
            int attempts,
            CapabilityOperationTermination termination,
            String diagnosticId,
            long started) {
        CapabilityOperationContext context = request.operationContext();
        return new CapabilityOperationMetadata(
                context.operationId(), context.operationType(),
                new ProviderSafeIdentity("document-acl-authority", Optional.empty()), attempts,
                Duration.ofNanos(System.nanoTime() - started).toMillis(), termination, diagnosticId,
                context.resourceLimits().reference(), false,
                termination == CapabilityOperationTermination.DEADLINE_EXCEEDED,
                termination == CapabilityOperationTermination.CANCELLED);
    }

    private static Set<String> requiredSet(Set<String> values) {
        if (values == null) throw new IllegalArgumentException("authority set must not be null");
        return values;
    }

    private static String diagnostic(AuthorityResponse response) {
        return response.diagnosticId() == null || response.diagnosticId().isBlank()
                ? diagnosticId() : response.diagnosticId();
    }

    private static String diagnosticId() {
        return "doc-acl-" + UUID.randomUUID().toString().replace("-", "");
    }

    private record AuthorityRequest(
            String invocationId,
            String requestCorrelationId,
            String capabilityId,
            String operationId,
            String registrationIdentity,
            String subjectType,
            String subjectId,
            String domain,
            String materialType,
            String operation,
            String permissionEvidenceId,
            String permissionVersion,
            String profileProjectionDigest,
            String resourceLimitDigest,
            String deadline) {
        static AuthorityRequest from(DocumentAclScopeRequest request) {
            var context = request.operationContext();
            return new AuthorityRequest(
                    context.invocationId(), context.requestCorrelationId(), context.capabilityId(),
                    context.operationId(), request.registrationIdentity(), request.subjectRef().type(),
                    request.subjectRef().id(), request.corpusKey().domain(), request.corpusKey().materialType(),
                    request.operation().name(), request.permissionEvidence().evidenceId(),
                    request.permissionEvidence().permissionVersion(), request.profileProjectionDigest(),
                    context.resourceLimits().reference().canonicalDigest(), context.absoluteDeadline().toString());
        }
    }

    private record AuthorityResponse(
            String outcome,
            String invocationId,
            String requestCorrelationId,
            String operationId,
            String registrationIdentity,
            String subjectType,
            String subjectId,
            String domain,
            String materialType,
            String operation,
            String permissionEvidenceId,
            String permissionVersion,
            String profileProjectionDigest,
            String tenantId,
            String subjectPrincipalId,
            Set<String> departmentIds,
            Set<String> roleIds,
            Set<String> attributeKeys,
            String documentIdConstraint,
            Set<String> allowedDocumentIds,
            Set<String> deniedDocumentIds,
            String authorityVersion,
            String issuedAt,
            String expiresAt,
            String authorityEvidenceRef,
            String declaredCanonicalDigest,
            String reason,
            String decisionEvidenceRef,
            String failureCode,
            String diagnosticId) {
        boolean matches(DocumentAclScopeRequest request) {
            var context = request.operationContext();
            return java.util.Objects.equals(invocationId, context.invocationId())
                    && java.util.Objects.equals(requestCorrelationId, context.requestCorrelationId())
                    && java.util.Objects.equals(operationId, context.operationId())
                    && java.util.Objects.equals(registrationIdentity, request.registrationIdentity())
                    && java.util.Objects.equals(subjectType, request.subjectRef().type())
                    && java.util.Objects.equals(subjectId, request.subjectRef().id())
                    && java.util.Objects.equals(domain, request.corpusKey().domain())
                    && java.util.Objects.equals(materialType, request.corpusKey().materialType())
                    && java.util.Objects.equals(operation, request.operation().name())
                    && java.util.Objects.equals(permissionEvidenceId, request.permissionEvidence().evidenceId())
                    && java.util.Objects.equals(permissionVersion, request.permissionEvidence().permissionVersion())
                    && java.util.Objects.equals(profileProjectionDigest, request.profileProjectionDigest());
        }
    }
}
