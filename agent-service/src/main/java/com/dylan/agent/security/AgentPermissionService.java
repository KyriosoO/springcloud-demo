package com.dylan.agent.security;

import java.util.Set;

import org.springframework.stereotype.Component;

import com.dylan.agent.api.enums.AgentIntent;
import com.dylan.agent.adapter.api.AdapterRole;
import com.dylan.agent.config.AgentProperties;
import com.dylan.agent.exception.AgentPermissionDeniedException;
import com.dylan.agent.model.AgentUserContext;
import com.dylan.agent.model.FieldPolicy;
import com.dylan.agent.model.MaskType;
import com.dylan.agent.metadata.domain.internal.DomainCatalogView;
import com.dylan.agent.metadata.domain.internal.DomainCatalogView.DomainView;
import com.dylan.agent.metadata.domain.internal.DomainCatalogView.FieldView;
import com.dylan.agent.adapter.api.query.ValidatedFilter;
import com.dylan.agent.adapter.api.query.ValidatedQuery;
import com.dylan.agent.adapter.api.aggregate.ValidatedAggregateMetric;
import com.dylan.agent.adapter.api.aggregate.ValidatedAggregateQuery;
import com.dylan.agent.api.enums.AggregateFunction;

/**
 * Agent 权限服务，按顺序校验 intent/domain/field/operator/display。
 * 任一步失败即停止，不调用 Adapter。
 */
@Component
public class AgentPermissionService {

    private final AgentProperties properties;
    private final DomainCatalogView domainCatalogView;

    public AgentPermissionService(AgentProperties properties, DomainCatalogView domainCatalogView) {
        this.properties = properties;
        this.domainCatalogView = domainCatalogView;
    }

    /** 校验用户至少拥有一个 intentRoles 中配置的角色。 */
    public void requireAgentAccess(AgentUserContext context) {
        Set<String> allowed = properties.getIntentRoles().values().stream()
                .flatMap(Set::stream).collect(java.util.stream.Collectors.toSet());
        if (context.getRoles().stream().noneMatch(allowed::contains)) {
            throw new AgentPermissionDeniedException(com.dylan.agent.api.enums.AgentErrorCode.AGENT_INTENT_FORBIDDEN,
                    "当前账号没有 Agent 访问权限。");
        }
    }

    /** 校验用户是否有权执行指定 intent。 */
    public void checkIntent(AgentUserContext context, AgentIntent intent) {
        Set<String> allowed = properties.getIntentRoles().getOrDefault(intent, Set.of());
        if (context.getRoles().stream().noneMatch(allowed::contains)) {
            throw new AgentPermissionDeniedException(com.dylan.agent.api.enums.AgentErrorCode.AGENT_INTENT_FORBIDDEN,
                    "当前账号无权执行该操作。");
        }
    }

    /** 依次校验 domain 访问权限、filter 字段的 filter 权限、操作符白名单、selectFields 的 display 权限。 */
    public void checkQuery(AgentUserContext context, String domain, ValidatedQuery query) {
        DomainView domainView = requireDomain(domain, AdapterRole.QUERYABLE);
        if (domainView == null) {
            throw new AgentPermissionDeniedException("不支持的业务域: " + domain);
        }

        for (ValidatedFilter filter : query.getFilters()) {
            FieldView fp = requireField(domainView, filter.getField());
            if (!fp.operators().contains(filter.getOperator())) {
                throw new AgentPermissionDeniedException(
                        com.dylan.agent.api.enums.AgentErrorCode.AGENT_OPERATOR_FORBIDDEN,
                        "不支持的操作符: " + filter.getOperator());
            }
        }

        for (String field : query.getSelectFields()) {
            requireField(domainView, field);
        }
    }

    /** 获取字段的展示策略（操作符 + 角色 + 脱敏类型），用于结果脱敏。 */
    public FieldPolicy getDisplayPolicy(AgentUserContext context, String domain, String field) {
        DomainView domainView = requireDomain(domain, AdapterRole.QUERYABLE);
        if (domainView == null) {
            throw new AgentPermissionDeniedException("不支持的业务域: " + domain);
        }
        FieldView fp = requireField(domainView, field);
        return new FieldPolicy(field, fp.operators(), context.getRoles(), context.getRoles(), MaskType.NONE);
    }

    /** 校验聚合查询权限：domain 访问 + filter 字段 filter 权限 + groupBy 字段 display 权限 + metric 字段 display 权限。 */
    public void checkAggregate(AgentUserContext context, String domain, ValidatedAggregateQuery query) {
        DomainView domainView = requireDomain(domain, AdapterRole.AGGREGATABLE);
        if (domainView == null) {
            throw new AgentPermissionDeniedException("不支持的业务域: " + domain);
        }

        for (ValidatedFilter filter : query.getFilters()) {
            FieldView fp = requireField(domainView, filter.getField());
            if (!fp.operators().contains(filter.getOperator())) {
                throw new AgentPermissionDeniedException(
                        com.dylan.agent.api.enums.AgentErrorCode.AGENT_OPERATOR_FORBIDDEN,
                        "不支持的操作符: " + filter.getOperator());
            }
        }

        for (String field : query.getGroupByFields()) {
            requireField(domainView, field);
        }

        for (ValidatedAggregateMetric metric : query.getMetrics()) {
            if (metric.getFunction() == AggregateFunction.COUNT && metric.getField() == null) {
                continue;
            }
            requireField(domainView, metric.getField());
        }
    }

    private DomainView requireDomain(String domain, AdapterRole role) {
        try {
            return domainCatalogView.requireDomain(domain, role);
        } catch (IllegalArgumentException ex) {
            return null;
        }
    }

    private FieldView requireField(DomainView domain, String field) {
        try {
            return domain.requireField(field);
        } catch (IllegalArgumentException ex) {
            throw new AgentPermissionDeniedException("不支持的字段: " + field);
        }
    }
}
