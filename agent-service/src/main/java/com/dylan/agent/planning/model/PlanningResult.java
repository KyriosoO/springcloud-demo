package com.dylan.agent.planning.model;

import java.time.Instant;

/**
 * Planning 结果封闭联合，由 D02_00 唯一负责。
 *
 * <p>{@code permits} 仅允许 {@link ExecutablePlanningResult} 和 {@link ResolvedClarification}。
 * Planning 异常和取消通过独立失败/取消通道交给 Lifecycle，不作为第三个 variant。
 */
public sealed interface PlanningResult
        permits ExecutablePlanningResult, ResolvedClarification {

    /** 与 InvocationHandle、Route、Plan 一致的 correlation。 */
    String requestCorrelationId();

    /** 必须等于 Handle deadline，不可延长。 */
    Instant absoluteDeadline();
}
