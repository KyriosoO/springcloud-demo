package com.dylan.agent.capability.clarify;

import org.springframework.stereotype.Component;

import com.dylan.agent.api.enums.AgentIntent;
import com.dylan.agent.capability.AgentCapabilityHandler;
import com.dylan.agent.capability.CapabilityExecutionContext;
import com.dylan.agent.capability.CapabilityExecutionResult;
import com.dylan.agent.api.capability.AgentCapabilityRiskLevel;
import com.dylan.agent.capability.CapabilityValidationContext;
import com.dylan.agent.capability.model.ValidatedClarifyPlan;

/** CLARIFY 意图的能力处理器。validate() 委托 ClarifyPlanValidator，execute() 直接返回反问结果。CLARIFY 不写 query_context_json。 */
@Component
public class ClarifyCapabilityHandler
        implements AgentCapabilityHandler<ValidatedClarifyPlan> {

    private final ClarifyPlanValidator clarifyPlanValidator;

    public ClarifyCapabilityHandler(ClarifyPlanValidator clarifyPlanValidator) {
        this.clarifyPlanValidator = clarifyPlanValidator;
    }

    @Override
    public AgentIntent intent() {
        return AgentIntent.CLARIFY;
    }

    @Override
    public AgentCapabilityRiskLevel riskLevel() {
        return AgentCapabilityRiskLevel.READ_ONLY;
    }

    @Override
    public ValidatedClarifyPlan validate(CapabilityValidationContext context) {
        return clarifyPlanValidator.validate(context);
    }

    @Override
    public CapabilityExecutionResult execute(
            CapabilityExecutionContext context,
            ValidatedClarifyPlan plan) {
        return CapabilityExecutionResult.clarify(plan.question());
    }
}
