package com.dylan.agent.application;

import com.dylan.agent.api.contract.runtime.common.RuntimeTurnProjection;
import com.dylan.agent.invocation.model.InvocationHandle;
import com.dylan.agent.metadata.authorization.model.DelegationConstraintRef;
import com.dylan.agent.planning.model.PlanningCommand;

import java.util.List;
import java.util.Objects;

import org.springframework.stereotype.Component;

/**
 * 基于已提交的 InvocationHandle 创建不可变 Planning 命令。
 */
@Component
public class PlanningCommandFactory {

    public PlanningCommand create(
            InvocationHandle handle,
            String userMessage,
            List<RuntimeTurnProjection> history) {
        return create(handle, userMessage, history, null, null);
    }

    public PlanningCommand create(
            InvocationHandle handle,
            String userMessage,
            List<RuntimeTurnProjection> history,
            String requestedProfile,
            String materialType) {
        Objects.requireNonNull(handle, "handle must not be null");
        return new PlanningCommand(
                handle,
                userMessage,
                history,
                handle.agentProfileRef(),
                DelegationConstraintRef.CHAT_ALL,
                requestedProfile,
                materialType);
    }
}
