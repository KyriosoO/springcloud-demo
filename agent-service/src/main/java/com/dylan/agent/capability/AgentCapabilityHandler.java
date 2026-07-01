package com.dylan.agent.capability;

import com.dylan.agent.api.capability.AgentCapabilityRiskLevel;
import com.dylan.agent.api.enums.AgentIntent;
import com.dylan.agent.capability.model.ValidatedCapabilityPlan;

/**
 * 能力处理器接口，一个 handler 对应一个 {@link AgentIntent}。
 *
 * <p>{@code validate} 将 Runtime 原始 plan 校验为可信的 {@link ValidatedCapabilityPlan}；
 * {@code execute} 执行权限校验、适配器调用、结果装配，返回统一的 {@link CapabilityExecutionResult}。
 * Orchestrator 不应按 intent 分支，全部通过此接口委托。
 *
 * <p>{@link #riskLevel()} 定义了该 handler 的风险等级声明。
 * 首期 {@code CapabilityDescriptorFactory} 不通过 handler 动态读取 riskLevel，
 * 而是在 descriptor 中直接声明 {@code AgentCapabilityRiskLevel}；
 * 这是有意为之——当前所有能力均为 READ_ONLY，handler 的 riskLevel 仅作为接口契约预留，
 * 供后续不同 handler 返回不同风险等级时再由 factory 或 orchestrator 读取。
 *
 * @param <P> 该 handler 产出的具体 validated plan 类型
 */
public interface AgentCapabilityHandler<P extends ValidatedCapabilityPlan> {

    /** 该 handler 注册的 intent。 */
    AgentIntent intent();

    /** 风险等级，直接使用 API 级 {@link AgentCapabilityRiskLevel}。 */
    AgentCapabilityRiskLevel riskLevel();

    /**
     * 校验 Runtime plan（envelope 已由 {@link CapabilityRouteResolver} 检查），
     * 产出可信的 validated plan。
     */
    P validate(CapabilityValidationContext context);

    /**
     * 执行已校验的 plan — 权限检查、调用 adapter、处理结果 — 返回统一执行结果。
     */
    CapabilityExecutionResult execute(
            CapabilityExecutionContext context,
            P plan);
}
