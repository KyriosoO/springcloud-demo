package com.dylan.agent.capability;

import org.springframework.stereotype.Component;

import com.dylan.agent.api.enums.AgentIntent;
import com.dylan.agent.api.response.PlanGenerateResponse;
import com.dylan.agent.exception.AgentPlanValidationException;

/**
 * 从 Runtime 响应中提取原始 {@link AgentIntent}，仅做 envelope 校验：
 * response 非空、requestId 匹配、planVersion="1.0"、intent 非空。
 *
 * <p>不校验 domain、filter、query/CLARIFY shape 等能力细节，这些由 handler.validate() 负责。
 */
@Component
public class CapabilityRouteResolver {

    private static final String EXPECTED_PLAN_VERSION = "1.0";

    /** 从 Runtime 响应提取 intent，仅做 envelope 校验（response/plan 非空、requestId 匹配、planVersion=1.0、intent 非空）。 */
    public AgentIntent resolve(
            PlanGenerateResponse response,
            String expectedRequestId) {
        if (response == null || response.getPlan() == null) {
            throw new AgentPlanValidationException("Runtime 返回的 Plan 为空。");
        }
        if (!expectedRequestId.equals(response.getRequestId())) {
            throw new AgentPlanValidationException("Runtime requestId 不匹配。");
        }
        if (!EXPECTED_PLAN_VERSION.equals(response.getPlan().getPlanVersion())) {
            throw new AgentPlanValidationException(
                    "不支持的 planVersion: "
                    + response.getPlan().getPlanVersion());
        }
        AgentIntent intent = response.getPlan().getIntent();
        if (intent == null) {
            throw new AgentPlanValidationException("Plan intent 为空。");
        }
        return intent;
    }
}
