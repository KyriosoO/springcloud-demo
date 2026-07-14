package com.dylan.agent.capability.document.governance.provider;

import com.dylan.agent.adapter.api.document.provider.*;
import com.dylan.agent.adapter.api.operation.CapabilityOperationType;
import com.dylan.agent.adapter.api.operation.ProviderSafeIdentity;
import org.springframework.jdbc.core.JdbcTemplate;
import java.time.Clock;
import java.util.*;

/** 07 authoritative activation feed 与 consumer acknowledgement。 */
public final class DocumentProviderActivationPublisher {
    private final JdbcTemplate jdbc;
    private final Clock clock;
    private final DocumentProviderCanonicalizer canonicalizer;

    public DocumentProviderActivationPublisher(JdbcTemplate jdbc, Clock clock, DocumentProviderCanonicalizer canonicalizer) { this.jdbc = jdbc; this.clock = clock; this.canonicalizer = canonicalizer; }

    public List<DocumentProviderActivationSnapshot> current() {
        return jdbc.query("SELECT operation_type,state,provider_safe_identity,provider_model_identity,adapter_service_identity_ref,adapter_deployment_ref,vendor_contract_version,template_model_digest,provider_binding_digest,wire_contract_version,rollout_version,valid_until,snapshot_digest FROM document_provider_activation",
                (rs, i) -> {
                    CapabilityOperationType type = CapabilityOperationType.of(rs.getString(1));
                    DocumentProviderActivationState state = DocumentProviderActivationState.valueOf(rs.getString(2));
                    DocumentProviderBindingReference binding = state == DocumentProviderActivationState.ACTIVE
                            ? new DocumentProviderBindingReference(type,
                            new ProviderSafeIdentity(rs.getString(3), Optional.ofNullable(rs.getString(4))), rs.getString(5), rs.getString(6),
                            rs.getString(7), rs.getString(8), rs.getString(9)) : null;
                    return new DocumentProviderActivationSnapshot(type, state, Optional.ofNullable(binding),
                            rs.getString(10), rs.getString(11), rs.getTimestamp(12).toInstant(), rs.getString(13));
                }).stream().filter(snapshot -> clock.instant().isBefore(snapshot.validUntil())).peek(snapshot -> {
                    if (snapshot.expectedProvider().filter(value -> !value.canonicalDigest().equals(canonicalizer.providerBindingDigest(value))).isPresent()
                            || !snapshot.canonicalDigest().equals(canonicalizer.activationSnapshotDigest(snapshot))) {
                        throw new IllegalStateException("provider activation feed integrity failure");
                    }
                }).toList();
    }

    public void acknowledge(String consumerId, CapabilityOperationType operationType,
                            String deploymentDigest, String activationDigest) {
        if (consumerId == null || consumerId.isBlank() || deploymentDigest == null || !deploymentDigest.matches("[0-9a-f]{64}")
                || operationType == null || activationDigest == null || !activationDigest.matches("[0-9a-f]{64}")) {
            throw new IllegalArgumentException("invalid activation acknowledgement");
        }
        jdbc.update("INSERT INTO document_provider_activation_ack(consumer_id,operation_type,deployment_digest,activation_digest,observed_at) VALUES(?,?,?,?,?) ON DUPLICATE KEY UPDATE deployment_digest=VALUES(deployment_digest),activation_digest=VALUES(activation_digest),observed_at=VALUES(observed_at)",
                consumerId, operationType.value(), deploymentDigest, activationDigest, java.sql.Timestamp.from(clock.instant()));
    }
}
