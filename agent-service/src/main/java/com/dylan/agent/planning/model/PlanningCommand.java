package com.dylan.agent.planning.model;

import com.dylan.agent.api.contract.runtime.common.RuntimeTurnProjection;
import com.dylan.agent.shared.ref.AgentProfileRef;
import com.dylan.agent.invocation.model.InvocationHandle;

import java.util.List;
import java.util.Objects;

/**
 * 内部 Planning 命令，由 D02_00 唯一负责。
 *
 * <p>Entry/Lifecycle 在 Start 事务提交后构造此不可变命令并交给 PlanningService。
 * 字段全部来自 InvocationHandle 的已提交引用——不接受调用方自报权限、Context 或 DTO。
 *
 * <p>构造器验证 agentProfileRef 等于 Handle 绑定的 Profile，且 deadline 未被外部字段覆盖。
 * 不存在 Chat/Task 两套 Command。
 */
public final class PlanningCommand {

    private final InvocationHandle handle;
    private final String userMessage;
    private final List<RuntimeTurnProjection> history;
    private final AgentProfileRef agentProfileRef;
    private final Object delegationConstraintRef; // DelegationConstraintRef — CHAT uses none()

    public PlanningCommand(
            InvocationHandle handle,
            String userMessage,
            List<RuntimeTurnProjection> history,
            AgentProfileRef agentProfileRef,
            Object delegationConstraintRef) {
        this.handle = Objects.requireNonNull(handle, "handle must not be null");
        this.userMessage = Objects.requireNonNull(userMessage, "userMessage must not be null");
        if (userMessage.isBlank()) {
            throw new IllegalArgumentException("userMessage must not be blank");
        }
        this.history = List.copyOf(history != null ? history : List.of());
        this.agentProfileRef = Objects.requireNonNull(agentProfileRef, "agentProfileRef must not be null");
        this.delegationConstraintRef = delegationConstraintRef;

        // 构造器不变量：agentProfileRef 必须等于 Handle 绑定的目标 Profile
        if (!handle.agentProfileRef().equals(agentProfileRef)) {
            throw new IllegalArgumentException(
                    "agentProfileRef " + agentProfileRef + " must equal handle.agentProfileRef "
                            + handle.agentProfileRef());
        }
    }

    public InvocationHandle handle() {
        return handle;
    }

    public String userMessage() {
        return userMessage;
    }

    public List<RuntimeTurnProjection> history() {
        return history;
    }

    public AgentProfileRef agentProfileRef() {
        return agentProfileRef;
    }

    public Object delegationConstraintRef() {
        return delegationConstraintRef;
    }
}
