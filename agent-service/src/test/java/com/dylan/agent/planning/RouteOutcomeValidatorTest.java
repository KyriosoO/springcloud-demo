package com.dylan.agent.planning;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import com.dylan.agent.api.capability.AgentCapabilityExecutionMode;
import com.dylan.agent.api.capability.AgentCapabilityRiskLevel;
import com.dylan.agent.api.contract.runtime.clarification.ClarificationReasonCode;
import com.dylan.agent.api.contract.runtime.clarification.ClarificationRequired;
import com.dylan.agent.api.contract.runtime.common.AgentDomainMode;
import com.dylan.agent.api.contract.runtime.common.AgentPlanKind;
import com.dylan.agent.api.contract.runtime.common.RuntimeOperationType;
import com.dylan.agent.api.contract.runtime.route.RouteDecision;
import com.dylan.agent.invocation.model.ChatInvocationOrigin;
import com.dylan.agent.invocation.model.ContextOwnerRef;
import com.dylan.agent.invocation.model.ConversationScope;
import com.dylan.agent.invocation.model.ExecutionSubjectRef;
import com.dylan.agent.invocation.model.InvocationHandle;
import com.dylan.agent.invocation.model.InvocationType;
import com.dylan.agent.kernel.definition.CapabilityRoutingDescriptor;
import com.dylan.agent.metadata.catalog.AvailableCapability;
import com.dylan.agent.metadata.catalog.AvailableCapabilitySnapshot;
import com.dylan.agent.metadata.domain.port.DomainMetadataEvidence;
import com.dylan.agent.planning.model.PlanningCommand;
import com.dylan.agent.shared.ref.AgentProfileRef;
import com.dylan.agent.testsupport.RuntimeContractTestSupport;

import java.time.Duration;
import java.time.Instant;
import java.util.List;
import java.util.Set;

import org.junit.jupiter.api.Test;

class RouteOutcomeValidatorTest {

    private static final Instant NOW = Instant.parse("2026-07-02T10:00:00Z");

    private final RouteOutcomeValidator validator = new RouteOutcomeValidator();

    @Test
    void validatesAvailableRouteDecision() {
        RouteDecision decision = decision("query.search", "employee");

        ValidatedRouteDecision validated = validator.validate(decision, command(), snapshot(requiredCapability()));

        assertThat(validated.capability().capabilityId()).isEqualTo("query.search");
        assertThat(validated.domain()).contains("employee");
    }

    @Test
    void rejectsUnavailableCapability() {
        RouteDecision decision = decision("missing", "employee");

        assertThatThrownBy(() -> validator.validate(decision, command(), snapshot(requiredCapability())))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("capability");
    }

    @Test
    void rejectsDomainOutsideAvailableSet() {
        RouteDecision decision = decision("query.search", "transaction");

        assertThatThrownBy(() -> validator.validate(decision, command(), snapshot(requiredCapability())))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("domain");
    }

    @Test
    void throwsTypedExceptionForRouteClarification() {
        ClarificationRequired clarification = new ClarificationRequired();
        clarification.setRequestId("req-1");
        clarification.setReasonCode(ClarificationReasonCode.DOMAIN_AMBIGUOUS);
        clarification.setMetadata(RuntimeContractTestSupport.metadata(RuntimeOperationType.ROUTE));

        assertThatThrownBy(() -> validator.validate(clarification, command(), snapshot(requiredCapability())))
                .isInstanceOf(RouteOutcomeValidator.RouteClarificationException.class);
    }

    private static RouteDecision decision(String capabilityId, String domain) {
        RouteDecision decision = new RouteDecision();
        decision.setRequestId("req-1");
        decision.setCapabilityId(capabilityId);
        decision.setDomain(domain);
        decision.setMetadata(RuntimeContractTestSupport.metadata(RuntimeOperationType.ROUTE));
        return decision;
    }

    private static PlanningCommand command() {
        AgentProfileRef profile = AgentProfileRef.of("agent-default", "profile-v1");
        InvocationHandle handle = InvocationHandle.forChat(
                "inv-1",
                new ChatInvocationOrigin("conv-1", "turn-1"),
                "req-1",
                new ExecutionSubjectRef("user", "dylan"),
                new ContextOwnerRef("conversation", "conv-1"),
                new ConversationScope("conv-1"),
                profile,
                NOW.plusSeconds(30));
        return new PlanningCommand(handle, "岗位是 HRM", List.of(), profile, null);
    }

    private static AvailableCapabilitySnapshot snapshot(AvailableCapability capability) {
        return new AvailableCapabilitySnapshot(
                "req-1",
                "auth-digest",
                com.dylan.agent.testsupport.DomainMetadataTestSupport.evidence("catalog-v1", "adapter-v1", "availability-v1", NOW),
                List.of(capability),
                NOW);
    }

    private static AvailableCapability requiredCapability() {
        return new AvailableCapability(
                "query.search",
                AgentPlanKind.QUERY,
                AgentDomainMode.REQUIRED,
                new CapabilityRoutingDescriptor("query", List.of("query"), List.of()),
                Set.of("employee"),
                AgentCapabilityRiskLevel.READ_ONLY,
                AgentCapabilityExecutionMode.IMMEDIATE,
                "registration-v1");
    }
}
