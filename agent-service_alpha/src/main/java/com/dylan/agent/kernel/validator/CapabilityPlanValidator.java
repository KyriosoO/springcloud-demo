package com.dylan.agent.kernel.validator;

import com.dylan.agent.api.contract.runtime.plan.AgentPlan;
import com.dylan.agent.kernel.core.ExecutionValidationContext;

/**
 * Raw Plan → Validated Plan 确定性可信边界。
 *
 * <p>校验 capabilityId/planKind/domain、字段/operator/function、
 * Context merge 后一致性和 canonical 值。
 * 禁止 Runtime/LLM、Handler/Adapter/数据库、Invocation/Context 写入、
 * 权限扩大、自动 fallback。
 */
public interface CapabilityPlanValidator<R extends AgentPlan, V extends ValidatedPlan> {
    V validate(R rawPlan, ExecutionValidationContext context);
}
