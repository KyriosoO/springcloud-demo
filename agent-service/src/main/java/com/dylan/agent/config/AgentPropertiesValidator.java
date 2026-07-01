package com.dylan.agent.config;

import java.util.Set;

import org.springframework.beans.factory.InitializingBean;
import org.springframework.stereotype.Component;

import com.dylan.agent.adapter.QueryableAdapterRegistry;
import com.dylan.agent.adapter.AggregatableAdapterRegistry;
import com.dylan.agent.api.enums.AgentFieldType;
import com.dylan.agent.api.enums.AgentIntent;
import com.dylan.agent.api.enums.AgentOperator;
import com.dylan.agent.capability.AgentCapabilityHandlerRegistry;
import com.dylan.agent.model.MaskType;
import com.dylan.agent.planning.filter.OperatorSemantics;

/**
 * 启动时校验 AgentProperties 的完整性与 Adapter 一致性。
 */
@Component
public class AgentPropertiesValidator implements InitializingBean {

    private final AgentProperties properties;
    private final QueryableAdapterRegistry adapterRegistry;
    private final AgentCapabilityHandlerRegistry capabilityHandlerRegistry;
    private final AggregatableAdapterRegistry aggregateAdapterRegistry;

    public AgentPropertiesValidator(AgentProperties properties,
                                     QueryableAdapterRegistry adapterRegistry,
                                     AgentCapabilityHandlerRegistry capabilityHandlerRegistry,
                                     AggregatableAdapterRegistry aggregateAdapterRegistry) {
        this.properties = properties;
        this.adapterRegistry = adapterRegistry;
        this.capabilityHandlerRegistry = capabilityHandlerRegistry;
        this.aggregateAdapterRegistry = aggregateAdapterRegistry;
    }

    @Override
    public void afterPropertiesSet() {
        validateIntentRoles();
        validateCapabilityHandlers();
        validateDomainConfig();
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

    private void validateDomainConfig() {
        var domains = properties.getDomains();
        if (domains == null || domains.isEmpty()) {
            throw new IllegalStateException("agent.domains 必须至少配置一个 domain。");
        }

        // 配置 domain 集合与已装配 Adapter 集合一致
        Set<String> configDomains = domains.keySet();
        Set<String> adapterDomains = adapterRegistry.domains();
        if (!configDomains.equals(adapterDomains)) {
            throw new IllegalStateException(
                    "配置 domain 集合与已装配 Adapter 不一致。"
                    + "config=" + configDomains + " adapter=" + adapterDomains);
        }

        for (var domainEntry : domains.entrySet()) {
            String domainName = domainEntry.getKey();
            var dp = domainEntry.getValue();

            if (dp.getAliases() == null || dp.getAliases().isEmpty()) {
                throw new IllegalStateException("agent.domains." + domainName + ".aliases 必须非空。");
            }
            if (dp.getAccessRoles() == null || dp.getAccessRoles().isEmpty()) {
                throw new IllegalStateException("agent.domains." + domainName + ".access-roles 必须非空。");
            }
            if (dp.getDefaultSelectFields() == null || dp.getDefaultSelectFields().isEmpty()) {
                throw new IllegalStateException("agent.domains." + domainName + ".default-select-fields 必须非空。");
            }
            if (dp.getFields() == null || dp.getFields().isEmpty()) {
                throw new IllegalStateException("agent.domains." + domainName + ".fields 必须配置。");
            }

            // 字段集合精确等于 Adapter supportedFields
            Set<String> configFields = dp.getFields().keySet();
            Set<String> adapterFields = adapterRegistry.supportedFields(domainName);
            if (!configFields.equals(adapterFields)) {
                throw new IllegalStateException(
                        "domain " + domainName + " 配置字段集合与 Adapter 不一致。"
                        + "config=" + configFields + " adapter=" + adapterFields);
            }

            // 逐字段校验
            for (var entry : dp.getFields().entrySet()) {
                String name = entry.getKey();
                var fp = entry.getValue();
                if (fp.getType() == null) {
                    throw new IllegalStateException("字段 " + domainName + "." + name + " 的 type 必须配置。");
                }
                if (fp.getOperators() == null || fp.getOperators().isEmpty()) {
                    throw new IllegalStateException("字段 " + domainName + "." + name + " 的 operators 必须非空。");
                }
                for (AgentOperator operator : fp.getOperators()) {
                    if (!OperatorSemantics.supports(operator, fp.getType())) {
                        throw new IllegalStateException(
                                "字段 " + domainName + "." + name
                                + " 的 operator " + operator
                                + " 与字段类型 " + fp.getType()
                                + " 不兼容。");
                    }
                }
                if (fp.getFilterRoles() == null || fp.getFilterRoles().isEmpty()) {
                    throw new IllegalStateException("字段 " + domainName + "." + name + " 的 filter-roles 必须非空。");
                }
                if (fp.getDisplayRoles() == null || fp.getDisplayRoles().isEmpty()) {
                    throw new IllegalStateException("字段 " + domainName + "." + name + " 的 display-roles 必须非空。");
                }
                if (fp.getMask() == null) {
                    throw new IllegalStateException("字段 " + domainName + "." + name + " 的 mask 必须配置。");
                }
                if (fp.getType() == AgentFieldType.INSTANT
                        && (fp.getFormatHint() == null || fp.getFormatHint().isBlank())) {
                    throw new IllegalStateException(
                            "INSTANT 字段 " + domainName + "." + name + " 必须提供 format-hint。");
                }
                if (fp.getType() == AgentFieldType.DECIMAL) {
                    Integer precision = fp.getDecimalPrecision();
                    Integer scale = fp.getDecimalScale();
                    if (precision == null || scale == null
                            || precision <= 0 || scale < 0 || scale > precision) {
                        throw new IllegalStateException(
                                "DECIMAL 字段 " + domainName + "." + name
                                + " 必须配置合法的 decimal-precision 和 decimal-scale。");
                    }
                } else if (fp.getDecimalPrecision() != null || fp.getDecimalScale() != null) {
                    throw new IllegalStateException(
                            "非 DECIMAL 字段 " + domainName + "." + name
                            + " 不允许配置 decimal-precision 或 decimal-scale。");
                }
            }

            // default select fields 必须存在
            for (String df : dp.getDefaultSelectFields()) {
                if (!dp.getFields().containsKey(df)) {
                    throw new IllegalStateException(
                            "domain " + domainName + " default select field '" + df + "' 在 fields 配置中不存在。");
                }
            }
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
        if (aggregateAdapterRegistry.domains().isEmpty()) {
            throw new IllegalStateException(
                    "agent.aggregate 已配置但无 AggregatableAdapter 实现。");
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
