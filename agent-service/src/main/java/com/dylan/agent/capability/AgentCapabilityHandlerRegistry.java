package com.dylan.agent.capability;

import java.util.EnumMap;
import java.util.List;
import java.util.Map;
import java.util.Set;

import org.springframework.stereotype.Component;

import com.dylan.agent.api.enums.AgentIntent;
import com.dylan.agent.exception.AgentPlanValidationException;

/**
 * 收集所有 {@link AgentCapabilityHandler} Spring Bean，按 {@link AgentIntent}
 * 构建查找表。启动时拒绝 null intent、重复 intent、空 handler 列表。
 *
 * <p>使用 {@link EnumMap} 实现 O(1) 查找；构造完成后通过 {@link Map#copyOf} 冻结。
 */
@Component
public class AgentCapabilityHandlerRegistry {

    private final Map<AgentIntent, AgentCapabilityHandler<?>> handlers;

    public AgentCapabilityHandlerRegistry(
            List<AgentCapabilityHandler<?>> handlerList) {
        Map<AgentIntent, AgentCapabilityHandler<?>> map =
                new EnumMap<>(AgentIntent.class);

        for (AgentCapabilityHandler<?> handler : handlerList) {
            if (handler.intent() == null) {
                throw new IllegalStateException(
                        "AgentCapabilityHandler intent must not be null");
            }
            AgentCapabilityHandler<?> existing =
                    map.put(handler.intent(), handler);
            if (existing != null) {
                throw new IllegalStateException(
                        "Duplicate AgentCapabilityHandler intent: "
                        + handler.intent());
            }
        }

        if (map.isEmpty()) {
            throw new IllegalStateException(
                    "至少需要一个 AgentCapabilityHandler。");
        }

        this.handlers = Map.copyOf(map);
    }

    /** 按 intent 查找 handler，不存在时抛异常。 */
    public AgentCapabilityHandler<?> getRequired(AgentIntent intent) {
        AgentCapabilityHandler<?> handler = handlers.get(intent);
        if (handler == null) {
            throw new AgentPlanValidationException(
                    "不支持的 Agent intent: " + intent);
        }
        return handler;
    }

    /** 返回所有已注册的 intent 集合。 */
    public Set<AgentIntent> supportedIntents() {
        return handlers.keySet();
    }
}
