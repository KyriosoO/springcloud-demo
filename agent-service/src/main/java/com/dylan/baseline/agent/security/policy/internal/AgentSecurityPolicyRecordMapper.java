package com.dylan.baseline.agent.security.policy.internal;

import com.dylan.baseline.agent.security.policy.StoredAgentSecurityPolicy;
import com.dylan.baseline.agent.security.policy.admin.SecurityPolicyAdministrationRepository.StoredPolicyVersion;
import java.time.Instant;
import org.apache.ibatis.annotations.Insert;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.Select;
import org.apache.ibatis.annotations.Update;

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
               AND v.policy_digest = a.policy_digest
             WHERE a.scope = 'GLOBAL'
            """)
    StoredAgentSecurityPolicy selectActive();

    @Select("""
            SELECT v.policy_version AS policyVersion,
                   v.schema_version AS schemaVersion,
                   CAST(v.policy_payload AS CHAR) AS policyPayload,
                   v.policy_digest AS policyDigest,
                   v.change_class AS changeClass
              FROM agent_security_policy_version v
             WHERE v.policy_version = #{policyVersion}
            """)
    StoredPolicyVersion selectVersion(@Param("policyVersion") String policyVersion);

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
               AND v.policy_digest = a.policy_digest
             WHERE a.scope = 'GLOBAL'
             FOR UPDATE
            """)
    StoredAgentSecurityPolicy selectActiveForUpdate();

    @Insert("""
            INSERT INTO agent_security_policy_version
                (policy_version, schema_version, policy_payload, policy_digest, change_class,
                 approval_ref, created_by_ref_digest, created_at)
            VALUES
                (#{target.policyVersion}, #{target.schemaVersion}, #{target.policyPayload},
                 #{target.policyDigest}, #{target.changeClass}, #{approvalRef}, #{actorRefDigest}, #{occurredAt})
            """)
    int insertVersion(
            @Param("target") StoredPolicyVersion target,
            @Param("approvalRef") String approvalRef,
            @Param("actorRefDigest") String actorRefDigest,
            @Param("occurredAt") Instant occurredAt);

    @Insert("""
            INSERT INTO agent_security_policy_active
                (scope, policy_version, policy_digest, policy_epoch, state_version,
                 activated_at, activated_by_ref_digest)
            VALUES ('GLOBAL', #{policyVersion}, #{policyDigest}, 1, 1, #{occurredAt}, #{actorRefDigest})
            """)
    int insertInitialActive(
            @Param("policyVersion") String policyVersion,
            @Param("policyDigest") String policyDigest,
            @Param("occurredAt") Instant occurredAt,
            @Param("actorRefDigest") String actorRefDigest);

    @Update("""
            UPDATE agent_security_policy_active
               SET policy_version = #{policyVersion},
                   policy_digest = #{policyDigest},
                   policy_epoch = policy_epoch + 1,
                   state_version = state_version + 1,
                   activated_at = #{occurredAt},
                   activated_by_ref_digest = #{actorRefDigest}
             WHERE scope = 'GLOBAL'
               AND state_version = #{expectedStateVersion}
               AND policy_digest = #{expectedFromDigest}
            """)
    int casUpdateActive(
            @Param("policyVersion") String policyVersion,
            @Param("policyDigest") String policyDigest,
            @Param("expectedStateVersion") long expectedStateVersion,
            @Param("expectedFromDigest") String expectedFromDigest,
            @Param("occurredAt") Instant occurredAt,
            @Param("actorRefDigest") String actorRefDigest);

    @Insert("""
            INSERT INTO agent_security_policy_activation_audit
                (activation_id, scope, from_policy_version, to_policy_version, to_policy_digest,
                 new_policy_epoch, change_class, approval_ref, approval_evidence_digest,
                 actor_type, actor_ref_digest, correlation_id, occurred_at)
            VALUES
                (#{activationId}, 'GLOBAL', #{fromPolicyVersion}, #{toPolicyVersion}, #{toPolicyDigest},
                 #{newPolicyEpoch}, #{changeClass}, #{approvalRef}, #{approvalEvidenceDigest},
                 #{actorType}, #{actorRefDigest}, #{correlationId}, #{occurredAt})
            """)
    int insertActivationAudit(
            @Param("activationId") String activationId,
            @Param("fromPolicyVersion") String fromPolicyVersion,
            @Param("toPolicyVersion") String toPolicyVersion,
            @Param("toPolicyDigest") String toPolicyDigest,
            @Param("newPolicyEpoch") long newPolicyEpoch,
            @Param("changeClass") String changeClass,
            @Param("approvalRef") String approvalRef,
            @Param("approvalEvidenceDigest") String approvalEvidenceDigest,
            @Param("actorType") String actorType,
            @Param("actorRefDigest") String actorRefDigest,
            @Param("correlationId") String correlationId,
            @Param("occurredAt") Instant occurredAt);
}
