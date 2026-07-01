package com.dylan.agent.capability.clarify;

import org.springframework.stereotype.Component;

import com.dylan.agent.api.enums.AgentIntent;
import com.dylan.agent.api.plan.AgentPlan;
import com.dylan.agent.api.plan.ClarifySpec;
import com.dylan.agent.capability.CapabilityValidationContext;
import com.dylan.agent.capability.model.ValidatedClarifyPlan;
import com.dylan.agent.exception.AgentPlanValidationException;
import com.dylan.agent.metadata.domain.internal.DomainCatalogView;

/** CLARIFY plan 校验器。校验 intent 为 CLARIFY、question 1~500 字符、query 为空、domain 非空时存在于配置。 */
@Component
public class ClarifyPlanValidator {

    private final DomainCatalogView domainCatalogView;

    public ClarifyPlanValidator(DomainCatalogView domainCatalogView) {
        this.domainCatalogView = domainCatalogView;
    }

    /** 将 Runtime 原始 CLARIFY plan 校验为 ValidatedClarifyPlan。 */
    public ValidatedClarifyPlan validate(CapabilityValidationContext context) {
        AgentPlan plan = context.planResponse().getPlan();

        if (plan.getIntent() != AgentIntent.CLARIFY) {
            throw new AgentPlanValidationException("Plan intent 必须为 CLARIFY。");
        }

        ClarifySpec clarify = plan.getClarify();
        if (clarify == null) {
            throw new AgentPlanValidationException("CLARIFY Plan 缺少 clarify 字段。");
        }
        if (plan.getQuery() != null) {
            throw new AgentPlanValidationException("CLARIFY Plan 不能同时携带 query。");
        }
        if (plan.getAggregate() != null) {
            throw new AgentPlanValidationException("CLARIFY Plan 不能同时携带 aggregate。");
        }

        String question = clarify.getQuestion();
        if (question == null || question.isBlank() || question.length() > 500) {
            throw new AgentPlanValidationException("CLARIFY question 长度必须在 1～500 之间。");
        }

        String domain = plan.getDomain();
        if (domain != null && !domain.isBlank()) {
            if (!domainCatalogView.containsDomain(domain)) {
                throw new AgentPlanValidationException("不支持的 domain: " + domain);
            }
        }

        return new ValidatedClarifyPlan(domain, question.trim());
    }
}
