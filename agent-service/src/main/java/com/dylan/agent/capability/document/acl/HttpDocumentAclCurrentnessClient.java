package com.dylan.agent.capability.document.acl;

import com.dylan.agent.adapter.api.document.DocumentAclObjectRef;
import com.dylan.agent.adapter.api.operation.*;
import com.fasterxml.jackson.databind.DeserializationFeature;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.http.HttpHeaders;
import org.springframework.web.client.RestClient;

import java.time.Clock;
import java.time.Duration;
import java.time.Instant;
import java.util.List;
import java.util.Optional;
import java.util.UUID;

/** scope/candidate batch currentness 的 strict typed、one-attempt client。 */
public final class HttpDocumentAclCurrentnessClient implements DocumentAclCurrentnessPort {
    private final RestClient restClient;
    private final DocumentAclAuthorityCredentialProvider credentials;
    private final ObjectMapper objectMapper;
    private final Clock clock;
    private final DocumentAclCompilerLimits limits;

    public HttpDocumentAclCurrentnessClient(
            RestClient restClient,
            DocumentAclAuthorityCredentialProvider credentials,
            ObjectMapper objectMapper,
            Clock clock,
            DocumentAclCompilerLimits limits) {
        this.restClient = restClient;
        this.credentials = credentials;
        this.objectMapper = objectMapper.copy().enable(DeserializationFeature.FAIL_ON_UNKNOWN_PROPERTIES);
        this.clock = clock;
        this.limits = limits;
    }

    @Override
    public DocumentAclCurrentnessDecision verifyScope(DocumentAclScopeCurrentnessRequest request) {
        return call("/internal/document-acl/currentness/scope", WireRequest.scope(request), request.operationContext());
    }

    @Override
    public DocumentAclCurrentnessDecision verifyCandidates(DocumentAclCandidateCurrentnessRequest request) {
        if (request.candidates().size() > limits.maxCurrentnessCandidates()) {
            return localFailure(request.operationContext(), "CANDIDATE_LIMIT_EXCEEDED", 0, System.nanoTime());
        }
        return call("/internal/document-acl/currentness/candidates", WireRequest.candidates(request), request.operationContext());
    }

    private DocumentAclCurrentnessDecision call(
            String path,
            WireRequest body,
            CapabilityOperationContext context) {
        long started = System.nanoTime();
        if (context.cancellation().isCancelled()) return localFailure(context, "CANCELLED", 0, started);
        if (!context.absoluteDeadline().isAfter(clock.instant())) {
            return localFailure(context, "DEADLINE_EXCEEDED", 0, started);
        }
        try {
            byte[] bytes = restClient.post().uri(path)
                    .header(HttpHeaders.AUTHORIZATION, credentials.authorizationHeader())
                    .header("X-Agent-Request-Id", context.requestCorrelationId())
                    .header("X-Agent-Operation-Id", context.operationId())
                    .header("X-Agent-Deadline", context.absoluteDeadline().toString())
                    .body(body).retrieve().body(byte[].class);
            if (bytes == null || bytes.length == 0 || bytes.length > limits.maxWireBytes()) {
                return localFailure(context, "INVALID_RESPONSE", 1, started);
            }
            if (context.cancellation().isCancelled()) return localFailure(context, "CANCELLED", 1, started);
            if (!context.absoluteDeadline().isAfter(clock.instant())) {
                return localFailure(context, "DEADLINE_EXCEEDED", 1, started);
            }
            WireResponse response = objectMapper.readValue(bytes, WireResponse.class);
            if (!body.matches(response)) return localFailure(context, "BINDING_MISMATCH", 1, started);
            DocumentCurrentnessOutcome outcome = DocumentCurrentnessOutcome.valueOf(response.outcome());
            Instant checkedAt = Instant.parse(response.checkedAt());
            Instant validUntil = Instant.parse(response.validUntil());
            if (checkedAt.isAfter(clock.instant()) || !validUntil.isAfter(clock.instant())
                    || validUntil.isAfter(context.absoluteDeadline())) {
                return localFailure(context, "STALE_RESPONSE", 1, started);
            }
            CapabilityOperationTermination termination = outcome == DocumentCurrentnessOutcome.ALLOW
                    ? CapabilityOperationTermination.SUCCEEDED : CapabilityOperationTermination.REJECTED;
            return new DocumentAclCurrentnessDecision(
                    outcome, response.authorityVersion(), response.permissionVersion(), response.decisionVersion(),
                    checkedAt, validUntil, response.reasonCode(), metadata(context, 1, termination, started));
        } catch (Exception ex) {
            return localFailure(context, "AUTHORITY_UNAVAILABLE", 1, started);
        }
    }

    private DocumentAclCurrentnessDecision localFailure(
            CapabilityOperationContext context, String reason, int attempts, long started) {
        Instant now = clock.instant();
        return new DocumentAclCurrentnessDecision(
                DocumentCurrentnessOutcome.FAILURE, null, null, diagnosticId(), now, now, reason,
                metadata(context, attempts,
                        "CANCELLED".equals(reason) ? CapabilityOperationTermination.CANCELLED
                                : "DEADLINE_EXCEEDED".equals(reason)
                                ? CapabilityOperationTermination.DEADLINE_EXCEEDED
                                : CapabilityOperationTermination.FAILED,
                        started));
    }

    private static CapabilityOperationMetadata metadata(
            CapabilityOperationContext context,
            int attempts,
            CapabilityOperationTermination termination,
            long started) {
        return new CapabilityOperationMetadata(
                context.operationId(), context.operationType(),
                new ProviderSafeIdentity("document-acl-authority", Optional.empty()), attempts,
                Duration.ofNanos(System.nanoTime() - started).toMillis(), termination, diagnosticId(),
                context.resourceLimits().reference(), false,
                termination == CapabilityOperationTermination.DEADLINE_EXCEEDED,
                termination == CapabilityOperationTermination.CANCELLED);
    }

    private static String diagnosticId() { return "doc-current-" + UUID.randomUUID().toString().replace("-", ""); }

    private record WireRequest(
            String invocationId, String requestCorrelationId, String operationId,
            String evidenceDigest, String authorityVersion, String permissionVersion,
            String candidateSetDigest, List<DocumentAclObjectRef> candidates, String deadline) {
        static WireRequest scope(DocumentAclScopeCurrentnessRequest request) {
            return from(request.evidence(), null, List.of(), request.operationContext());
        }
        static WireRequest candidates(DocumentAclCandidateCurrentnessRequest request) {
            return from(request.evidence(), request.candidateSetDigest(), request.candidates(), request.operationContext());
        }
        static WireRequest from(DocumentAclExecutionEvidence evidence, String digest,
                                List<DocumentAclObjectRef> candidates, CapabilityOperationContext context) {
            return new WireRequest(context.invocationId(), context.requestCorrelationId(), context.operationId(),
                    evidence.canonicalDigest(), evidence.aclAuthorityVersion(),
                    evidence.permissionEvidence().permissionVersion(), digest, List.copyOf(candidates),
                    context.absoluteDeadline().toString());
        }
        boolean matches(WireResponse response) {
            return invocationId.equals(response.invocationId())
                    && requestCorrelationId.equals(response.requestCorrelationId())
                    && operationId.equals(response.operationId())
                    && evidenceDigest.equals(response.evidenceDigest())
                    && java.util.Objects.equals(candidateSetDigest, response.candidateSetDigest());
        }
    }

    private record WireResponse(
            String outcome, String invocationId, String requestCorrelationId, String operationId,
            String evidenceDigest, String candidateSetDigest, String authorityVersion,
            String permissionVersion, String decisionVersion, String checkedAt, String validUntil,
            String reasonCode) {}
}
