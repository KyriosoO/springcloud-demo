package com.dylan.baseline.agent.security.policy.internal;

import com.dylan.baseline.agent.security.policy.StoredAgentSecurityPolicy;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Select;

@Mapper
public interface AgentSecurityPolicyRecordMapper {

    @Select("""
            SELECT v.policy_version AS policyVersion,
                   v.schema_version AS schemaVersion,
                   CAST(v.policy_payload AS CHAR) AS policyPayload,
                   v.policy_digest AS policyDigest,
                   a.policy_epoch AS policyEpoch,
                   a.state_version AS stateVersion
              FROM agent_security_policy_active a
              JOIN agent_security_policy_version v
                ON v.policy_version = a.policy_version
             WHERE a.scope = 'GLOBAL'
            """)
    StoredAgentSecurityPolicy selectActive();
}
