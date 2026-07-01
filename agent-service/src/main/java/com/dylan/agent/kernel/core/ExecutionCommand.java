package com.dylan.agent.kernel.core;

import com.dylan.agent.invocation.model.InvocationHandle;
import com.dylan.agent.planning.model.ExecutablePlanningResult;

import java.util.Objects;

/**
 * Lifecycle 交给 Core 的不可变内部命令。
 * 聚合 InvocationHandle + 原始 ExecutablePlanningResult + CancellationToken。
 * Registration、Raw Plan、Snapshot 不得作为可替换并列参数。
 */
public final class ExecutionCommand {

    private final InvocationHandle handle;
    private final ExecutablePlanningResult planningResult;
    private final Object cancellation; // CancellationToken after D02_02

    public ExecutionCommand(InvocationHandle handle,
                            ExecutablePlanningResult planningResult,
                            Object cancellation) {
        this.handle = Objects.requireNonNull(handle);
        this.planningResult = Objects.requireNonNull(planningResult);
        this.cancellation = cancellation;

        // 构造器校验：Handle 与 PlanningResult 的 correlation、subject/owner/scope、deadline 一致
        if (!handle.requestCorrelationId().equals(planningResult.requestCorrelationId())) {
            throw new IllegalArgumentException(
                    "correlation mismatch: handle=" + handle.requestCorrelationId()
                            + " planning=" + planningResult.requestCorrelationId());
        }
        if (!handle.absoluteDeadline().equals(planningResult.absoluteDeadline())) {
            throw new IllegalArgumentException("absoluteDeadline mismatch");
        }
    }

    public InvocationHandle handle() { return handle; }
    public ExecutablePlanningResult planningResult() { return planningResult; }
    public Object cancellation() { return cancellation; }
}
