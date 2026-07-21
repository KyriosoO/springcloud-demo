package com.dylan.agent.planning.model;

/**
 * Planning 操作失败异常，由 D02_00 唯一负责。
 *
 * <p>由 PlanningService 在其内部阶段失败时抛出；通过独立通道交给 Lifecycle 形成 FAILED 终态。
 * 不把 cause 链、Runtime 原始响应或内部 plan 结果泄露给调用方。</p>
 */
public final class PlanningFailureException extends RuntimeException {

    private final PlanningFailure failure;

    public PlanningFailureException(PlanningFailure failure) {
        super(java.util.Objects.requireNonNull(failure, "failure must not be null").errorCode().name());
        this.failure = java.util.Objects.requireNonNull(failure);
    }

    public PlanningFailure failure() {
        return failure;
    }
}
