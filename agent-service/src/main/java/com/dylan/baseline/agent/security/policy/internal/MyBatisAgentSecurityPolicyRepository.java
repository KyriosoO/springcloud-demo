package com.dylan.baseline.agent.security.policy.internal;

import com.dylan.baseline.agent.security.policy.AgentSecurityPolicyRepository;
import com.dylan.baseline.agent.security.policy.StoredAgentSecurityPolicy;
import java.util.Optional;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.stereotype.Repository;

/** 仅在显式启用持久化且外部提供DataSource/MyBatis配置时注册。 */
@Repository
@ConditionalOnProperty(
        prefix = "agent.security.policy",
        name = "persistence-enabled",
        havingValue = "true")
public final class MyBatisAgentSecurityPolicyRepository implements AgentSecurityPolicyRepository {

    private final AgentSecurityPolicyRecordMapper mapper;

    public MyBatisAgentSecurityPolicyRepository(AgentSecurityPolicyRecordMapper mapper) {
        this.mapper = mapper;
    }

    @Override
    public Optional<StoredAgentSecurityPolicy> findActive() {
        return Optional.ofNullable(mapper.selectActive());
    }
}
