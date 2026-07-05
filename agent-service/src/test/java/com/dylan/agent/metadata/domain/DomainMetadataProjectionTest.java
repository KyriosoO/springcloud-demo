package com.dylan.agent.metadata.domain;

import static org.assertj.core.api.Assertions.assertThat;

import java.time.Duration;
import java.time.Instant;
import java.util.Map;
import java.util.Optional;
import java.util.Set;

import org.junit.jupiter.api.Test;

import com.dylan.agent.adapter.api.AdapterRole;
import com.dylan.agent.api.capability.AgentCapabilityExecutionMode;
import com.dylan.agent.api.capability.AgentCapabilityRiskLevel;
import com.dylan.agent.api.enums.AgentOperator;
import com.dylan.agent.metadata.authorization.model.PlanningEffectiveScope;
import com.dylan.agent.metadata.domain.port.CanonicalFieldRef;
import com.dylan.agent.model.MaskType;
import com.dylan.agent.testsupport.DomainMetadataTestSupport;

class DomainMetadataProjectionTest {

    private static final Instant DEADLINE = Instant.parse("2026-07-02T00:01:00Z");

    @Test
    void routeAndPlanProjectionsComeFromSameExpectedEvidenceAndEffectiveScope() {
        var port = DomainMetadataTestSupport.domainMetadataPort();
        var evidence = DomainMetadataTestSupport.store().current().evidence();
        PlanningEffectiveScope scope = scope();

        var routes = port.routeProjection(
                Set.of("employee", "transaction"),
                scope,
                evidence,
                "auth-evidence",
                DEADLINE);
        var schema = port.planSchema(AdapterRole.QUERYABLE, "employee", scope, evidence, DEADLINE);

        assertThat(routes).extracting("domain").containsExactly("employee");
        assertThat(schema.getDomain()).isEqualTo("employee");
        assertThat(schema.getFields()).extracting("field").containsExactly("chineseName");
        assertThat(schema.getDefaultSelectFields()).containsExactly("chineseName");
        assertThat(schema.getSortFields()).containsExactly("chineseName");
    }

    private PlanningEffectiveScope scope() {
        CanonicalFieldRef field = new CanonicalFieldRef("employee", "chineseName");
        return new PlanningEffectiveScope(
                Set.of("query.search"),
                Set.of("employee"),
                Map.of(field, new PlanningEffectiveScope.FieldAccess(
                        true,
                        true,
                        Set.of(AgentOperator.EQ, AgentOperator.CONTAINS),
                        Set.of(),
                        Optional.of(MaskType.NONE))),
                Set.of(),
                Set.of(),
                AgentCapabilityRiskLevel.READ_ONLY,
                AgentCapabilityExecutionMode.IMMEDIATE,
                Duration.ofSeconds(30),
                1,
                100,
                100,
                10_000);
    }
}
