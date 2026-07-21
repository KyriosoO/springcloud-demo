package com.dylan.agent.planning.model;

import com.dylan.agent.api.contract.runtime.common.RuntimeTurnProjection;
import com.dylan.agent.shared.ref.AgentProfileRef;
import com.dylan.agent.invocation.model.InvocationHandle;
import com.dylan.agent.metadata.authorization.model.DelegationConstraintRef;

import java.util.List;
import java.util.Objects;

/**
 * 内部规划命令，由 D02_00 唯一负责。
 *
 * <p>入口/生命周期层在启动事务提交后构造此不可变命令并交给 PlanningService。
 * 字段全部来自 InvocationHandle 的已提交引用，不接受调用方自报权限、Context 或 DTO。
 *
 * <p>构造器验证 agentProfileRef 等于 InvocationHandle 绑定的 Profile，且 deadline 未被外部字段覆盖。
 * 不存在 Chat/Task 两套命令。
 */
public final class PlanningCommand {

    private final InvocationHandle handle;
    private final String userMessage;
    private final List<RuntimeTurnProjection> history;
    private final AgentProfileRef agentProfileRef;
    private final DelegationConstraintRef delegationConstraintRef;
    private final String requestedProfile;
    private final String materialType;

    public PlanningCommand(
            InvocationHandle handle,
            String userMessage,
            List<RuntimeTurnProjection> history,
            AgentProfileRef agentProfileRef,
            DelegationConstraintRef delegationConstraintRef) {
        this(handle, userMessage, history, agentProfileRef, delegationConstraintRef, null, null);
    }

    public PlanningCommand(
            InvocationHandle handle,
            String userMessage,
            List<RuntimeTurnProjection> history,
            AgentProfileRef agentProfileRef,
            DelegationConstraintRef delegationConstraintRef,
            String requestedProfile,
            String materialType) {
        this.handle = Objects.requireNonNull(handle, "handle must not be null");
        this.userMessage = Objects.requireNonNull(userMessage, "userMessage must not be null");
        if (userMessage.isBlank()) {
            throw new IllegalArgumentException("userMessage must not be blank");
        }
        this.history = List.copyOf(history != null ? history : List.of());
        this.agentProfileRef = Objects.requireNonNull(agentProfileRef, "agentProfileRef must not be null");
        this.delegationConstraintRef = delegationConstraintRef == null
                ? DelegationConstraintRef.CHAT_ALL
                : delegationConstraintRef;
        this.requestedProfile = normalizeOptional(requestedProfile, "requestedProfile");
        this.materialType = normalizeOptional(materialType, "materialType");

// 构造器不变量：agentProfileRef 必须等于 InvocationHandle 绑定的目标 Profile。
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

    public DelegationConstraintRef delegationConstraintRef() {
        return delegationConstraintRef;
    }

    public String requestedProfile() { return requestedProfile; }

    public String materialType() { return materialType; }

    private static String normalizeOptional(String value, String name) {
        if (value == null) return null;
        String normalized = value.trim();
        if (normalized.isEmpty()) return null;
        if (normalized.length() > 64 || !normalized.matches("[A-Za-z0-9][A-Za-z0-9._-]{0,63}")) {
            throw new IllegalArgumentException(name + " is invalid");
        }
        return normalized;
    }
}
