package com.dylan.agent.kernel.handler;

import com.dylan.agent.kernel.validator.ValidatedPlan;
import com.dylan.agent.kernel.core.ExecutionContext;

/**
 * 只接收 Validated Plan 的单一 capability 业务编排接口。
 *
 * <p>只能编排一个 capability。不得接收 Raw Plan、修改 Invocation、持久化 Context、
 * 作授权决定、二次选择 Adapter 或返回新 capabilityId/planKind。
 */
public interface CapabilityHandler<V extends ValidatedPlan, O> {
    HandlerResult<O> execute(V plan, ExecutionContext context);
}
