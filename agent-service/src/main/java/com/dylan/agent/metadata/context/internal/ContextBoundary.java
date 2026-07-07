package com.dylan.agent.metadata.context.internal;

import com.dylan.agent.api.context.AggregateCapabilityContextPayload;
import com.dylan.agent.api.context.CapabilityContextPayload;
import com.dylan.agent.api.context.DocumentCapabilityContextPayload;
import com.dylan.agent.api.context.QueryCapabilityContextPayload;
import com.dylan.agent.api.contract.runtime.common.AgentDomainMode;
import com.dylan.agent.api.contract.runtime.common.RuntimeAggregateContextView;
import com.dylan.agent.api.contract.runtime.common.RuntimeContextView;
import com.dylan.agent.api.contract.runtime.common.RuntimeContextType;
import com.dylan.agent.api.contract.runtime.common.RuntimeDocumentContextView;
import com.dylan.agent.api.contract.runtime.common.RuntimeQueryContextView;
import com.dylan.agent.invocation.model.InvocationHandle;
import com.dylan.agent.kernel.definition.ContextReadDeclaration;
import com.dylan.agent.kernel.definition.ContextWriteDeclaration;
import com.dylan.agent.kernel.port.ContextApprovalPort;
import com.dylan.agent.kernel.port.ContextExecutionPort;
import com.dylan.agent.kernel.port.model.ApprovedContextWrite;
import com.dylan.agent.kernel.port.model.ContextApprovalRequest;
import com.dylan.agent.kernel.port.model.ExpectedContextVersion;
import com.dylan.agent.kernel.registration.ResolvedRegistration;
import com.dylan.agent.metadata.authorization.model.ExecutionScope;
import com.dylan.agent.metadata.authorization.model.PlanningAuthorizationEvidence;
import com.dylan.agent.metadata.config.AgentSecuritySettingsRegistry;
import com.dylan.agent.metadata.context.model.ContextRecordKey;
import com.dylan.agent.metadata.context.model.ContextSnapshot;
import com.dylan.agent.metadata.context.model.ContextWriteCandidate;
import com.dylan.agent.metadata.context.migration.ContextMigrationRegistry;
import com.dylan.agent.metadata.context.migration.ContextPayloadMigrator;
import com.dylan.agent.metadata.context.port.ContextPlanningPort;
import com.dylan.agent.metadata.context.request.ContextReadRequest;
import com.dylan.agent.metadata.crypto.internal.PayloadJsonCodec;
import com.dylan.agent.metadata.crypto.model.PayloadProtectionContext;
import com.dylan.agent.metadata.crypto.model.PayloadPurpose;
import com.dylan.agent.metadata.crypto.port.ProtectedPayloadCodec;

import java.time.Clock;
import java.time.Duration;
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
    private final AgentSecuritySettingsRegistry settingsRegistry;
    private final ContextMigrationRegistry migrationRegistry;
    private final Clock clock;

    public ContextBoundary(
            ContextRepository repository,
            PayloadJsonCodec jsonCodec,
            ProtectedPayloadCodec protectedPayloadCodec,
            AgentSecuritySettingsRegistry settingsRegistry,
            Clock clock) {
        this(repository, jsonCodec, protectedPayloadCodec, settingsRegistry, new ContextMigrationRegistry(List.of()), clock);
    }

    public ContextBoundary(
            ContextRepository repository,
            PayloadJsonCodec jsonCodec,
            ProtectedPayloadCodec protectedPayloadCodec,
            AgentSecuritySettingsRegistry settingsRegistry,
            ContextMigrationRegistry migrationRegistry,
            Clock clock) {
        this.repository = Objects.requireNonNull(repository);
        this.jsonCodec = Objects.requireNonNull(jsonCodec);
        this.protectedPayloadCodec = Objects.requireNonNull(protectedPayloadCodec);
        this.settingsRegistry = Objects.requireNonNull(settingsRegistry);
        this.migrationRegistry = Objects.requireNonNull(migrationRegistry);
        this.clock = Objects.requireNonNull(clock);
    }

    @Override
    public Optional<ContextSnapshot> load(ContextReadRequest request) {
        Objects.requireNonNull(request, "request must not be null");
        if (!request.evidence().planningScope().readableContextTypes()
                .contains(request.declaration().contextType())) {
            throw new IllegalStateException("context type is not readable by planning scope");
        }
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
        if (!evidence.planningScope().readableContextTypes().contains(declaration.contextType())
                || !snapshot.requestCorrelationId().equals(evidence.requestCorrelationId())
                || snapshot.contextType() != declaration.contextType()
                || !snapshot.effectiveContractRef().equals(declaration.contractRef())
                || !declaration.payloadType().isInstance(snapshot.payload())) {
            throw new IllegalStateException("context snapshot does not match planning evidence/declaration");
        }
        Set<String> readableFields = declaration.readableFields();
        CapabilityContextPayload payload = snapshot.payload();
        if (payload instanceof QueryCapabilityContextPayload query) {
            RuntimeQueryContextView view = new RuntimeQueryContextView();
            view.setSourceInvocationId(snapshot.sourceInvocationId());
            if (readableFields.contains("filters")) {
                view.setFilters(query.filters());
            }
            if (readableFields.contains("selectFields")) {
                view.setSelectFields(query.selectFields());
            }
            if (readableFields.contains("sorts")) {
                view.setSorts(query.sorts());
            }
            if (readableFields.contains("page")) {
                view.setPage(query.page());
            }
            if (readableFields.contains("size")) {
                view.setSize(query.size());
            }
            if (readableFields.contains("total")) {
                view.setTotal(query.total());
            }
            if (readableFields.contains("totalExact")) {
                view.setTotalExact(query.totalExact());
            }
            if (readableFields.contains("totalPages")) {
                view.setTotalPages(query.totalPages());
            }
            return view;
        }
        if (payload instanceof AggregateCapabilityContextPayload aggregate) {
            RuntimeAggregateContextView view = new RuntimeAggregateContextView();
            view.setSourceInvocationId(snapshot.sourceInvocationId());
            if (readableFields.contains("filters")) {
                view.setFilters(aggregate.filters());
            }
            if (readableFields.contains("metrics")) {
                view.setMetrics(aggregate.metrics());
            }
            if (readableFields.contains("groupByFields")) {
                view.setGroupByFields(aggregate.groupByFields());
            }
            if (readableFields.contains("orderBy")) {
                view.setOrderBy(aggregate.orderBy());
            }
            if (readableFields.contains("maxRows")) {
                view.setMaxRows(aggregate.maxRows());
            }
            return view;
        }
        if (payload instanceof DocumentCapabilityContextPayload document) {
            RuntimeDocumentContextView view = new RuntimeDocumentContextView();
            view.setSourceInvocationId(snapshot.sourceInvocationId());
            if (readableFields.contains("operation")) {
                view.setOperation(document.operation());
            }
            if (readableFields.contains("domain")) {
                view.setDomain(document.domain());
            }
            if (readableFields.contains("queryText")) {
                view.setQueryText(document.queryText());
            }
            if (readableFields.contains("filters")) {
                view.setFilters(document.filters());
            }
            if (readableFields.contains("citationIds")) {
                view.setCitationIds(document.citationIds());
            }
            if (readableFields.contains("topK")) {
                view.setTopK(document.topK());
            }
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
        Set<RuntimeContextType> seen = new LinkedHashSet<>();
        for (ContextSnapshot snapshot : List.copyOf(snapshots == null ? List.of() : snapshots)) {
            if (!seen.add(snapshot.contextType())) {
                throw new IllegalStateException("duplicate contextType: " + snapshot.contextType());
            }
            ContextReadDeclaration declaration = registration.registration()
                    .definition()
                    .contextAccess()
                    .read(snapshot.contextType());
            if (declaration == null || !scope.readableContextTypes().contains(snapshot.contextType())) {
                throw new IllegalStateException("context snapshot is stale");
            }
            validateSnapshotBinding(snapshot, handle, declaration, scope);
            ContextRecordEntity current = repository.findByKey(snapshot.recordKey())
                    .orElseThrow(() -> new IllegalStateException("context snapshot is stale"));
            validateCurrentRecord(snapshot, current);
        }
    }

    @Override
    public List<ApprovedContextWrite> approve(
            List<ContextWriteCandidate> candidates,
            ContextApprovalRequest request) {
        Objects.requireNonNull(request, "request must not be null");
        Set<RuntimeContextType> seen = new LinkedHashSet<>();
        return List.copyOf(candidates == null ? List.of() : candidates).stream()
                .map(candidate -> approveCandidate(candidate, request, seen))
                .toList();
    }

    private ApprovedContextWrite approveCandidate(
            ContextWriteCandidate candidate,
            ContextApprovalRequest request,
            Set<RuntimeContextType> seen) {
        Objects.requireNonNull(candidate, "context write candidate must not be null");
        if (!seen.add(candidate.contextType())) {
            throw new IllegalStateException("duplicate context write candidate: " + candidate.contextType());
        }
        ContextWriteDeclaration declaration = request.registration().registration()
                .definition()
                .contextAccess()
                .write(candidate.contextType());
        if (declaration == null
                || !request.executionScope().writableContextTypes().contains(candidate.contextType())
                || !candidate.contractRef().equals(declaration.contractRef())
                || !declaration.payloadType().isInstance(candidate.payload())) {
            throw new IllegalStateException("context write is not declared or authorized");
        }
        validateWritableFields(candidate.payload(), declaration.writableFields());

        ContextRecordKey key = new ContextRecordKey(
                request.handle().owner(),
                request.handle().scope(),
                candidate.contextType());
        Optional<ContextSnapshot> consumed = request.consumedSnapshot(candidate.contextType());
        Optional<ContextRecordEntity> current = consumed.isPresent() ? Optional.empty() : repository.findByKey(key);
        ExpectedContextVersion expected = consumed
                .map(snapshot -> ExpectedContextVersion.version(snapshot.recordVersion()))
                .or(() -> current.map(entity -> ExpectedContextVersion.version(entity.recordVersion())))
                .orElseGet(ExpectedContextVersion::absent);
        String contextId = consumed
                .map(ContextSnapshot::contextId)
                .or(() -> current.map(ContextRecordEntity::contextId))
                .orElse("ctx-" + request.handle().invocationId() + "-" + candidate.contextType().name());
        return new ApprovedContextWrite(
                contextId,
                key,
                candidate,
                request.registration().capabilityId(),
                request.handle().invocationId(),
                sourceDomain(request),
                request.now().plus(strictestTtl(declaration, request)),
                expected);
    }

    private void validateSnapshotBinding(
            ContextSnapshot snapshot,
            InvocationHandle handle,
            ContextReadDeclaration declaration,
            ExecutionScope scope) {
        if (!snapshot.requestCorrelationId().equals(handle.requestCorrelationId())
                || !snapshot.owner().equals(handle.owner())
                || !ContextBindingSupport.sameScope(snapshot.scope(), handle.scope())
                || !snapshot.effectiveContractRef().equals(declaration.contractRef())
                || !declaration.payloadType().isInstance(snapshot.payload())
                || !snapshot.policyEvidenceRef().equals(scope.currentPolicyVersion())
                || !snapshot.permissionEvidenceRef().equals(scope.currentPermissionEvidenceId())) {
            throw new IllegalStateException("context snapshot is stale");
        }
    }

    private void validateCurrentRecord(ContextSnapshot snapshot, ContextRecordEntity current) {
        if (!current.readable()
                || !current.expiresAt().isAfter(clock.instant())
                || !current.contextId().equals(snapshot.contextId())
                || !current.contractRef().equals(snapshot.storedContractRef())
                || current.recordVersion() != snapshot.recordVersion()
                || !current.sourceCapabilityId().equals(snapshot.sourceCapabilityId())
                || !current.sourceInvocationId().equals(snapshot.sourceInvocationId())
                || !Objects.equals(current.sourceDomain(), snapshot.sourceDomain().orElse(null))) {
            throw new IllegalStateException("context snapshot is stale");
        }
    }

    private String sourceDomain(ContextApprovalRequest request) {
        if (request.selectedDomain().isPresent()) {
            return request.selectedDomain().orElseThrow();
        }
        if (request.registration().registration().definition().domainMode() == AgentDomainMode.REQUIRED) {
            throw new IllegalStateException("context write requires selected domain");
        }
        return null;
    }

    private Duration strictestTtl(ContextWriteDeclaration declaration, ContextApprovalRequest request) {
        Duration ttl = min(declaration.maxTtl(), request.executionScope().maxTotalDuration());
        return min(ttl, settingsRegistry.current().globalMaxContextTtl());
    }

    private static Duration min(Duration left, Duration right) {
        return left.compareTo(right) <= 0 ? left : right;
    }

    private static void validateWritableFields(CapabilityContextPayload payload, Set<String> writableFields) {
        Set<String> fields = payloadFields(payload);
        if (!writableFields.containsAll(fields)) {
            throw new IllegalStateException("context write contains undeclared payload fields");
        }
    }

    private static Set<String> payloadFields(CapabilityContextPayload payload) {
        Set<String> fields = new LinkedHashSet<>();
        if (payload instanceof QueryCapabilityContextPayload query) {
            if (!query.filters().isEmpty()) {
                fields.add("filters");
            }
            if (!query.selectFields().isEmpty()) {
                fields.add("selectFields");
            }
            if (!query.sorts().isEmpty()) {
                fields.add("sorts");
            }
            fields.add("page");
            fields.add("size");
            if (query.total() != null) {
                fields.add("total");
            }
            if (query.totalExact() != null) {
                fields.add("totalExact");
            }
            if (query.totalPages() != null) {
                fields.add("totalPages");
            }
            return fields;
        }
        if (payload instanceof AggregateCapabilityContextPayload aggregate) {
            if (!aggregate.filters().isEmpty()) {
                fields.add("filters");
            }
            fields.add("metrics");
            if (!aggregate.groupByFields().isEmpty()) {
                fields.add("groupByFields");
            }
            if (!aggregate.orderBy().isEmpty()) {
                fields.add("orderBy");
            }
            fields.add("maxRows");
            return fields;
        }
        if (payload instanceof DocumentCapabilityContextPayload document) {
            fields.add("operation");
            fields.add("domain");
            fields.add("queryText");
            if (!document.filters().isEmpty()) {
                fields.add("filters");
            }
            if (!document.citationIds().isEmpty()) {
                fields.add("citationIds");
            }
            fields.add("topK");
            return fields;
        }
        throw new IllegalStateException("unsupported context payload type: " + payload.getClass().getName());
    }

    private ContextSnapshot toSnapshot(ContextRecordEntity entity, ContextReadRequest request) {
        byte[] plaintext = protectedPayloadCodec.decrypt(
                entity.protectedPayload(),
                new PayloadProtectionContext(
                        PayloadPurpose.CONTEXT_PAYLOAD,
                        entity.contextId(),
                        entity.contractRef(),
                        ContextBindingSupport.bindingDigest(entity)));
        CapabilityContextPayload payload = deserializeAndMigrate(
                plaintext,
                entity,
                request);
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

    private CapabilityContextPayload deserializeAndMigrate(
            byte[] plaintext,
            ContextRecordEntity entity,
            ContextReadRequest request) {
        if (entity.contractRef().equals(request.declaration().contractRef())) {
            return (CapabilityContextPayload) jsonCodec.deserialize(
                    plaintext,
                    request.declaration().payloadType());
        }
        ContextPayloadMigrator<?, ?> migrator = migrationRegistry.resolve(
                        entity.contractRef(),
                        request.declaration().contractRef())
                .orElseThrow(() -> new IllegalStateException("context contract is incompatible"));
        CapabilityContextPayload source = (CapabilityContextPayload) jsonCodec.deserialize(
                plaintext,
                migrator.sourceType());
        return migrate(migrator, source);
    }

    @SuppressWarnings({"unchecked", "rawtypes"})
    private static CapabilityContextPayload migrate(
            ContextPayloadMigrator migrator,
            CapabilityContextPayload source) {
        return (CapabilityContextPayload) migrator.migrate(source);
    }
}
