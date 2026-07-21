package com.dylan.agent.planning.model;

import com.dylan.agent.api.contract.common.ContractRef;
import com.dylan.agent.api.contract.runtime.common.RuntimeOperationMetadata;
import com.dylan.agent.metadata.context.model.ContextSnapshot;
import com.fasterxml.jackson.databind.MapperFeature;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.SerializationFeature;
import com.fasterxml.jackson.datatype.jsr310.JavaTimeModule;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.Comparator;
import java.util.List;

/** PAI-1 唯一 canonical form 与 SHA-256 生成器。 */
public final class PlanningArtifactCanonicalizer {

    private static final ObjectMapper MAPPER = new ObjectMapper()
            .registerModule(new JavaTimeModule())
            .enable(MapperFeature.SORT_PROPERTIES_ALPHABETICALLY)
            .enable(SerializationFeature.ORDER_MAP_ENTRIES_BY_KEYS)
            .disable(SerializationFeature.WRITE_DATES_AS_TIMESTAMPS);

    private PlanningArtifactCanonicalizer() {
    }

    public static PlanningArtifactIdentity create(ExecutablePlanningResult result) {
        List<ContextSnapshotForm> contexts = result.contextSnapshots().stream()
                .map(PlanningArtifactCanonicalizer::contextForm)
                .sorted(Comparator.comparing(ContextSnapshotForm::businessKey))
                .toList();
        String contextDigest = digestJson(contexts);
        PlanningArtifactCanonicalForm form = new PlanningArtifactCanonicalForm(
                "PAI-1",
                result.invocationId(),
                result.requestCorrelationId(),
                result.capabilityId(),
                result.domain().orElse(null),
                result.planKind().name(),
                result.resolvedRegistration().registrationIdentity(),
                digestJson(result.rawPlan()),
                result.authorizationSnapshot().safeReference(),
                contexts,
                auditForm(result.routeAudit()),
                auditForm(result.planAudit()),
                result.absoluteDeadline().toString());
        return new PlanningArtifactIdentity(
                result.invocationId(),
                result.requestCorrelationId(),
                result.resolvedRegistration().registrationIdentity(),
                result.authorizationSnapshot().safeReference(),
                contextDigest,
                result.absoluteDeadline(),
                digestJson(form));
    }

    public static boolean matches(ExecutablePlanningResult result) {
        return create(result).equals(result.artifactIdentity());
    }

    private static ContextSnapshotForm contextForm(ContextSnapshot snapshot) {
        return new ContextSnapshotForm(
                snapshot.contextId(),
                snapshot.contextType().name(),
                snapshot.owner().type(),
                snapshot.owner().id(),
                snapshot.scope().scopeId(),
                contract(snapshot.storedContractRef()),
                contract(snapshot.effectiveContractRef()),
                snapshot.recordVersion(),
                snapshot.sourceCapabilityId(),
                snapshot.sourceInvocationId(),
                snapshot.sourceDomain().orElse(null));
    }

    private static String contract(ContractRef ref) {
        return ref.namespace() + ":" + ref.name() + ":" + ref.version();
    }

    private static PlanningOperationAuditForm auditForm(PlanningOperationAudit audit) {
        RuntimeOperationMetadata metadata = audit.runtimeMetadata().orElse(null);
        return new PlanningOperationAuditForm(
                audit.operation().name(),
                audit.metadataStatus().name(),
                audit.localDurationMs(),
                audit.termination().name(),
                metadata == null ? null : metadata.getProviderAttempts(),
                metadata == null ? null : metadata.getRepairAttempts(),
                metadata == null ? null : metadata.getRepairDurationMs(),
                metadata == null ? null : metadata.getTotalDurationMs(),
                metadata == null || metadata.getTerminationReason() == null
                        ? null : metadata.getTerminationReason().name(),
                metadata == null ? null : metadata.getDeadlineReached(),
                metadata == null ? null : metadata.getRepairLimitReached());
    }

    private static String digestJson(Object value) {
        try {
            byte[] canonical = MAPPER.writeValueAsBytes(value);
            byte[] digest = MessageDigest.getInstance("SHA-256").digest(canonical);
            return java.util.HexFormat.of().formatHex(digest);
        } catch (Exception ex) {
            throw new IllegalStateException("canonicalize planning artifact failed", ex);
        }
    }

    private record PlanningArtifactCanonicalForm(
            String generation,
            String invocationId,
            String requestCorrelationId,
            String capabilityId,
            String domain,
            String planKind,
            String registrationIdentity,
            String rawPlanContractDigest,
            String authorizationSnapshotRef,
            List<ContextSnapshotForm> contextSnapshots,
            PlanningOperationAuditForm routeAudit,
            PlanningOperationAuditForm planAudit,
            String absoluteDeadline) {
    }

    private record ContextSnapshotForm(
            String contextId,
            String contextType,
            String ownerType,
            String ownerId,
            String scopeId,
            String storedContractRef,
            String effectiveContractRef,
            long recordVersion,
            String sourceCapabilityId,
            String sourceInvocationId,
            String sourceDomain) {

        private String businessKey() {
            return contextType + "|" + contextId;
        }
    }

    private record PlanningOperationAuditForm(
            String operation,
            String metadataStatus,
            long localDurationMs,
            String termination,
            Integer providerAttempts,
            Integer repairAttempts,
            Long repairDurationMs,
            Long totalDurationMs,
            String terminationReason,
            Boolean deadlineReached,
            Boolean repairLimitReached) {
    }
}
