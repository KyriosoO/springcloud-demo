package com.dylan.agent.metadata.config;

import com.dylan.agent.api.capability.AgentCapabilityExecutionMode;
import com.dylan.agent.api.capability.AgentCapabilityRiskLevel;
import com.dylan.agent.api.contract.common.AgentExecutionContracts;
import com.dylan.agent.api.contract.runtime.common.AgentDomainMode;
import com.dylan.agent.api.contract.runtime.common.AgentPlanKind;
import com.dylan.agent.kernel.definition.CapabilityDefinition;
import com.dylan.agent.kernel.definition.CapabilityRoutingDescriptor;
import com.dylan.agent.kernel.definition.ContextAccessDeclaration;
import com.dylan.agent.kernel.resource.DocumentResourceLimits;
import com.dylan.agent.metadata.MetadataTestSupport;
import org.junit.jupiter.api.Test;

import java.util.List;

import static org.assertj.core.api.Assertions.assertThatThrownBy;

class AgentMetadataResourceLimitStartupGateTest {

    @Test
    void rejectsCapabilityWhoseContractHasNoProfileOrPolicyContribution() {
        CapabilityDefinition document = CapabilityDefinition.builder()
                .capabilityId("document.search")
                .planKind(AgentPlanKind.DOCUMENT)
                .routingDescriptor(new CapabilityRoutingDescriptor("document", List.of("document"), List.of()))
                .domainMode(AgentDomainMode.NONE)
                .riskLevel(AgentCapabilityRiskLevel.READ_ONLY)
                .executionMode(AgentCapabilityExecutionMode.IMMEDIATE)
                .inputContract(AgentExecutionContracts.DOCUMENT_PLAN)
                .outputContract(AgentExecutionContracts.DOCUMENT_RESULT)
                .contextAccess(new ContextAccessDeclaration(List.of(), List.of()))
                .resourceLimitDeclaration(DocumentResourceLimits.declaration(
                        DocumentResourceLimits.intrinsicFor("document.search")))
                .resourceLimitConsumers(DocumentResourceLimits.consumers("document.search"))
                .build();

        assertThatThrownBy(() -> AgentMetadataResourceLimitStartupGate.validate(
                MetadataTestSupport.bundle("bundle-v1", "digest-v1"), List.of(document)))
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("missing resource contribution");
    }
}
