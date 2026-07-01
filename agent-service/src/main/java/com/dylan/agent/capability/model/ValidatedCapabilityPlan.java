package com.dylan.agent.capability.model;

import com.dylan.agent.api.enums.AgentIntent;

/** 校验通过的 capability plan 接口。实现类保证已通过 Java 侧结构校验，可安全执行。 */
public interface ValidatedCapabilityPlan {

    AgentIntent intent();

    String domain();

    String auditSummary();
}
