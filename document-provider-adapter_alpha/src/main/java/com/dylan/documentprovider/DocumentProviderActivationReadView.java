package com.dylan.documentprovider;

import com.dylan.agent.adapter.api.document.provider.*;
import com.dylan.agent.adapter.api.operation.CapabilityOperationType;
import org.springframework.stereotype.Component;
import java.time.Instant;
import java.util.Map;
import java.util.concurrent.atomic.AtomicReference;

/** 07 feed 的本地 fail-closed projection；启动或过期时拒绝外发。 */
@Component
public final class DocumentProviderActivationReadView {
    private final DocumentProviderCanonicalizer canonicalizer;
    private final AtomicReference<State> current = new AtomicReference<>(new State(Map.of(), Instant.EPOCH));

    public DocumentProviderActivationReadView(DocumentProviderCanonicalizer canonicalizer) {
        this.canonicalizer = canonicalizer;
    }

    public DocumentProviderActivationSnapshot requireCurrent(CapabilityOperationType type) {
        State state = current.get();
        DocumentProviderActivationSnapshot snapshot = state.snapshots().get(type);
        if (snapshot == null || snapshot.state() != DocumentProviderActivationState.ACTIVE
                || !Instant.now().isBefore(snapshot.validUntil()) || !Instant.now().isBefore(state.distributionValidUntil())
                || snapshot.expectedProvider().filter(value -> !value.canonicalDigest().equals(
                canonicalizer.providerBindingDigest(value))).isPresent()
                || !snapshot.canonicalDigest().equals(canonicalizer.activationSnapshotDigest(snapshot))) {
            throw new IllegalStateException("activation unavailable");
        }
        return snapshot;
    }

    public void replace(Map<CapabilityOperationType, DocumentProviderActivationSnapshot> next) {
        Instant validUntil = next.values().stream().map(DocumentProviderActivationSnapshot::validUntil)
                .min(Instant::compareTo).orElse(Instant.EPOCH);
        replace(next, validUntil);
    }

    public void replace(Map<CapabilityOperationType, DocumentProviderActivationSnapshot> next,
                        Instant distributionValidUntil) {
        current.set(new State(Map.copyOf(next), distributionValidUntil));
    }

    private record State(Map<CapabilityOperationType, DocumentProviderActivationSnapshot> snapshots,
                         Instant distributionValidUntil) {}
}
