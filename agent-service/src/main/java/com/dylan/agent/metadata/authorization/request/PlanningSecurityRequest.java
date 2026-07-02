package com.dylan.agent.metadata.authorization.request;

import com.dylan.agent.invocation.model.InvocationHandle;
import com.dylan.agent.metadata.authorization.model.DelegationConstraintRef;
import com.dylan.agent.shared.ref.AgentProfileRef;

import java.util.Objects;

/** 绑定 InvocationHandle 的 Planning 安全捕获请求。 */
public record PlanningSecurityRequest(
        InvocationHandle handle,
        AgentProfileRef agentProfileRef,
        DelegationConstraintRef delegationConstraintRef) {
    public PlanningSecurityRequest {
        Objects.requireNonNull(handle, "handle must not be null");
        Objects.requireNonNull(agentProfileRef, "agentProfileRef must not be null");
        Objects.requireNonNull(delegationConstraintRef, "delegationConstraintRef must not be null");
        if (!handle.agentProfileRef().equals(agentProfileRef)) {
            throw new IllegalArgumentException("agentProfileRef must match InvocationHandle");
        }
    }
}
