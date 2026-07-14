package com.dylan.agent.capability.document.provider;

import com.dylan.agent.adapter.api.document.provider.DocumentProviderBindingReference;
import com.dylan.agent.adapter.api.operation.CapabilityOperationMetadata;

import java.time.Clock;
import java.time.Instant;
import java.util.Objects;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.ConcurrentMap;

/** P1 metadata 与 P2 trusted candidate 之间的短效、一次性 Provider binding sidecar。 */
public final class DocumentProviderOperationBindingRegistry {
    private final Clock clock;
    private final ConcurrentMap<String, Entry> entries = new ConcurrentHashMap<>();

    public DocumentProviderOperationBindingRegistry(Clock clock) {
        this.clock = Objects.requireNonNull(clock, "clock must not be null");
    }

    public void publish(
            String operationId,
            DocumentProviderBindingReference binding,
            Instant validUntil) {
        requireText(operationId, "operationId");
        Objects.requireNonNull(binding, "binding must not be null");
        Objects.requireNonNull(validUntil, "validUntil must not be null");
        cleanupExpired();
        if (!clock.instant().isBefore(validUntil)
                || entries.putIfAbsent(operationId, new Entry(binding, validUntil)) != null) {
            throw new IllegalStateException("document provider operation binding cannot be published");
        }
    }

    public DocumentProviderBindingReference consume(CapabilityOperationMetadata metadata) {
        Objects.requireNonNull(metadata, "metadata must not be null");
        Entry entry = entries.remove(metadata.operationId());
        if (entry == null || !clock.instant().isBefore(entry.validUntil())
                || !metadata.operationType().equals(entry.binding().operationType())
                || !metadata.provider().equals(entry.binding().provider())) {
            throw new IllegalArgumentException("trusted document provider binding missing or mismatched");
        }
        return entry.binding();
    }

    private void cleanupExpired() {
        Instant now = clock.instant();
        entries.entrySet().removeIf(entry -> !now.isBefore(entry.getValue().validUntil()));
    }

    private static String requireText(String value, String name) {
        if (value == null || value.isBlank()) {
            throw new IllegalArgumentException(name + " must not be blank");
        }
        return value;
    }

    private record Entry(DocumentProviderBindingReference binding, Instant validUntil) {}
}
