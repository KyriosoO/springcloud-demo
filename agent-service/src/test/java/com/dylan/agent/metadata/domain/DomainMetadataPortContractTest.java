package com.dylan.agent.metadata.domain;

import com.dylan.agent.adapter.api.AdapterRole;
import com.dylan.agent.adapter.api.AgentAdapterPort;
import com.dylan.agent.api.capability.AgentCapabilityExecutionMode;
import com.dylan.agent.api.capability.AgentCapabilityRiskLevel;
import com.dylan.agent.api.contract.runtime.common.RuntimeContextType;
import com.dylan.agent.api.enums.AgentFieldType;
import com.dylan.agent.api.enums.AgentOperator;
import com.dylan.agent.kernel.port.model.AdapterExecutionBinding;
import com.dylan.agent.kernel.port.model.DomainBindingRequest;
import com.dylan.agent.kernel.port.model.DomainExecutionResolution;
import com.dylan.agent.kernel.port.model.ExecutionFieldRule;
import com.dylan.agent.kernel.port.model.ExecutionValidationProjection;
import com.dylan.agent.kernel.registration.ResolvedRegistration;
import com.dylan.agent.model.MaskType;
import com.dylan.agent.metadata.authorization.model.ExecutionScope;
import com.dylan.agent.metadata.authorization.model.PlanningEffectiveScope;
import com.dylan.agent.metadata.domain.port.CanonicalFieldRef;
import com.dylan.agent.metadata.domain.port.CanonicalFunctionRef;
import com.dylan.agent.metadata.domain.port.CanonicalOperatorRef;
import com.dylan.agent.metadata.domain.port.DomainAvailabilitySnapshot;
import com.dylan.agent.metadata.domain.port.DomainMetadataEvidence;
import com.dylan.agent.metadata.domain.port.DomainMetadataReferenceSet;
import org.junit.jupiter.api.Test;

import java.time.Duration;
import java.time.Instant;
import java.util.Map;
import java.util.Optional;
import java.util.Set;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.Mockito.mock;

class DomainMetadataPortContractTest {

    @Test
    void referenceSetRequiresOperatorAndFunctionFieldsToBeDeclared() {
        CanonicalFieldRef field = new CanonicalFieldRef("employee", "name");

        DomainMetadataReferenceSet refs = new DomainMetadataReferenceSet(
                Set.of("employee"),
                Set.of(field),
                Set.of(new CanonicalOperatorRef(field, AgentOperator.EQ)),
                Set.of(new CanonicalFunctionRef(field, "COUNT")));

        assertThat(refs.isEmpty()).isFalse();

        CanonicalFieldRef undeclared = new CanonicalFieldRef("employee", "salary");
        assertThatThrownBy(() -> new DomainMetadataReferenceSet(
                Set.of("employee"),
                Set.of(field),
                Set.of(new CanonicalOperatorRef(undeclared, AgentOperator.GT)),
                Set.of()))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("operator field");
    }

    @Test
    void evidenceSafeRefIsStableAndDoesNotExposeCatalogBody() {
        DomainMetadataEvidence left = com.dylan.agent.testsupport.DomainMetadataTestSupport.evidence(
                "catalog-v1", "adapter-v1", "availability-digest", Instant.parse("2026-07-01T00:00:00Z"));
        DomainMetadataEvidence same = com.dylan.agent.testsupport.DomainMetadataTestSupport.evidence(
                "catalog-v1", "adapter-v1", "availability-digest", Instant.parse("2026-07-01T00:00:00Z"));
        DomainMetadataEvidence different = com.dylan.agent.testsupport.DomainMetadataTestSupport.evidence(
                "catalog-v2", "adapter-v1", "availability-digest", Instant.parse("2026-07-01T00:00:00Z"));

        assertThat(left.safeRef()).isEqualTo(same.safeRef());
        assertThat(left.safeRef()).isNotEqualTo(different.safeRef());
        assertThat(left.safeRef()).doesNotContain("catalog-v1");
    }

    @Test
    void availabilitySnapshotIsIndexedByRequestedRole() {
        DomainMetadataEvidence evidence = com.dylan.agent.testsupport.DomainMetadataTestSupport.evidence(
                "catalog-v1", "adapter-v1", "availability-digest", Instant.parse("2026-07-01T00:00:00Z"));

        DomainAvailabilitySnapshot snapshot = new DomainAvailabilitySnapshot(
                evidence,
                java.util.Map.of(AdapterRole.QUERYABLE, Set.of("employee")));

        assertThat(snapshot.availableDomains()).containsOnlyKeys(AdapterRole.QUERYABLE);
        assertThatThrownBy(() -> snapshot.availableDomains().put(AdapterRole.AGGREGATABLE, Set.of("employee")))
                .isInstanceOf(UnsupportedOperationException.class);
        assertThatThrownBy(() -> snapshot.availableDomains().get(AdapterRole.QUERYABLE).add("finance"))
                .isInstanceOf(UnsupportedOperationException.class);
    }

    @Test
    void planningEffectiveScopeIsImmutableRequestLevelProjection() {
        CanonicalFieldRef field = new CanonicalFieldRef("employee", "name");
        PlanningEffectiveScope scope = com.dylan.agent.testsupport.PlanningEffectiveScopeTestFactory.create(
                Set.of("query.search"),
                Set.of("employee"),
                Map.of(field, new PlanningEffectiveScope.FieldAccess(
                        true,
                        true,
                        Set.of(AgentOperator.EQ),
                        Set.of("COUNT"),
                        Optional.of(MaskType.EMAIL))),
                Set.of(RuntimeContextType.QUERY),
                Set.of(RuntimeContextType.QUERY),
                AgentCapabilityRiskLevel.READ_ONLY,
                AgentCapabilityExecutionMode.IMMEDIATE,
                Duration.ofSeconds(30),
                1,
                20,
                100,
                10_000);

        assertThat(scope.allowedCapabilityIds()).containsExactly("query.search");
        assertThat(scope.planningBudgetLimits().maxTotalDuration()).isEqualTo(Duration.ofSeconds(30));
        assertThat(scope.fieldAccess().get(field).allowedOperators()).containsExactly(AgentOperator.EQ);
        assertThatThrownBy(() -> scope.allowedDomains().add("finance"))
                .isInstanceOf(UnsupportedOperationException.class);
        assertThatThrownBy(() -> scope.fieldAccess().clear())
                .isInstanceOf(UnsupportedOperationException.class);
        assertThatThrownBy(() -> scope.fieldAccess().get(field).allowedFunctions().add("SUM"))
                .isInstanceOf(UnsupportedOperationException.class);
    }

    @Test
    void domainBindingRequestRequiresEvidenceFromExecutionScope() {
        DomainMetadataEvidence expected = evidence("catalog-v1", "adapter-v1");
        DomainMetadataEvidence other = evidence("catalog-v2", "adapter-v1");
        ExecutionScope scope = executionScope(expected);

        assertThat(new DomainBindingRequest(
                mock(ResolvedRegistration.class),
                "employee",
                scope,
                expected,
                Instant.parse("2026-07-01T00:01:00Z")).expectedEvidence())
                .isEqualTo(expected);

        assertThatThrownBy(() -> new DomainBindingRequest(
                mock(ResolvedRegistration.class),
                "employee",
                scope,
                other,
                Instant.parse("2026-07-01T00:01:00Z")))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("execution scope");
    }

    @Test
    void domainExecutionResolutionRequiresEvidenceClosedVersions() {
        DomainMetadataEvidence expected = evidence("catalog-v1", "adapter-v1");
        AdapterExecutionBinding binding = com.dylan.agent.testsupport.DomainMetadataTestSupport.binding(
                AdapterRole.QUERYABLE,
                "employee",
                AgentAdapterPort.class,
                new TestAdapterPort(),
                "adapter-v1",
                expected,
                Instant.parse("2026-07-01T00:00:00Z"));
        ExecutionValidationProjection projection = new ExecutionValidationProjection(
                AdapterRole.QUERYABLE,
                "employee",
                Map.of(),
                java.util.List.of(),
                expected.staticEvidence().safeRef());

        assertThat(new DomainExecutionResolution(binding, projection, expected).expectedEvidence())
                .isEqualTo(expected);

        assertThatThrownBy(() -> new DomainExecutionResolution(
                binding,
                projection,
                evidence("catalog-v2", "adapter-v1")))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("metadata evidence");
    }

    @Test
    void executionValidationProjectionRejectsUnsafeOrInconsistentProjection() {
        ExecutionFieldRule fieldRule = new ExecutionFieldRule(
                "name",
                AgentFieldType.STRING,
                Set.of(AgentOperator.EQ),
                Set.of(),
                100,
                null,
                null,
                null);

        assertThatThrownBy(() -> new ExecutionValidationProjection(
                AdapterRole.QUERYABLE,
                "employee",
                Map.of("other", fieldRule),
                java.util.List.of("name"),
                "catalog-v1"))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("rule.field");

        assertThatThrownBy(() -> new ExecutionValidationProjection(
                AdapterRole.QUERYABLE,
                "employee",
                Map.of("name", fieldRule),
                java.util.List.of(" "),
                "catalog-v1"))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("defaultSelectFields");

        assertThatThrownBy(() -> new ExecutionValidationProjection(
                AdapterRole.QUERYABLE,
                "employee",
                Map.of("name", fieldRule),
                java.util.List.of("name"),
                Set.of("missing"),
                "catalog-v1"))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("sortFields");

        assertThatThrownBy(() -> new ExecutionValidationProjection(
                AdapterRole.QUERYABLE,
                "employee",
                Map.of("name", fieldRule),
                java.util.List.of("name"),
                " "))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("projectionVersion");
    }

    private ExecutionScope executionScope(DomainMetadataEvidence evidence) {
        return com.dylan.agent.testsupport.ExecutionScopeTestFactory.create(
                "user:u-1",
                evidence,
                Instant.parse("2026-07-01T00:00:30Z"),
                "perm-evidence-1",
                "perm-v1",
                "policy-v1",
                Set.of("query.search"),
                Set.of("employee"),
                Map.of(),
                Map.of(),
                com.dylan.agent.kernel.resource.StandardResourceLimits
                        .testEffective(100, 100, 10_000));
    }

    private DomainMetadataEvidence evidence(String catalogVersion, String adapterVersion) {
        return com.dylan.agent.testsupport.DomainMetadataTestSupport.evidence(
                catalogVersion,
                adapterVersion,
                "availability-digest",
                Instant.parse("2026-07-01T00:00:00Z"));
    }

    private static final class TestAdapterPort implements AgentAdapterPort {
    }
}
