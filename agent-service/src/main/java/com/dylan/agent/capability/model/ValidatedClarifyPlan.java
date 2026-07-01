package com.dylan.agent.capability.model;

import com.dylan.agent.api.enums.AgentIntent;

/** CLARIFY 意图的校验通过 plan。封装反问文本和可选 domain。 */
public final class ValidatedClarifyPlan implements ValidatedCapabilityPlan {

    private final String domain;
    private final String question;

    public ValidatedClarifyPlan(String domain, String question) {
        this.domain = domain;
        this.question = question;
    }

    @Override
    public AgentIntent intent() {
        return AgentIntent.CLARIFY;
    }

    @Override
    public String domain() {
        return domain;
    }

    public String question() {
        return question;
    }

    @Override
    public String auditSummary() {
        return domain == null
                ? "CLARIFY"
                : "CLARIFY domain=" + domain;
    }
}
