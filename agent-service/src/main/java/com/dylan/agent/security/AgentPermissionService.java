package com.dylan.agent.security;

import java.util.Set;

import org.springframework.stereotype.Component;

import com.dylan.agent.api.enums.AgentIntent;
import com.dylan.agent.api.enums.AgentOperator;
import com.dylan.agent.config.AgentProperties;
import com.dylan.agent.config.AgentProperties.DomainProperties;
import com.dylan.agent.config.AgentProperties.FieldProperties;
import com.dylan.agent.exception.AgentPermissionDeniedException;
import com.dylan.agent.model.AgentUserContext;
import com.dylan.agent.model.FieldPolicy;
import com.dylan.agent.model.MaskType;
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

    public AgentPermissionService(AgentProperties properties) {
        this.properties = properties;
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
        DomainProperties domainProps = properties.getDomains().get(domain);
        if (domainProps == null) {
            throw new AgentPermissionDeniedException("不支持的业务域: " + domain);
        }
        if (context.getRoles().stream().noneMatch(r -> domainProps.getAccessRoles().contains(r))) {
            throw new AgentPermissionDeniedException("当前账号无权访问该业务域。");
        }

        for (ValidatedFilter filter : query.getFilters()) {
            FieldProperties fp = requireField(domainProps, filter.getField());
            if (context.getRoles().stream().noneMatch(r -> fp.getFilterRoles().contains(r))) {
                throw new AgentPermissionDeniedException("当前账号无权使用该字段查询: " + filter.getField());
            }
            if (!fp.getOperators().contains(filter.getOperator())) {
                throw new AgentPermissionDeniedException(
                        com.dylan.agent.api.enums.AgentErrorCode.AGENT_OPERATOR_FORBIDDEN,
                        "不支持的操作符: " + filter.getOperator());
            }
        }

        for (String field : query.getSelectFields()) {
            FieldProperties fp = requireField(domainProps, field);
            if (context.getRoles().stream().noneMatch(r -> fp.getDisplayRoles().contains(r))) {
                throw new AgentPermissionDeniedException("当前账号无权查看该字段: " + field);
            }
        }
    }

    /** 获取字段的展示策略（操作符 + 角色 + 脱敏类型），用于结果脱敏。 */
    public FieldPolicy getDisplayPolicy(AgentUserContext context, String domain, String field) {
        DomainProperties domainProps = properties.getDomains().get(domain);
        if (domainProps == null) {
            throw new AgentPermissionDeniedException("不支持的业务域: " + domain);
        }
        FieldProperties fp = requireField(domainProps, field);
        return new FieldPolicy(field, fp.getOperators(), fp.getFilterRoles(), fp.getDisplayRoles(), fp.getMask());
    }

    /** 校验聚合查询权限：domain 访问 + filter 字段 filter 权限 + groupBy 字段 display 权限 + metric 字段 display 权限。 */
    public void checkAggregate(AgentUserContext context, String domain, ValidatedAggregateQuery query) {
        DomainProperties domainProps = properties.getDomains().get(domain);
        if (domainProps == null) {
            throw new AgentPermissionDeniedException("不支持的业务域: " + domain);
        }
        if (context.getRoles().stream().noneMatch(r -> domainProps.getAccessRoles().contains(r))) {
            throw new AgentPermissionDeniedException("当前账号无权访问该业务域。");
        }

        for (ValidatedFilter filter : query.getFilters()) {
            FieldProperties fp = requireField(domainProps, filter.getField());
            if (context.getRoles().stream().noneMatch(r -> fp.getFilterRoles().contains(r))) {
                throw new AgentPermissionDeniedException("当前账号无权使用该字段查询: " + filter.getField());
            }
            if (!fp.getOperators().contains(filter.getOperator())) {
                throw new AgentPermissionDeniedException(
                        com.dylan.agent.api.enums.AgentErrorCode.AGENT_OPERATOR_FORBIDDEN,
                        "不支持的操作符: " + filter.getOperator());
            }
        }

        for (String field : query.getGroupByFields()) {
            FieldProperties fp = requireField(domainProps, field);
            if (context.getRoles().stream().noneMatch(r -> fp.getDisplayRoles().contains(r))) {
                throw new AgentPermissionDeniedException("当前账号无权使用该字段分组: " + field);
            }
        }

        for (ValidatedAggregateMetric metric : query.getMetrics()) {
            if (metric.getFunction() == AggregateFunction.COUNT && metric.getField() == null) {
                continue;
            }
            FieldProperties fp = requireField(domainProps, metric.getField());
            if (context.getRoles().stream().noneMatch(r -> fp.getDisplayRoles().contains(r))) {
                throw new AgentPermissionDeniedException("当前账号无权查看该字段: " + metric.getField());
            }
        }
    }

    private FieldProperties requireField(DomainProperties domainProps, String field) {
        FieldProperties fp = domainProps.getFields().get(field);
        if (fp == null) {
            throw new AgentPermissionDeniedException("不支持的字段: " + field);
        }
        return fp;
    }
}
