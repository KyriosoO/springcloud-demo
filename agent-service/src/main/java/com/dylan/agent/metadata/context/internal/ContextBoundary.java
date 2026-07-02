package com.dylan.agent.metadata.context.internal;

import com.dylan.agent.api.context.AggregateCapabilityContextPayload;
import com.dylan.agent.api.context.CapabilityContextPayload;
import com.dylan.agent.api.context.QueryCapabilityContextPayload;
import com.dylan.agent.api.contract.runtime.common.RuntimeAggregateContextView;
import com.dylan.agent.api.contract.runtime.common.RuntimeContextView;
import com.dylan.agent.api.contract.runtime.common.RuntimeQueryContextView;
import com.dylan.agent.invocation.model.InvocationHandle;
import com.dylan.agent.invocation.model.ConversationScope;
import com.dylan.agent.invocation.model.RunScope;
import com.dylan.agent.kernel.definition.ContextReadDeclaration;
import com.dylan.agent.kernel.port.ContextApprovalPort;
import com.dylan.agent.kernel.port.ContextExecutionPort;
import com.dylan.agent.kernel.port.model.ApprovedContextWrite;
import com.dylan.agent.kernel.port.model.ContextApprovalRequest;
import com.dylan.agent.kernel.port.model.ExpectedContextVersion;
import com.dylan.agent.kernel.registration.ResolvedRegistration;
import com.dylan.agent.metadata.authorization.model.ExecutionScope;
import com.dylan.agent.metadata.authorization.model.PlanningAuthorizationEvidence;
import com.dylan.agent.metadata.context.model.ContextRecordKey;
import com.dylan.agent.metadata.context.model.ContextSnapshot;
import com.dylan.agent.metadata.context.model.ContextWriteCandidate;
import com.dylan.agent.metadata.context.port.ContextPlanningPort;
import com.dylan.agent.metadata.context.request.ContextReadRequest;
import com.dylan.agent.metadata.crypto.internal.PayloadJsonCodec;
import com.dylan.agent.metadata.crypto.model.PayloadProtectionContext;
import com.dylan.agent.metadata.crypto.model.PayloadPurpose;
import com.dylan.agent.metadata.crypto.port.ProtectedPayloadCodec;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.time.Clock;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Objects;
import java.util.Optional;
import java.util.Set;

/** D02_03 Context 边界，负责 planning load、execution currentness 和 write approval。 */
public final class ContextBoundary implements ContextPlanningPort, ContextExecutionPort, ContextApprovalPort {

    private final ContextRepository repository;
    private final PayloadJsonCodec jsonCodec;
    private final ProtectedPayloadCodec protectedPayloadCodec;
    private final Clock clock;

    public ContextBoundary(
            ContextRepository repository,
            PayloadJsonCodec jsonCodec,
            ProtectedPayloadCodec protectedPayloadCodec,
            Clock clock) {
        this.repository = Objects.requireNonNull(repository);
        this.jsonCodec = Objects.requireNonNull(jsonCodec);
        this.protectedPayloadCodec = Objects.requireNonNull(protectedPayloadCodec);
        this.clock = Objects.requireNonNull(clock);
    }

    @Override
    public Optional<ContextSnapshot> load(ContextReadRequest request) {
        Objects.requireNonNull(request, "request must not be null");
        ContextRecordKey key = new ContextRecordKey(
                request.owner(),
                request.scope(),
                request.declaration().contextType());
        return repository.findCurrent(key, clock.instant())
                .filter(entity -> entity.expiresAt().isAfter(clock.instant()))
                .map(entity -> toSnapshot(entity, request));
    }

    @Override
    public RuntimeContextView toRuntimeView(
            ContextSnapshot snapshot,
            ContextReadDeclaration declaration,
            PlanningAuthorizationEvidence evidence) {
        Objects.requireNonNull(snapshot, "snapshot must not be null");
        Objects.requireNonNull(declaration, "declaration must not be null");
        Objects.requireNonNull(evidence, "evidence must not be null");
        if (!snapshot.requestCorrelationId().equals(evidence.requestCorrelationId())
                || snapshot.contextType() != declaration.contextType()
                || !snapshot.effectiveContractRef().equals(declaration.contractRef())) {
            throw new IllegalStateException("context snapshot does not match planning evidence/declaration");
        }
        CapabilityContextPayload payload = snapshot.payload();
        if (payload instanceof QueryCapabilityContextPayload query) {
            RuntimeQueryContextView view = new RuntimeQueryContextView();
            view.setSourceInvocationId(snapshot.sourceInvocationId());
            view.setFilters(query.filters());
            view.setSelectFields(query.selectFields());
            view.setPage(query.page());
            view.setSize(query.size());
            return view;
        }
        if (payload instanceof AggregateCapabilityContextPayload aggregate) {
            RuntimeAggregateContextView view = new RuntimeAggregateContextView();
            view.setSourceInvocationId(snapshot.sourceInvocationId());
            view.setFilters(aggregate.filters());
            view.setMetrics(aggregate.metrics());
            view.setGroupByFields(aggregate.groupByFields());
            view.setMaxRows(aggregate.maxRows());
            return view;
        }
        throw new IllegalStateException("unsupported context payload type: " + payload.getClass().getName());
    }

    @Override
    public void revalidateAll(
            List<ContextSnapshot> snapshots,
            InvocationHandle handle,
            ResolvedRegistration registration,
            ExecutionScope scope) {
        Objects.requireNonNull(handle, "handle must not be null");
        Objects.requireNonNull(registration, "registration must not be null");
        Objects.requireNonNull(scope, "scope must not be null");
        Set<com.dylan.agent.api.contract.runtime.common.RuntimeContextType> seen = new LinkedHashSet<>();
        for (ContextSnapshot snapshot : List.copyOf(snapshots == null ? List.of() : snapshots)) {
            if (!seen.add(snapshot.contextType())) {
                throw new IllegalStateException("duplicate contextType: " + snapshot.contextType());
            }
            if (!snapshot.owner().equals(handle.owner())
                    || !snapshot.scope().equals(handle.scope())
                    || !snapshot.expiresAt().isAfter(clock.instant())) {
                throw new IllegalStateException("context snapshot is stale");
            }
        }
    }

    @Override
    public List<ApprovedContextWrite> approve(
            List<ContextWriteCandidate> candidates,
            ContextApprovalRequest request) {
        Objects.requireNonNull(request, "request must not be null");
        return List.copyOf(candidates == null ? List.of() : candidates).stream()
                .map(candidate -> {
                    ContextRecordKey key = new ContextRecordKey(
                            request.handle().owner(),
                            request.handle().scope(),
                            candidate.contextType());
                    Optional<ContextSnapshot> consumed = request.consumedSnapshot(candidate.contextType());
                    ExpectedContextVersion expected = consumed
                            .map(snapshot -> ExpectedContextVersion.version(snapshot.recordVersion()))
                            .orElseGet(ExpectedContextVersion::absent);
                    String contextId = consumed
                            .map(ContextSnapshot::contextId)
                            .orElse("ctx-" + request.handle().invocationId() + "-" + candidate.contextType().name());
                    return new ApprovedContextWrite(
                            contextId,
                            key,
                            candidate,
                            request.registration().capabilityId(),
                            request.handle().invocationId(),
                            null,
                            request.now().plus(request.executionScope().maxTotalDuration()),
                            expected);
                })
                .toList();
    }

    private ContextSnapshot toSnapshot(ContextRecordEntity entity, ContextReadRequest request) {
        byte[] plaintext = protectedPayloadCodec.decrypt(
                entity.protectedPayload(),
                new PayloadProtectionContext(
                        PayloadPurpose.CONTEXT_PAYLOAD,
                        entity.contextId(),
                        entity.contractRef(),
                        bindingDigest(entity)));
        CapabilityContextPayload payload = (CapabilityContextPayload) jsonCodec.deserialize(
                plaintext,
                request.declaration().payloadType());
        return new ContextSnapshot(
                entity.contextId(),
                request.requestCorrelationId(),
                entity.recordKey(),
                entity.sourceCapabilityId(),
                entity.sourceInvocationId(),
                entity.sourceDomain(),
                entity.contractRef(),
                request.declaration().contractRef(),
                entity.recordVersion(),
                entity.expiresAt(),
                request.evidence().metadataBundleVersion(),
                request.evidence().policyVersion(),
                request.evidence().permissionEvidenceId(),
                request.evidence().delegationConstraintRef().constraintId(),
                ExpectedContextVersion.version(entity.recordVersion()),
                payload);
    }

    private String bindingDigest(ContextRecordEntity entity) {
        return sha256Hex(String.join("|",
                entity.recordKey().owner().type(),
                entity.recordKey().owner().id(),
                scopeType(entity),
                entity.recordKey().scope().scopeId(),
                entity.recordKey().contextType().name(),
                entity.sourceCapabilityId(),
                entity.sourceInvocationId(),
                Objects.toString(entity.sourceDomain(), ""),
                Long.toString(entity.recordVersion())));
    }

    private String scopeType(ContextRecordEntity entity) {
        if (entity.recordKey().scope() instanceof ConversationScope) {
            return "CONVERSATION";
        }
        if (entity.recordKey().scope() instanceof RunScope) {
            return "RUN";
        }
        throw new IllegalArgumentException("unsupported context scope type: "
                + entity.recordKey().scope().getClass().getName());
    }

    private static String sha256Hex(String canonical) {
        try {
            byte[] digest = MessageDigest.getInstance("SHA-256")
                    .digest(canonical.getBytes(StandardCharsets.UTF_8));
            StringBuilder hex = new StringBuilder(digest.length * 2);
            for (byte b : digest) {
                hex.append(String.format("%02x", b));
            }
            return hex.toString();
        } catch (Exception ex) {
            throw new IllegalStateException("failed to compute context binding digest", ex);
        }
    }
}
