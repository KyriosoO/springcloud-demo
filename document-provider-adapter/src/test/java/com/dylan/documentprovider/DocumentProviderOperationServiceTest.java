package com.dylan.documentprovider;

import com.dylan.agent.adapter.api.document.provider.*;
import com.dylan.agent.adapter.api.operation.CapabilityOperationType;
import com.dylan.agent.adapter.api.operation.ProviderSafeIdentity;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;
import java.time.Instant;
import java.util.*;
import static org.assertj.core.api.Assertions.*;

class DocumentProviderOperationServiceTest {
    private static final CapabilityOperationType TYPE = CapabilityOperationType.of("DOCUMENT_REWRITE");

    @Test
    void acceptsOneBoundRequestAndRejectsReplay() {
        DocumentProviderCanonicalizer canonicalizer = new DocumentProviderCanonicalizer(new ObjectMapper());
        DocumentProviderActivationSnapshot snapshot = snapshot(canonicalizer);
        DocumentProviderActivationReadView view = activeView(canonicalizer, snapshot);
        DocumentVendorClient vendor = new StubVendorClient();
        DocumentProviderOperationService service = new DocumentProviderOperationService(
                view, new DocumentProviderReplayGuard(), vendor, canonicalizer);
        var request = request(canonicalizer, "op-1", snapshot.canonicalDigest(),
                snapshot.expectedProvider().orElseThrow().canonicalDigest());

        var response = service.rewrite("agent-service", request);

        assertThat(response.payload().candidates()).containsExactly("税收优惠政策");
        assertThat(response.providerBinding()).isEqualTo(snapshot.expectedProvider().orElseThrow());
        assertThatThrownBy(() -> service.rewrite("agent-service", request))
                .isInstanceOf(ProviderAdapterException.class)
                .extracting(ex -> ((ProviderAdapterException) ex).code)
                .isEqualTo(DocumentProviderAdapterFailureCode.REQUEST_REJECTED);
    }

    @Test
    void failsClosedWhenActivationIsUnavailable() {
        DocumentProviderCanonicalizer canonicalizer = new DocumentProviderCanonicalizer(new ObjectMapper());
        DocumentProviderOperationService service = new DocumentProviderOperationService(
                new DocumentProviderActivationReadView(canonicalizer), new DocumentProviderReplayGuard(),
                new StubVendorClient(), canonicalizer);
        var request = request(canonicalizer, "op-2", "a".repeat(64), "c".repeat(64));

        assertThatThrownBy(() -> service.rewrite("agent-service", request))
                .isInstanceOf(ProviderAdapterException.class)
                .extracting(ex -> ((ProviderAdapterException) ex).code)
                .isEqualTo(DocumentProviderAdapterFailureCode.ACTIVATION_REJECTED);
    }

    @Test
    void rejectsTamperedInputBeforeVendorInvocation() {
        DocumentProviderCanonicalizer canonicalizer = new DocumentProviderCanonicalizer(new ObjectMapper());
        DocumentProviderActivationSnapshot snapshot = snapshot(canonicalizer);
        DocumentProviderActivationReadView view = activeView(canonicalizer, snapshot);
        java.util.concurrent.atomic.AtomicInteger attempts = new java.util.concurrent.atomic.AtomicInteger();
        DocumentVendorClient vendor = new StubVendorClient() {
            @Override public DocumentUntrustedRewritePayload rewrite(DocumentRewriteInputProjection input,
                                                                      DocumentProviderBindingReference binding) {
                attempts.incrementAndGet();
                return super.rewrite(input, binding);
            }
        };
        DocumentProviderOperationService service = new DocumentProviderOperationService(
                view, new DocumentProviderReplayGuard(), vendor, canonicalizer);
        var valid = request(canonicalizer, "op-tamper", snapshot.canonicalDigest(),
                snapshot.expectedProvider().orElseThrow().canonicalDigest());
        var tampered = new DocumentProviderWireRequest<>(valid.wireContractVersion(), valid.operationId(),
                valid.operationType(), valid.requestDigest(), valid.absoluteDeadlineEpochMillis(),
                valid.expectedActivationDigest(), valid.expectedProviderBindingDigest(),
                new DocumentRewriteInputProjection("被篡改", "zh-CN", 2));

        assertThatThrownBy(() -> service.rewrite("agent-service", tampered))
                .isInstanceOf(ProviderAdapterException.class)
                .extracting(ex -> ((ProviderAdapterException) ex).code)
                .isEqualTo(DocumentProviderAdapterFailureCode.REQUEST_REJECTED);
        assertThat(attempts).hasValue(0);
    }

    @Test
    void rejectsOperationTypeThatDoesNotMatchEndpoint() {
        DocumentProviderCanonicalizer canonicalizer = new DocumentProviderCanonicalizer(new ObjectMapper());
        DocumentProviderOperationService service = new DocumentProviderOperationService(
                new DocumentProviderActivationReadView(canonicalizer), new DocumentProviderReplayGuard(),
                new StubVendorClient(), canonicalizer);
        CapabilityOperationType embedding = CapabilityOperationType.of("DOCUMENT_EMBEDDING");
        long deadline = Instant.now().plusSeconds(10).toEpochMilli();
        var input = new DocumentRewriteInputProjection("税收优惠", "zh-CN", 2);
        String digest = canonicalizer.wireRequestDigest("DPW-1", "op-wrong", embedding, deadline,
                "a".repeat(64), "c".repeat(64), input);
        var request = new DocumentProviderWireRequest<>("DPW-1", "op-wrong", embedding, digest, deadline,
                "a".repeat(64), "c".repeat(64), input);

        assertThatThrownBy(() -> service.rewrite("agent-service", request))
                .isInstanceOf(ProviderAdapterException.class)
                .extracting(ex -> ((ProviderAdapterException) ex).code)
                .isEqualTo(DocumentProviderAdapterFailureCode.REQUEST_REJECTED);
    }

    private static DocumentProviderBindingReference binding(DocumentProviderCanonicalizer canonicalizer) {
        ProviderSafeIdentity provider = new ProviderSafeIdentity("provider-safe", Optional.of("model-safe"));
        String digest = canonicalizer.providerBindingDigest(TYPE, provider, "document-provider-adapter",
                "deployment-1", "vendor-v1", "d".repeat(64));
        return new DocumentProviderBindingReference(TYPE,
                provider, "document-provider-adapter", "deployment-1", "vendor-v1", "d".repeat(64), digest);
    }

    private static DocumentProviderActivationSnapshot snapshot(DocumentProviderCanonicalizer canonicalizer) {
        DocumentProviderBindingReference binding = binding(canonicalizer);
        Instant validUntil = Instant.now().plusSeconds(30);
        String digest = canonicalizer.activationSnapshotDigest(TYPE, DocumentProviderActivationState.ACTIVE,
                binding, "DPW-1", "rollout-1", validUntil);
        return new DocumentProviderActivationSnapshot(TYPE, DocumentProviderActivationState.ACTIVE,
                Optional.of(binding), "DPW-1", "rollout-1", validUntil, digest);
    }

    private static DocumentProviderActivationReadView activeView(
            DocumentProviderCanonicalizer canonicalizer, DocumentProviderActivationSnapshot snapshot) {
        DocumentProviderActivationReadView view = new DocumentProviderActivationReadView(canonicalizer);
        view.replace(Map.of(TYPE, snapshot));
        return view;
    }

    private static DocumentProviderWireRequest<DocumentRewriteInputProjection> request(
            DocumentProviderCanonicalizer canonicalizer, String operationId,
            String activationDigest, String bindingDigest) {
        long deadline = Instant.now().plusSeconds(10).toEpochMilli();
        var input = new DocumentRewriteInputProjection("税收优惠", "zh-CN", 2);
        String digest = canonicalizer.wireRequestDigest(
                "DPW-1", operationId, TYPE, deadline, activationDigest, bindingDigest, input);
        return new DocumentProviderWireRequest<>("DPW-1", operationId, TYPE, digest, deadline,
                activationDigest, bindingDigest, input);
    }

    private static class StubVendorClient implements DocumentVendorClient {
        @Override public DocumentUntrustedRewritePayload rewrite(DocumentRewriteInputProjection input, DocumentProviderBindingReference binding) { return new DocumentUntrustedRewritePayload(List.of("税收优惠政策")); }
        @Override public DocumentUntrustedEmbeddingPayload embedding(DocumentEmbeddingInputProjection input, DocumentProviderBindingReference binding) { throw new UnsupportedOperationException(); }
        @Override public DocumentUntrustedRerankPayload rerank(DocumentRerankInputProjection input, DocumentProviderBindingReference binding) { throw new UnsupportedOperationException(); }
        @Override public DocumentUntrustedGenerationPayload generation(DocumentGenerationInputProjection input, DocumentProviderBindingReference binding) { throw new UnsupportedOperationException(); }
    }
}
