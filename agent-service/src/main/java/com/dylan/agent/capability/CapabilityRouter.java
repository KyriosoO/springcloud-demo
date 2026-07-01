package com.dylan.agent.capability;

import org.springframework.stereotype.Component;

import com.dylan.agent.api.enums.AgentIntent;
import com.dylan.agent.exception.AgentPlanValidationException;

/**
 * {@link AgentCapabilityHandlerRegistry} 的薄门面 — 按 intent 查找 handler。
 *
 * <p>新增 intent 只需新增 handler Bean，registry map 自动吸收，
 * 此处和 orchestrator 均无需 switch/if-else。
 */
@Component
public class CapabilityRouter {

    private final AgentCapabilityHandlerRegistry registry;

    public CapabilityRouter(AgentCapabilityHandlerRegistry registry) {
        this.registry = registry;
    }

    public AgentCapabilityHandler<?> route(AgentIntent intent) {
        if (intent == null) {
            throw new AgentPlanValidationException("Plan intent 为空。");
        }
        return registry.getRequired(intent);
    }
}
