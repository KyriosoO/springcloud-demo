package com.dylan.agent.invocation.model;

import com.dylan.agent.shared.ref.AgentProfileRef;

import java.time.Clock;
import java.time.Duration;
import java.time.Instant;
import java.util.Objects;

/**
 * Start 事务提交后由 Lifecycle 返回的不可变调用引用。
 *
 * <p>唯一绑定 invocationId、invocation type、origin、subject/scope、
 * agentProfileRef 和 absolute deadline。不保存 JWT、权限、PlanningResult 或可变状态。
 *
 * <p>当前只创建 CHAT origin + ConversationScope。
 */
public final class InvocationHandle {

    private final String invocationId;
    private final InvocationType invocationType;
    private final InvocationOrigin origin;
    private final String requestCorrelationId;
    private final ExecutionSubjectRef subject;
    private final ContextOwnerRef owner;
    private final InvocationScope scope;
    private final AgentProfileRef agentProfileRef;
    private final Instant absoluteDeadline;

    public static InvocationHandle forChat(
            String invocationId,
            ChatInvocationOrigin origin,
            String requestCorrelationId,
            ExecutionSubjectRef subject,
            ContextOwnerRef owner,
            ConversationScope scope,
            AgentProfileRef agentProfileRef,
            Instant absoluteDeadline) {
        if (!origin.conversationId().equals(scope.scopeId())) {
            throw new IllegalArgumentException("origin conversationId must match scopeId");
        }
        return new InvocationHandle(invocationId, InvocationType.CHAT, origin,
                requestCorrelationId, subject, owner, scope, agentProfileRef,
                absoluteDeadline);
    }

    private InvocationHandle(
            String invocationId,
            InvocationType invocationType,
            InvocationOrigin origin,
            String requestCorrelationId,
            ExecutionSubjectRef subject,
            ContextOwnerRef owner,
            InvocationScope scope,
            AgentProfileRef agentProfileRef,
            Instant absoluteDeadline) {
        this.invocationId = Objects.requireNonNull(invocationId);
        this.invocationType = Objects.requireNonNull(invocationType);
        this.origin = Objects.requireNonNull(origin);
        this.requestCorrelationId = Objects.requireNonNull(requestCorrelationId);
        this.subject = Objects.requireNonNull(subject);
        this.owner = Objects.requireNonNull(owner);
        this.scope = Objects.requireNonNull(scope);
        this.agentProfileRef = Objects.requireNonNull(agentProfileRef);
        this.absoluteDeadline = Objects.requireNonNull(absoluteDeadline);

        if (invocationId.isBlank()) {
            throw new IllegalArgumentException("invocationId must not be blank");
        }
        if (requestCorrelationId.isBlank()) {
            throw new IllegalArgumentException("requestCorrelationId must not be blank");
        }

        // 构造器强制 type/origin/scope 闭合
        if (!origin.isCompatibleWith(invocationType)) {
            throw new IllegalArgumentException(
                    "origin " + origin + " is not compatible with type " + invocationType);
        }
        if (!scope.isCompatibleWith(origin)) {
            throw new IllegalArgumentException(
                    "scope " + scope + " is not compatible with origin " + origin);
        }
    }

    public String invocationId() { return invocationId; }
    public InvocationType invocationType() { return invocationType; }
    public InvocationOrigin origin() { return origin; }
    public String requestCorrelationId() { return requestCorrelationId; }
    public ExecutionSubjectRef subject() { return subject; }
    public ContextOwnerRef owner() { return owner; }
    public InvocationScope scope() { return scope; }
    public AgentProfileRef agentProfileRef() { return agentProfileRef; }
    public Instant absoluteDeadline() { return absoluteDeadline; }

    public Duration remaining(Clock clock) {
        Instant now = Objects.requireNonNull(clock).instant();
        return now.isBefore(absoluteDeadline)
                ? Duration.between(now, absoluteDeadline)
                : Duration.ZERO;
    }

    public boolean isExpired(Clock clock) {
        return remaining(clock).isZero();
    }
}
