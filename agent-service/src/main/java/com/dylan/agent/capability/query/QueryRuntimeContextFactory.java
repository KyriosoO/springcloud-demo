package com.dylan.agent.capability.query;

import com.dylan.agent.api.plan.AgentFilter;
import com.dylan.agent.api.runtime.RuntimeQueryContext;
import com.dylan.agent.capability.model.ValidatedQueryPlan;

/** 包级私有工厂，从 ValidatedQueryPlan 构建 RuntimeQueryContext，用于持久化 query_context_json 供下一轮 MERGE 使用。 */
final class QueryRuntimeContextFactory {

    private QueryRuntimeContextFactory() {
    }

    static RuntimeQueryContext toRuntimeQueryContext(
            String sourceTurnId,
            ValidatedQueryPlan plan) {
        RuntimeQueryContext context = new RuntimeQueryContext();
        context.setSourceTurnId(sourceTurnId);
        context.setDomain(plan.domain());
        context.setFilters(plan.query().getFilters().stream()
                .map(filter -> {
                    AgentFilter value = new AgentFilter();
                    value.setField(filter.getField());
                    value.setOperator(filter.getOperator());
                    value.setValue(filter.getValue());
                    value.setValues(filter.getValues().isEmpty()
                            ? null : filter.getValues());
                    return value;
                })
                .toList());
        context.setSelectFields(plan.query().getSelectFields());
        context.setPage(plan.query().getPage());
        context.setSize(plan.query().getSize());
        return context;
    }
}
