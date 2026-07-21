package com.dylan.agent.capability.document.governance.provider;

import com.dylan.agent.adapter.api.document.provider.*;
import com.dylan.agent.adapter.api.operation.CapabilityOperationType;
import com.dylan.agent.capability.document.governance.validation.DocumentValidationModels;
import com.dylan.agent.capability.document.governance.emergency.DocumentEmergencyGateCanonicalizer;
import com.dylan.agent.capability.document.governance.emergency.DocumentEmergencyTargetRef;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.transaction.annotation.Transactional;

import java.sql.Timestamp;
import java.nio.ByteBuffer;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.time.Clock;
import java.time.Duration;
import java.time.Instant;
import java.util.*;

/** Provider operation current authority；binding replacement 强制 break-before-make。 */
public final class DocumentProviderActivationCoordinator {
    public static final String WIRE_CONTRACT_VERSION = "DPW-1";
    private final JdbcTemplate jdbc;
    private final Clock clock;
    private final Duration snapshotTtl;
    private final DocumentProviderCanonicalizer canonicalizer;

    public DocumentProviderActivationCoordinator(JdbcTemplate jdbc, Clock clock, Duration snapshotTtl,
                                                 DocumentProviderCanonicalizer canonicalizer) {
        this.jdbc = jdbc;
        this.clock = clock;
        this.snapshotTtl = snapshotTtl;
        this.canonicalizer = Objects.requireNonNull(canonicalizer);
        if (snapshotTtl.isZero() || snapshotTtl.isNegative()) throw new IllegalArgumentException("snapshotTtl must be positive");
    }

    @Transactional
    public DocumentProviderActivationSnapshot deactivate(
            CapabilityOperationType operationType, String rolloutVersion, String changeId, String reasonCode) {
        return deactivate(operationType, rolloutVersion, changeId, reasonCode, null);
    }

    @Transactional
    public DocumentProviderActivationSnapshot deactivateForEmergency(
            CapabilityOperationType operationType, String rolloutVersion, String changeId,
            String reasonCode, String emergencyCauseRef) {
        requireText(emergencyCauseRef, "emergencyCauseRef");
        return deactivate(operationType, rolloutVersion, changeId, reasonCode, emergencyCauseRef);
    }

    private DocumentProviderActivationSnapshot deactivate(
            CapabilityOperationType operationType, String rolloutVersion, String changeId,
            String reasonCode, String emergencyCauseRef) {
        requireText(rolloutVersion, "rolloutVersion");
        requireText(changeId, "changeId");
        requireText(reasonCode, "reasonCode");
        Current current = lock(operationType);
        Instant validUntil = clock.instant().plus(snapshotTtl);
        String digest = canonicalizer.activationSnapshotDigest(operationType, DocumentProviderActivationState.INACTIVE,
                null, WIRE_CONTRACT_VERSION, rolloutVersion, validUntil);
        persist(operationType, DocumentProviderActivationState.INACTIVE, null, rolloutVersion, digest,
                validUntil, current == null ? -1 : current.rowVersion(), emergencyCauseRef);
        appendHistory(operationType, DocumentProviderActivationState.INACTIVE, current == null ? null : current.bindingDigest(),
                rolloutVersion, digest, changeId, reasonCode);
        return snapshot(operationType, DocumentProviderActivationState.INACTIVE, null, rolloutVersion, validUntil, digest);
    }

    @Transactional
    public DocumentProviderActivationSnapshot activate(
            DocumentProviderBindingReference binding,
            String rolloutVersion,
            String changeId,
            DocumentValidationModels.ReleaseGateEvidence gate,
            Map<String, String> requiredConsumers) {
        Objects.requireNonNull(binding);
        if (!binding.canonicalDigest().equals(canonicalizer.providerBindingDigest(binding))) {
            throw new IllegalArgumentException("provider binding digest mismatch");
        }
        requireText(rolloutVersion, "rolloutVersion");
        requireText(changeId, "changeId");
        Objects.requireNonNull(gate);
        validateRequiredConsumers(requiredConsumers);
        Instant now = clock.instant();
        if (!now.isBefore(gate.expiresAt()) || gate.issuedAt().isAfter(now)
                || !"PROVIDER_OPERATION".equals(gate.unitType())) {
            throw new IllegalStateException("current provider release gate evidence required");
        }
        if (!gate.exactTargetStateDigest().equals(binding.canonicalDigest())
                || !gate.unitKeyDigest().equals(unitKeyDigest(binding.operationType()))
                || !gate.canonicalDigest().equals(gateCanonical(gate))) {
            throw new IllegalStateException("release gate does not bind exact provider target");
        }
        assertNotEmergencyBlocked(binding);
        Current current = lock(binding.operationType());
        String currentDigest = current == null
                ? digest("PROVIDER-MISSING-1", binding.operationType().value()) : current.snapshotDigest();
        if (!gate.expectedStateDigest().equals(currentDigest)) {
            throw new IllegalStateException("release gate does not bind current provider state");
        }
        if (current != null && "ACTIVE".equals(current.state())
                && !binding.canonicalDigest().equals(current.bindingDigest())) {
            throw new IllegalStateException("provider replacement requires INACTIVE barrier first");
        }
        if (current != null && "INACTIVE".equals(current.state()) && current.rowVersion() > 0) {
            assertConsumerBarrier(binding.operationType(), current.snapshotDigest(), requiredConsumers);
        }
        Instant validUntil = clock.instant().plus(snapshotTtl);
        String digest = canonicalizer.activationSnapshotDigest(binding.operationType(), DocumentProviderActivationState.ACTIVE,
                binding, WIRE_CONTRACT_VERSION, rolloutVersion, validUntil);
        persist(binding.operationType(), DocumentProviderActivationState.ACTIVE, binding, rolloutVersion, digest,
                validUntil, current == null ? -1 : current.rowVersion(), null);
        appendHistory(binding.operationType(), DocumentProviderActivationState.ACTIVE, binding.canonicalDigest(),
                rolloutVersion, digest, changeId, "GATE_PASSED");
        return snapshot(binding.operationType(), DocumentProviderActivationState.ACTIVE, binding, rolloutVersion, validUntil, digest);
    }

    private void assertConsumerBarrier(CapabilityOperationType operationType, String inactiveDigest,
                                       Map<String, String> requiredConsumers) {
        validateRequiredConsumers(requiredConsumers);
        for (var required : requiredConsumers.entrySet()) {
            requireText(required.getKey(), "consumerId");
            requireDigest(required.getValue(), "consumerDeploymentDigest");
            int count = jdbc.queryForObject("SELECT COUNT(*) FROM document_provider_activation_ack WHERE consumer_id=? AND operation_type=? AND deployment_digest=? AND activation_digest=? AND observed_at>?",
                    Integer.class, required.getKey(), operationType.value(), required.getValue(), inactiveDigest,
                    Timestamp.from(clock.instant().minus(snapshotTtl)));
            if (count != 1) throw new IllegalStateException(
                    "consumer has not acknowledged INACTIVE barrier: " + required.getKey());
        }
    }

    private static void validateRequiredConsumers(Map<String, String> requiredConsumers) {
        if (requiredConsumers == null || requiredConsumers.isEmpty()) {
            throw new IllegalStateException("consumer deployment coverage required before provider activation");
        }
        requiredConsumers.forEach((consumer, deployment) -> {
            requireText(consumer, "consumerId");
            requireDigest(deployment, "consumerDeploymentDigest");
        });
    }

    private void assertNotEmergencyBlocked(DocumentProviderBindingReference binding) {
        String operationTarget = DocumentEmergencyGateCanonicalizer.targetBinding(
                new DocumentEmergencyTargetRef.ProviderOperationTarget(binding.operationType())).targetKeyDigest();
        String bindingTarget = DocumentEmergencyGateCanonicalizer.targetBinding(
                new DocumentEmergencyTargetRef.ProviderBindingTarget(binding.canonicalDigest())).targetKeyDigest();
        Integer count = jdbc.queryForObject("SELECT COUNT(*) FROM document_emergency_control WHERE state='ACTIVE' AND ((target_type='PROVIDER_OPERATION' AND target_key_digest=?) OR (target_type='PROVIDER_BINDING' AND target_key_digest=?))",
                Integer.class, operationTarget, bindingTarget);
        if (count != null && count > 0) throw new IllegalStateException("provider activation blocked by emergency control");
    }

    private static String gateCanonical(DocumentValidationModels.ReleaseGateEvidence gate) {
        return digest("DRG-1", gate.unitType(), gate.unitKeyDigest(), gate.expectedStateDigest(), gate.exactTargetStateDigest(),
                gate.reportCanonicalDigest(), gate.approvalSafeRef(), gate.issuedAt().toString(), gate.expiresAt().toString());
    }

    static String unitKeyDigest(CapabilityOperationType operationType){
        return digest("PROVIDER-OPERATION-UNIT-1",operationType.value());
    }

    private static String digest(String... values) {
        try {
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            for (String value : values) {
                byte[] bytes = value.getBytes(StandardCharsets.UTF_8);
                digest.update(ByteBuffer.allocate(4).putInt(bytes.length).array());
                digest.update(bytes);
            }
            return HexFormat.of().formatHex(digest.digest());
        } catch (Exception ex) { throw new IllegalStateException(ex); }
    }

    private Current lock(CapabilityOperationType operationType) {
        List<Current> rows = jdbc.query("SELECT state,provider_binding_digest,snapshot_digest,row_version FROM document_provider_activation WHERE operation_type=? FOR UPDATE",
                (rs, row) -> new Current(rs.getString(1), rs.getString(2), rs.getString(3), rs.getLong(4)),
                operationType.value());
        return rows.isEmpty() ? null : rows.getFirst();
    }

    private void persist(CapabilityOperationType type, DocumentProviderActivationState state,
                         DocumentProviderBindingReference binding, String rolloutVersion, String snapshotDigest,
                         Instant validUntil, long expectedVersion, String emergencyCauseRef) {
        if (expectedVersion < 0) {
            jdbc.update("INSERT INTO document_provider_activation(operation_type,state,provider_safe_identity,provider_model_identity,adapter_service_identity_ref,adapter_deployment_ref,vendor_contract_version,template_model_digest,provider_binding_digest,wire_contract_version,rollout_version,valid_until,snapshot_digest,emergency_cause_ref,row_version,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,0,?)",
                    type.value(), state.name(), binding == null ? null : binding.provider().providerId(),
                    binding == null ? null : binding.provider().modelRef().orElse(null),
                    binding == null ? null : binding.adapterServiceIdentityRef(),
                    binding == null ? null : binding.adapterDeploymentRef(),
                    binding == null ? null : binding.vendorContractVersion(),
                    binding == null ? null : binding.templateOrModelBindingDigest(),
                    binding == null ? null : binding.canonicalDigest(), WIRE_CONTRACT_VERSION, rolloutVersion,
                    Timestamp.from(validUntil), snapshotDigest, emergencyCauseRef, Timestamp.from(clock.instant()));
            return;
        }
        int updated = jdbc.update("UPDATE document_provider_activation SET state=?,provider_safe_identity=?,provider_model_identity=?,adapter_service_identity_ref=?,adapter_deployment_ref=?,vendor_contract_version=?,template_model_digest=?,provider_binding_digest=?,wire_contract_version=?,rollout_version=?,valid_until=?,snapshot_digest=?,emergency_cause_ref=?,row_version=row_version+1,updated_at=? WHERE operation_type=? AND row_version=?",
                state.name(), binding == null ? null : binding.provider().providerId(),
                binding == null ? null : binding.provider().modelRef().orElse(null),
                binding == null ? null : binding.adapterServiceIdentityRef(), binding == null ? null : binding.adapterDeploymentRef(),
                binding == null ? null : binding.vendorContractVersion(), binding == null ? null : binding.templateOrModelBindingDigest(),
                binding == null ? null : binding.canonicalDigest(), WIRE_CONTRACT_VERSION, rolloutVersion,
                Timestamp.from(validUntil), snapshotDigest, emergencyCauseRef, Timestamp.from(clock.instant()),
                type.value(), expectedVersion);
        if (updated != 1) throw new IllegalStateException("provider activation CAS conflict");
    }

    private void appendHistory(CapabilityOperationType type, DocumentProviderActivationState state,
                               String bindingDigest, String rolloutVersion, String snapshotDigest,
                               String changeId, String reasonCode) {
        jdbc.update("INSERT INTO document_provider_activation_history(history_id,operation_type,state,provider_binding_digest,rollout_version,snapshot_digest,change_id,reason_code,created_at) VALUES(?,?,?,?,?,?,?,?,?)",
                UUID.randomUUID().toString(), type.value(), state.name(), bindingDigest, rolloutVersion,
                snapshotDigest, changeId, reasonCode, Timestamp.from(clock.instant()));
    }

    private DocumentProviderActivationSnapshot snapshot(CapabilityOperationType type,
                                                        DocumentProviderActivationState state,
                                                        DocumentProviderBindingReference binding,
                                                        String rolloutVersion, Instant validUntil, String digest) {
        return new DocumentProviderActivationSnapshot(type, state, Optional.ofNullable(binding),
                WIRE_CONTRACT_VERSION, rolloutVersion, validUntil, digest);
    }
    private static void requireText(String value, String name) {
        if (value == null || value.isBlank()) throw new IllegalArgumentException(name + " must not be blank");
    }
    private static void requireDigest(String value, String name) {
        if (value == null || !value.matches("[0-9a-f]{64}")) {
            throw new IllegalArgumentException(name + " must be SHA-256 hex");
        }
    }
    private record Current(String state, String bindingDigest, String snapshotDigest, long rowVersion) {}
}
