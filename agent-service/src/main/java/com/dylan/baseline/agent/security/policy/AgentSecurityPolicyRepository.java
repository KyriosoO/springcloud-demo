package com.dylan.baseline.agent.security.policy;

import java.util.Optional;

/** 当前active策略的只读端口；激活控制面不属于本次迁移实施。 */
public interface AgentSecurityPolicyRepository {

    Optional<StoredAgentSecurityPolicy> findActive();
}
