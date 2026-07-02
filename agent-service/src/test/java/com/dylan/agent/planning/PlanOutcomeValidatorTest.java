package com.dylan.agent.planning;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import com.dylan.agent.api.contract.runtime.clarification.ClarificationReasonCode;
import com.dylan.agent.api.contract.runtime.clarification.ClarificationRequired;
import com.dylan.agent.api.contract.runtime.common.RuntimeOperationType;
import com.dylan.agent.api.contract.runtime.plan.ExecutablePlan;
import com.dylan.agent.api.contract.runtime.plan.QueryAgentPlan;
import com.dylan.agent.api.plan.AgentQuerySpec;
import com.dylan.agent.invocation.model.ChatInvocationOrigin;
import com.dylan.agent.invocation.model.ContextOwnerRef;
import com.dylan.agent.invocation.model.ConversationScope;
import com.dylan.agent.invocation.model.ExecutionSubjectRef;
import com.dylan.agent.invocation.model.InvocationHandle;
import com.dylan.agent.invocation.model.InvocationType;
import com.dylan.agent.planning.model.PlanningCommand;
import com.dylan.agent.shared.ref.AgentProfileRef;
import com.dylan.agent.testsupport.KernelTestSupport;
import com.dylan.agent.testsupport.RuntimeContractTestSupport;

import java.time.Instant;
import java.util.List;

import org.junit.jupiter.api.Test;

class PlanOutcomeValidatorTest {

    private static final Instant NOW = Instant.parse("2026-07-02T10:00:00Z");

    private final PlanOutcomeValidator validator = new PlanOutcomeValidator();

    @Test
    void validatesExecutablePlanBoundToRegistration() {
        ExecutablePlan executable = executable("req-1");

        ExecutablePlan validated = validator.validate(
                executable,
                command(),
                KernelTestSupport.resolvedQueryRegistration());

        assertThat(validated.getPlan()).isInstanceOf(QueryAgentPlan.class);
    }

    @Test
    void rejectsMismatchedRequestId() {
        assertThatThrownBy(() -> validator.validate(
                executable("other"),
                command(),
                KernelTestSupport.resolvedQueryRegistration()))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("requestId");
    }

    @Test
    void throwsTypedExceptionForPlanClarification() {
        ClarificationRequired clarification = new ClarificationRequired();
        clarification.setRequestId("req-1");
        clarification.setReasonCode(ClarificationReasonCode.VALUE_REQUIRED);
        clarification.setMetadata(RuntimeContractTestSupport.metadata(RuntimeOperationType.PLAN));

        assertThatThrownBy(() -> validator.validate(
                clarification,
                command(),
                KernelTestSupport.resolvedQueryRegistration()))
                .isInstanceOf(PlanOutcomeValidator.PlanClarificationException.class);
    }

    private static ExecutablePlan executable(String requestId) {
        QueryAgentPlan plan = new QueryAgentPlan();
        AgentQuerySpec query = new AgentQuerySpec();
        query.setSelectFields(List.of("chineseName"));
        plan.setQuery(query);

        ExecutablePlan executable = new ExecutablePlan();
        executable.setRequestId(requestId);
        executable.setPlan(plan);
        executable.setMetadata(RuntimeContractTestSupport.metadata(RuntimeOperationType.PLAN));
        return executable;
    }

    private static PlanningCommand command() {
        AgentProfileRef profile = AgentProfileRef.of("agent-default", "profile-v1");
        InvocationHandle handle = InvocationHandle.create(
                "inv-1",
                InvocationType.CHAT,
                new ChatInvocationOrigin("conv-1", "turn-1"),
                "req-1",
                new ExecutionSubjectRef("user", "dylan"),
                new ContextOwnerRef("conversation", "conv-1"),
                new ConversationScope("conv-1"),
                profile,
                NOW.plusSeconds(30));
        return new PlanningCommand(handle, "岗位是 HRM", List.of(), profile, null);
    }
}
