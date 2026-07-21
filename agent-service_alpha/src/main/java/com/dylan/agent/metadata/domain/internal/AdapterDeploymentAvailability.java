package com.dylan.agent.metadata.domain.internal;

import com.dylan.agent.metadata.domain.port.DomainAdapterKey;

import java.time.Instant;
import java.util.Map;
import java.util.Objects;

/** 本次请求捕获的最小 deployment/health availability。 */
public record AdapterDeploymentAvailability(
        Map<DomainAdapterKey, Entry> entries,
        Instant capturedAt,
        String canonicalDigest) {

    public AdapterDeploymentAvailability {
        entries = Map.copyOf(Objects.requireNonNull(entries, "entries must not be null"));
        Objects.requireNonNull(capturedAt, "capturedAt must not be null");
        canonicalDigest = DomainMetadataCanonicalizer.requireDigest(canonicalDigest, "canonicalDigest");
        String values = entries.entrySet().stream()
                .sorted(Map.Entry.comparingByKey())
                .map(entry -> DomainMetadataCanonicalizer.canonical(
                        entry.getKey().role().value(), entry.getKey().domain(),
                        entry.getValue().status().name(), entry.getValue().reasonCode().name()))
                .collect(java.util.stream.Collectors.joining());
        String expected = DomainMetadataCanonicalizer.digest("DAV-1", values);
        if (!canonicalDigest.equals(expected)) {
            throw new IllegalArgumentException("canonicalDigest does not match availability entries");
        }
    }

    public boolean isAvailable(DomainAdapterKey key) {
        Entry entry = entries.get(key);
        return entry != null && entry.status() == Status.AVAILABLE;
    }

    public static AdapterDeploymentAvailability capture(
            Map<DomainAdapterKey, Entry> entries,
            Instant capturedAt) {
        String values = entries.entrySet().stream()
                .sorted(Map.Entry.comparingByKey())
                .map(entry -> DomainMetadataCanonicalizer.canonical(
                        entry.getKey().role().value(), entry.getKey().domain(),
                        entry.getValue().status().name(), entry.getValue().reasonCode().name()))
                .collect(java.util.stream.Collectors.joining());
        return new AdapterDeploymentAvailability(
                entries, capturedAt, DomainMetadataCanonicalizer.digest("DAV-1", values));
    }

    public enum Status { AVAILABLE, UNAVAILABLE }

    public enum ReasonCode {
        AVAILABLE,
        BEAN_MISSING,
        PORT_TYPE_MISMATCH,
        DEADLINE_EXCEEDED,
        UNKNOWN
    }

    public record Entry(Status status, ReasonCode reasonCode) {
        public Entry {
            Objects.requireNonNull(status, "status must not be null");
            Objects.requireNonNull(reasonCode, "reasonCode must not be null");
            if ((status == Status.AVAILABLE) != (reasonCode == ReasonCode.AVAILABLE)) {
                throw new IllegalArgumentException("availability status/reason mismatch");
            }
        }
    }
}
