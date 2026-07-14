package com.dylan.agent.shared.ref;

import java.util.Objects;
import java.util.Optional;

/**
 * 稳定 Agent Profile 引用，由 D02_00 唯一提供。
 *
 * <p>字段：
 * <ul>
 *   <li>{@code agentId} — 稳定 Profile ID，非空；</li>
 *   <li>{@code expectedVersion} — 可选精确版本；未指定时只允许 Start 前解析 active version，
 *       Planning/Execution 绑定后禁止省略。</li>
 * </ul>
 *
 * <p>Profile Registry、InvocationHandle 和 PlanningCommand 共同消费此唯一类型。
 * 当前由 CHAT Invocation 显式绑定目标 Profile 的精确 ref。
 */
public final class AgentProfileRef {

    private final String agentId;
    private final String expectedVersion;

    private AgentProfileRef(String agentId, String expectedVersion) {
        this.agentId = Objects.requireNonNull(agentId, "agentId must not be null");
        if (agentId.isBlank()) {
            throw new IllegalArgumentException("agentId must not be blank");
        }
        this.expectedVersion = expectedVersion;
    }

    /** 创建带精确版本的引用。 */
    public static AgentProfileRef of(String agentId, String expectedVersion) {
        Objects.requireNonNull(expectedVersion, "expectedVersion must not be null");
        if (expectedVersion.isBlank()) {
            throw new IllegalArgumentException("expectedVersion must not be blank");
        }
        return new AgentProfileRef(agentId, expectedVersion);
    }

    /** 创建不带版本的引用（仅用于 Start 前解析 active version）。 */
    public static AgentProfileRef withoutVersion(String agentId) {
        return new AgentProfileRef(agentId, null);
    }

    public String agentId() {
        return agentId;
    }

    public Optional<String> expectedVersion() {
        return Optional.ofNullable(expectedVersion);
    }

    @Override
    public boolean equals(Object o) {
        if (this == o) return true;
        if (!(o instanceof AgentProfileRef that)) return false;
        return agentId.equals(that.agentId)
                && Objects.equals(expectedVersion, that.expectedVersion);
    }

    @Override
    public int hashCode() {
        return Objects.hash(agentId, expectedVersion);
    }

    @Override
    public String toString() {
        return expectedVersion != null
                ? "AgentProfileRef{agentId=" + agentId + ", version=" + expectedVersion + "}"
                : "AgentProfileRef{agentId=" + agentId + "}";
    }
}
