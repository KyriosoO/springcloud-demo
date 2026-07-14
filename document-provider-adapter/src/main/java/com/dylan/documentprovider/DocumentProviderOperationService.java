package com.dylan.documentprovider;

import com.dylan.agent.adapter.api.document.provider.*;
import com.dylan.agent.adapter.api.operation.CapabilityOperationType;
import org.springframework.stereotype.Service;
import java.time.Instant;
import java.util.UUID;
import java.util.function.BiFunction;

/** Adapter boundary：binding/deadline/replay 校验通过后最多一次 vendor write。 */
@Service
public final class DocumentProviderOperationService {
    private static final CapabilityOperationType REWRITE = CapabilityOperationType.of("DOCUMENT_REWRITE");
    private static final CapabilityOperationType EMBEDDING = CapabilityOperationType.of("DOCUMENT_EMBEDDING");
    private static final CapabilityOperationType RERANK = CapabilityOperationType.of("DOCUMENT_RERANK");
    private static final CapabilityOperationType GENERATION = CapabilityOperationType.of("DOCUMENT_GENERATION");
    private final DocumentProviderActivationReadView activation;
    private final DocumentProviderReplayGuard replayGuard;
    private final DocumentVendorClient vendorClient;
    private final DocumentProviderCanonicalizer canonicalizer;

    DocumentProviderOperationService(DocumentProviderActivationReadView activation,
                                     DocumentProviderReplayGuard replayGuard,
                                     DocumentVendorClient vendorClient,
                                     DocumentProviderCanonicalizer canonicalizer) {
        this.activation = activation;
        this.replayGuard = replayGuard;
        this.vendorClient = vendorClient;
        this.canonicalizer = canonicalizer;
    }

    DocumentProviderWireResponse<DocumentUntrustedRewritePayload> rewrite(
            String identity, DocumentProviderWireRequest<DocumentRewriteInputProjection> request) {
        return execute(identity, REWRITE, request, vendorClient::rewrite);
    }
    DocumentProviderWireResponse<DocumentUntrustedEmbeddingPayload> embedding(
            String identity, DocumentProviderWireRequest<DocumentEmbeddingInputProjection> request) {
        return execute(identity, EMBEDDING, request, vendorClient::embedding);
    }
    DocumentProviderWireResponse<DocumentUntrustedRerankPayload> rerank(
            String identity, DocumentProviderWireRequest<DocumentRerankInputProjection> request) {
        return execute(identity, RERANK, request, vendorClient::rerank);
    }
    DocumentProviderWireResponse<DocumentUntrustedGenerationPayload> generation(
            String identity, DocumentProviderWireRequest<DocumentGenerationInputProjection> request) {
        return execute(identity, GENERATION, request, vendorClient::generation);
    }

    private <I, O> DocumentProviderWireResponse<O> execute(
            String identity, CapabilityOperationType expectedType, DocumentProviderWireRequest<I> request,
            BiFunction<I, DocumentProviderBindingReference, O> invocation) {
        validate(identity, expectedType, request);
        DocumentProviderActivationSnapshot snapshot;
        try {
            snapshot = activation.requireCurrent(request.operationType());
        } catch (RuntimeException ex) {
            throw reject(request, DocumentProviderAdapterFailureCode.ACTIVATION_REJECTED, "activation-unavailable");
        }
        DocumentProviderBindingReference binding = snapshot.expectedProvider().orElseThrow();
        if (!snapshot.canonicalDigest().equals(request.expectedActivationDigest())
                || !binding.canonicalDigest().equals(request.expectedProviderBindingDigest())) {
            throw reject(request, DocumentProviderAdapterFailureCode.ACTIVATION_REJECTED, "activation-mismatch");
        }
        if (!replayGuard.register(identity, request.operationId(), request.requestDigest())) {
            throw reject(request, DocumentProviderAdapterFailureCode.REQUEST_REJECTED, "request-replayed");
        }
        O payload;
        try {
            payload = invocation.apply(request.input(), binding);
        } catch (UnavailableDocumentVendorClient.VendorUnavailableException ex) {
            throw reject(request, DocumentProviderAdapterFailureCode.VENDOR_UNAVAILABLE, "vendor-unavailable");
        } catch (RuntimeException ex) {
            throw reject(request, DocumentProviderAdapterFailureCode.VENDOR_FAILED, "vendor-failed");
        }
        if (payload == null) {
            throw reject(request, DocumentProviderAdapterFailureCode.VENDOR_INVALID_RESPONSE, "vendor-empty");
        }
        DocumentProviderActivationSnapshot after;
        try {
            after = activation.requireCurrent(request.operationType());
        } catch (RuntimeException ex) {
            throw reject(request, DocumentProviderAdapterFailureCode.ACTIVATION_REJECTED, "activation-changed");
        }
        if (!after.canonicalDigest().equals(snapshot.canonicalDigest())
                || !Instant.now().isBefore(Instant.ofEpochMilli(request.absoluteDeadlineEpochMillis()))) {
            throw reject(request, DocumentProviderAdapterFailureCode.REQUEST_ABORTED, "post-check-rejected");
        }
        return new DocumentProviderWireResponse<>("DPW-1", request.operationId(), request.operationType(),
                request.requestDigest(), snapshot.canonicalDigest(), binding, payload);
    }

    private void validate(String identity, CapabilityOperationType expectedType, DocumentProviderWireRequest<?> request) {
        if (request == null || request.input() == null || identity == null || identity.isBlank()
                || !"DPW-1".equals(request.wireContractVersion()) || request.operationId() == null
                || request.operationType() == null || request.requestDigest() == null
                || request.expectedActivationDigest() == null || request.expectedProviderBindingDigest() == null) {
            throw reject(request, DocumentProviderAdapterFailureCode.REQUEST_REJECTED, "request-invalid");
        }
        if (!expectedType.equals(request.operationType())) {
            throw reject(request, DocumentProviderAdapterFailureCode.REQUEST_REJECTED, "operation-type-mismatch");
        }
        String actualDigest;
        try {
            actualDigest = canonicalizer.wireRequestDigest(request.wireContractVersion(), request.operationId(),
                    request.operationType(), request.absoluteDeadlineEpochMillis(), request.expectedActivationDigest(),
                    request.expectedProviderBindingDigest(), request.input());
        } catch (RuntimeException ex) {
            throw reject(request, DocumentProviderAdapterFailureCode.REQUEST_REJECTED, "request-canonical-invalid");
        }
        if (!actualDigest.equals(request.requestDigest())) {
            throw reject(request, DocumentProviderAdapterFailureCode.REQUEST_REJECTED, "request-digest-mismatch");
        }
        if (!Instant.now().isBefore(Instant.ofEpochMilli(request.absoluteDeadlineEpochMillis()))) {
            throw reject(request, DocumentProviderAdapterFailureCode.DEADLINE_REJECTED, "deadline-expired");
        }
    }

    private static ProviderAdapterException reject(DocumentProviderWireRequest<?> request,
                                                     DocumentProviderAdapterFailureCode code, String reason) {
        return new ProviderAdapterException(
                request == null || request.operationId() == null ? "unbound" : request.operationId(),
                request == null || request.operationType() == null
                        ? com.dylan.agent.adapter.api.operation.CapabilityOperationType.of("UNKNOWN") : request.operationType(),
                request == null || request.requestDigest() == null ? "unbound" : request.requestDigest(),
                code, reason + "-" + UUID.randomUUID().toString().replace("-", ""));
    }
}
