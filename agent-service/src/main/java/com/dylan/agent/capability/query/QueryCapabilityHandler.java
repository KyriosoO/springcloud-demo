package com.dylan.agent.capability.query;

import org.springframework.stereotype.Component;

import com.dylan.agent.adapter.QueryableAdapterRegistry;
import com.dylan.agent.adapter.api.AdapterQueryResult;
import com.dylan.agent.adapter.api.AgentAdapterException;
import com.dylan.agent.adapter.api.QueryableAdapter;
import com.dylan.agent.api.enums.AgentIntent;
import com.dylan.agent.api.response.AgentQueryResult;
import com.dylan.agent.capability.AgentCapabilityHandler;
import com.dylan.agent.capability.CapabilityExecutionContext;
import com.dylan.agent.capability.CapabilityExecutionResult;
import com.dylan.agent.api.capability.AgentCapabilityRiskLevel;
import com.dylan.agent.capability.CapabilityValidationContext;
import com.dylan.agent.capability.model.ValidatedQueryPlan;
import com.dylan.agent.exception.AgentQueryException;
import com.dylan.agent.result.AgentResultProcessor;
import com.dylan.agent.security.AgentPermissionService;

/** QUERY 意图的能力处理器。validate() 委托 QueryPlanValidator，execute() 依次执行：权限校验 → Adapter 查找 → 查询执行 → 结果处理 → 消息构建 → 上下文持久化。Adapter 异常包装为 AgentQueryException。 */
@Component
public class QueryCapabilityHandler
        implements AgentCapabilityHandler<ValidatedQueryPlan> {

    private final QueryPlanValidator queryPlanValidator;
    private final AgentPermissionService permissionService;
    private final QueryableAdapterRegistry adapterRegistry;
    private final AgentResultProcessor resultProcessor;

    public QueryCapabilityHandler(
            QueryPlanValidator queryPlanValidator,
            AgentPermissionService permissionService,
            QueryableAdapterRegistry adapterRegistry,
            AgentResultProcessor resultProcessor) {
        this.queryPlanValidator = queryPlanValidator;
        this.permissionService = permissionService;
        this.adapterRegistry = adapterRegistry;
        this.resultProcessor = resultProcessor;
    }

    @Override
    public AgentIntent intent() {
        return AgentIntent.QUERY;
    }

    @Override
    public AgentCapabilityRiskLevel riskLevel() {
        return AgentCapabilityRiskLevel.READ_ONLY;
    }

    @Override
    public ValidatedQueryPlan validate(CapabilityValidationContext context) {
        return queryPlanValidator.validate(context);
    }

    @Override
    public CapabilityExecutionResult execute(
            CapabilityExecutionContext context,
            ValidatedQueryPlan plan) {

        permissionService.checkQuery(
                context.userContext(),
                plan.domain(),
                plan.query());

        QueryableAdapter adapter =
                adapterRegistry.getRequired(plan.domain());

        AdapterQueryResult rawResult;
        try {
            rawResult = adapter.query(plan.query());
        } catch (AgentAdapterException e) {
            throw new AgentQueryException(e.getSafeMessage(), e);
        }

        AgentQueryResult safeResult = resultProcessor.process(
                rawResult,
                plan.query(),
                context.userContext(),
                plan.domain());

        String message = QueryMessages.buildSuccessMessage(safeResult);

        return CapabilityExecutionResult.queryResult(
                message,
                QueryParameterMapper.toQueryParameters(plan),
                safeResult,
                QueryRuntimeContextFactory.toRuntimeQueryContext(
                        context.turnId(),
                        plan));
    }
}
