package com.dylan.agent.planning.model;

/**
 * 内部 Planning 失败或取消阶段。
 *
 * <p>该枚举不是 invocation 终态，也不会作为 API 响应枚举暴露。</p>
 */
public enum PlanningStage {
    HISTORY,
    PROFILE_POLICY,
    CATALOG,
    ROUTE,
    REGISTRATION,
    CONTEXT,
    PLAN,
    SNAPSHOT_FREEZE
}
