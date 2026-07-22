package com.dylan.baseline.agent.security.policy;

import java.util.Optional;

/** 当前active策略的业务只读端口；写入只允许经SecurityPolicyAdministrationService。 */
public interface AgentSecurityPolicyRepository {

    Optional<StoredAgentSecurityPolicy> findActive();
}
