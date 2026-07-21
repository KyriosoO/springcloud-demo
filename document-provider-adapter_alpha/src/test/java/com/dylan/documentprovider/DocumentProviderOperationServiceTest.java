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
                view, new DocumentProviderReplayGuard(), vendor, canonicalizer,
                properties(), java.time.Clock.systemUTC());
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
                new StubVendorClient(), canonicalizer, properties(), java.time.Clock.systemUTC());
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
                view, new DocumentProviderReplayGuard(), vendor, canonicalizer,
                properties(), java.time.Clock.systemUTC());
        var valid = request(canonicalizer, "op-tamper", snapshot.canonicalDigest(),
                snapshot.expectedProvider().orElseThrow().canonicalDigest());
        var tampered = new DocumentProviderWireRequest<>(valid.wireContractVersion(), valid.operationId(),
                valid.operationType(), valid.requestDigest(), valid.absoluteDeadlineEpochMillis(),
                valid.expectedActivationDigest(), valid.expectedProviderBindingDigest(),
                new DocumentRewriteInputProjection("被篡改", DocumentLanguage.ZH_CN, 2));

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
                new StubVendorClient(), canonicalizer, properties(), java.time.Clock.systemUTC());
        CapabilityOperationType embedding = CapabilityOperationType.of("DOCUMENT_EMBEDDING");
        long deadline = Instant.now().plusSeconds(10).toEpochMilli();
        var input = new DocumentRewriteInputProjection("税收优惠", DocumentLanguage.ZH_CN, 2);
        String digest = canonicalizer.wireRequestDigest("DPW-1", "op-wrong", embedding, deadline,
                "a".repeat(64), "c".repeat(64), input);
        var request = new DocumentProviderWireRequest<>("DPW-1", "op-wrong", embedding, digest, deadline,
                "a".repeat(64), "c".repeat(64), input);

        assertThatThrownBy(() -> service.rewrite("agent-service", request))
                .isInstanceOf(ProviderAdapterException.class)
                .extracting(ex -> ((ProviderAdapterException) ex).code)
                .isEqualTo(DocumentProviderAdapterFailureCode.REQUEST_REJECTED);
    }

    @Test
    void rejectsDeadlineBeyondOperationalStageHorizonBeforeVendorInvocation() {
        DocumentProviderCanonicalizer canonicalizer = new DocumentProviderCanonicalizer(new ObjectMapper());
        DocumentProviderActivationSnapshot snapshot = snapshot(canonicalizer);
        DocumentProviderActivationReadView view = activeView(canonicalizer, snapshot);
        java.util.concurrent.atomic.AtomicInteger attempts = new java.util.concurrent.atomic.AtomicInteger();
        DocumentVendorClient vendor = new StubVendorClient() {
            @Override public DocumentUntrustedRewritePayload rewrite(
                    DocumentRewriteInputProjection input, DocumentProviderBindingReference binding) {
                attempts.incrementAndGet();
                return super.rewrite(input, binding);
            }
        };
        DocumentProviderOperationService service = new DocumentProviderOperationService(
                view, new DocumentProviderReplayGuard(), vendor, canonicalizer,
                properties(), java.time.Clock.systemUTC());
        long deadline = Instant.now().plusSeconds(120).toEpochMilli();
        var input = new DocumentRewriteInputProjection("税收优惠", DocumentLanguage.ZH_CN, 2);
        String digest = canonicalizer.wireRequestDigest(
                "DPW-1", "op-horizon", TYPE, deadline, snapshot.canonicalDigest(),
                snapshot.expectedProvider().orElseThrow().canonicalDigest(), input);
        var request = new DocumentProviderWireRequest<>(
                "DPW-1", "op-horizon", TYPE, digest, deadline, snapshot.canonicalDigest(),
                snapshot.expectedProvider().orElseThrow().canonicalDigest(), input);

        assertThatThrownBy(() -> service.rewrite("agent-service", request))
                .isInstanceOf(ProviderAdapterException.class)
                .extracting(ex -> ((ProviderAdapterException) ex).code)
                .isEqualTo(DocumentProviderAdapterFailureCode.REQUEST_REJECTED);
        assertThat(attempts).hasValue(0);
    }

    @Test
    void rejectsEmbeddingBindingNotOwnedByActiveProvider() {
        CapabilityOperationType embeddingType = CapabilityOperationType.of("DOCUMENT_EMBEDDING");
        DocumentProviderCanonicalizer canonicalizer = new DocumentProviderCanonicalizer(new ObjectMapper());
        DocumentProviderActivationSnapshot snapshot = snapshot(canonicalizer, embeddingType);
        DocumentProviderActivationReadView view = activeView(canonicalizer, snapshot);
        DocumentVendorClient vendor = new StubVendorClient() {
            @Override public DocumentUntrustedEmbeddingPayload embedding(
                    DocumentEmbeddingInputProjection input, DocumentProviderBindingReference binding) {
                return new DocumentUntrustedEmbeddingPayload(
                        List.of(List.of(1.0f, 2.0f)), 2,
                        new com.dylan.agent.adapter.api.document.DocumentEmbeddingBindingReference(
                                "e".repeat(64), 2));
            }
        };
        DocumentProviderOperationService service = new DocumentProviderOperationService(
                view, new DocumentProviderReplayGuard(), vendor, canonicalizer,
                properties(), java.time.Clock.systemUTC());
        long deadline = Instant.now().plusSeconds(10).toEpochMilli();
        var input = new DocumentEmbeddingInputProjection(List.of("税收优惠"));
        String digest = canonicalizer.wireRequestDigest(
                "DPW-1", "op-embedding", embeddingType, deadline, snapshot.canonicalDigest(),
                snapshot.expectedProvider().orElseThrow().canonicalDigest(), input);
        var request = new DocumentProviderWireRequest<>(
                "DPW-1", "op-embedding", embeddingType, digest, deadline, snapshot.canonicalDigest(),
                snapshot.expectedProvider().orElseThrow().canonicalDigest(), input);

        assertThatThrownBy(() -> service.embedding("agent-service", request))
                .isInstanceOf(ProviderAdapterException.class)
                .extracting(ex -> ((ProviderAdapterException) ex).code)
                .isEqualTo(DocumentProviderAdapterFailureCode.VENDOR_INVALID_RESPONSE);
    }

    private static DocumentProviderBindingReference binding(DocumentProviderCanonicalizer canonicalizer) {
        return binding(canonicalizer, TYPE);
    }

    private static DocumentProviderBindingReference binding(
            DocumentProviderCanonicalizer canonicalizer,
            CapabilityOperationType type) {
        ProviderSafeIdentity provider = new ProviderSafeIdentity("provider-safe", Optional.of("model-safe"));
        String digest = canonicalizer.providerBindingDigest(type, provider, "document-provider-adapter",
                "deployment-1", "vendor-v1", "d".repeat(64));
        return new DocumentProviderBindingReference(type,
                provider, "document-provider-adapter", "deployment-1", "vendor-v1", "d".repeat(64), digest);
    }

    private static DocumentProviderActivationSnapshot snapshot(DocumentProviderCanonicalizer canonicalizer) {
        return snapshot(canonicalizer, TYPE);
    }

    private static DocumentProviderActivationSnapshot snapshot(
            DocumentProviderCanonicalizer canonicalizer,
            CapabilityOperationType type) {
        DocumentProviderBindingReference binding = binding(canonicalizer, type);
        Instant validUntil = Instant.now().plusSeconds(30);
        String digest = canonicalizer.activationSnapshotDigest(type, DocumentProviderActivationState.ACTIVE,
                binding, "DPW-1", "rollout-1", validUntil);
        return new DocumentProviderActivationSnapshot(type, DocumentProviderActivationState.ACTIVE,
                Optional.of(binding), "DPW-1", "rollout-1", validUntil, digest);
    }

    private static DocumentProviderActivationReadView activeView(
            DocumentProviderCanonicalizer canonicalizer, DocumentProviderActivationSnapshot snapshot) {
        DocumentProviderActivationReadView view = new DocumentProviderActivationReadView(canonicalizer);
        view.replace(Map.of(snapshot.operationType(), snapshot));
        return view;
    }

    private static DocumentProviderWireRequest<DocumentRewriteInputProjection> request(
            DocumentProviderCanonicalizer canonicalizer, String operationId,
            String activationDigest, String bindingDigest) {
        long deadline = Instant.now().plusSeconds(10).toEpochMilli();
        var input = new DocumentRewriteInputProjection("税收优惠", DocumentLanguage.ZH_CN, 2);
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

    private static DocumentProviderOperationProperties properties() {
        return new DocumentProviderOperationProperties();
    }
}
