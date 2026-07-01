package com.dylan.agent.config;

import java.util.Set;

import org.springframework.beans.factory.InitializingBean;
import org.springframework.stereotype.Component;

import com.dylan.agent.api.enums.AgentIntent;
import com.dylan.agent.capability.AgentCapabilityHandlerRegistry;

/**
 * 启动时校验 AgentProperties 的完整性与 Adapter 一致性。
 */
@Component
public class AgentPropertiesValidator implements InitializingBean {

    private final AgentProperties properties;
    private final AgentCapabilityHandlerRegistry capabilityHandlerRegistry;

    public AgentPropertiesValidator(AgentProperties properties,
                                     AgentCapabilityHandlerRegistry capabilityHandlerRegistry) {
        this.properties = properties;
        this.capabilityHandlerRegistry = capabilityHandlerRegistry;
    }

    @Override
    public void afterPropertiesSet() {
        validateIntentRoles();
        validateCapabilityHandlers();
        validateRuntime();
        validateQuery();
        validateAggregateConfig();
        validateConversation();
    }

    private void validateIntentRoles() {
        var intentRoles = properties.getIntentRoles();
        if (intentRoles == null) {
            throw new IllegalStateException("agent.intent-roles 必须配置。");
        }
        for (AgentIntent intent : AgentIntent.values()) {
            Set<String> roles = intentRoles.get(intent);
            if (roles == null || roles.isEmpty()) {
                throw new IllegalStateException("agent.intent-roles." + intent + " 必须配置非空角色。");
            }
        }
    }

    private void validateCapabilityHandlers() {
        Set<AgentIntent> configuredIntents =
                properties.getIntentRoles().keySet();
        Set<AgentIntent> handlerIntents =
                capabilityHandlerRegistry.supportedIntents();

        for (AgentIntent intent : configuredIntents) {
            if (!handlerIntents.contains(intent)) {
                throw new IllegalStateException(
                        "agent.intent-roles 配置了未注册 handler 的 intent: "
                        + intent);
            }
        }

        for (AgentIntent intent : handlerIntents) {
            if (!configuredIntents.contains(intent)) {
                throw new IllegalStateException(
                        "已注册 AgentCapabilityHandler 但缺少 intent-roles 配置: "
                        + intent);
            }
        }

        if (!handlerIntents.contains(AgentIntent.QUERY)) {
            throw new IllegalStateException("缺少 QUERY capability handler。");
        }

        if (!handlerIntents.contains(AgentIntent.CLARIFY)) {
            throw new IllegalStateException("缺少 CLARIFY capability handler。");
        }
        if (!handlerIntents.contains(AgentIntent.AGGREGATE)) {
            throw new IllegalStateException("缺少 AGGREGATE capability handler。");
        }
    }

    private void validateRuntime() {
        var rt = properties.getRuntime();
        if (rt.getBaseUrl() == null || rt.getBaseUrl().isBlank()) {
            throw new IllegalStateException("agent.runtime.base-url 必须配置。");
        }
        if (rt.getSharedKey() == null || rt.getSharedKey().length() < 16) {
            throw new IllegalStateException("agent.runtime.shared-key 长度必须至少 16。");
        }
        if (rt.getConnectTimeout() == null || rt.getReadTimeout() == null) {
            throw new IllegalStateException("agent.runtime 超时配置必须提供。");
        }
        if (rt.getConnectTimeout().isZero() || rt.getConnectTimeout().isNegative()
                || rt.getReadTimeout().isZero() || rt.getReadTimeout().isNegative()) {
            throw new IllegalStateException("agent.runtime 超时配置必须为正数。");
        }
        if (rt.getMaxResponseBytes() <= 0) {
            throw new IllegalStateException("agent.runtime.max-response-bytes 必须为正数。");
        }
    }

    private void validateQuery() {
        var q = properties.getQuery();
        if (q.getDefaultSize() <= 0) {
            throw new IllegalStateException("agent.query.default-size 必须为正数。");
        }
        if (q.getMaxSize() <= 0) {
            throw new IllegalStateException("agent.query.max-size 必须为正数。");
        }
        if (q.getDefaultSize() > q.getMaxSize()) {
            throw new IllegalStateException("agent.query.default-size 不能超过 max-size。");
        }
        if (q.getMaxSize() > q.getMaxResultWindow()) {
            throw new IllegalStateException("agent.query.max-size 不能超过 max-result-window。");
        }
        if (q.getMaxFilters() <= 0) {
            throw new IllegalStateException("agent.query.max-filters 必须为正数。");
        }
        if (q.getMaxInValues() <= 0) {
            throw new IllegalStateException("agent.query.max-in-values 必须为正数。");
        }
        if (q.getMaxFilterValueLength() <= 0) {
            throw new IllegalStateException("agent.query.max-filter-value-length 必须为正数。");
        }
        if (q.getMaxDownstreamResponseBytes() <= 0) {
            throw new IllegalStateException("agent.query.max-downstream-response-bytes 必须为正数。");
        }
    }

    private void validateAggregateConfig() {
        var a = properties.getAggregate();
        if (a == null) {
            throw new IllegalStateException("agent.aggregate 必须配置。");
        }
        if (a.getMaxMetrics() <= 0) {
            throw new IllegalStateException("agent.aggregate.max-metrics 必须为正数。");
        }
        if (a.getMaxGroupFields() <= 0) {
            throw new IllegalStateException("agent.aggregate.max-group-fields 必须为正数。");
        }
        if (a.getDefaultMaxRows() <= 0) {
            throw new IllegalStateException("agent.aggregate.default-max-rows 必须为正数。");
        }
        if (a.getMaxMaxRows() <= 0) {
            throw new IllegalStateException("agent.aggregate.max-max-rows 必须为正数。");
        }
        if (a.getDefaultMaxRows() > a.getMaxMaxRows()) {
            throw new IllegalStateException("agent.aggregate.default-max-rows 不能超过 max-max-rows。");
        }
    }

    private void validateConversation() {
        var c = properties.getConversation();
        if (c.getRecentTurnLimit() <= 0) {
            throw new IllegalStateException("agent.conversation.recent-turn-limit 必须为正数。");
        }
        if (c.getRetentionDays() <= 0) {
            throw new IllegalStateException("agent.conversation.retention-days 必须为正数。");
        }
        if (c.getCleanupDelay() == null || c.getCleanupDelay().isZero() || c.getCleanupDelay().isNegative()) {
            throw new IllegalStateException("agent.conversation.cleanup-delay 必须为正数。");
        }
    }
}
