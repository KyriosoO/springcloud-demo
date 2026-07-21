package com.dylan.agent.kernel.validator;

import com.dylan.agent.api.contract.runtime.common.AgentPlanKind;
import com.dylan.agent.api.contract.runtime.plan.AgentPlan;

import java.util.Optional;

/**
 * Validator 输出：Handler 所需的可信、不可变执行模型。
 * 在当前 Invocation 内不可变，不跨 Invocation 复用。
 */
public interface ValidatedPlan {
    String capabilityId();
    AgentPlanKind planKind();
    Optional<String> domain();
}
