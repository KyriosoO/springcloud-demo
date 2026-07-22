package com.dylan.baseline.agent.security.policy.internal;

import com.dylan.baseline.agent.security.policy.AgentSecurityPolicyRepository;
import com.dylan.baseline.agent.security.policy.StoredAgentSecurityPolicy;
import com.dylan.baseline.agent.security.policy.admin.SecurityPolicyAdministrationRepository;
import java.util.UUID;
import java.util.Optional;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.dao.DataAccessException;
import org.springframework.dao.DataIntegrityViolationException;
import org.springframework.stereotype.Repository;
import org.springframework.transaction.support.TransactionTemplate;

/** 仅在显式启用持久化且外部提供DataSource/MyBatis配置时注册。 */
@Repository
@ConditionalOnProperty(
        prefix = "agent.security.policy",
        name = "persistence-enabled",
        havingValue = "true")
public final class MyBatisAgentSecurityPolicyRepository
        implements AgentSecurityPolicyRepository, SecurityPolicyAdministrationRepository {

    private final AgentSecurityPolicyRecordMapper mapper;
    private final TransactionTemplate transactionTemplate;

    public MyBatisAgentSecurityPolicyRepository(
            AgentSecurityPolicyRecordMapper mapper, TransactionTemplate transactionTemplate) {
        this.mapper = mapper;
        this.transactionTemplate = transactionTemplate;
    }

    @Override
    public Optional<StoredAgentSecurityPolicy> findActive() {
        return Optional.ofNullable(mapper.selectActive());
    }

    @Override
    public Optional<StoredPolicyVersion> findVersion(String policyVersion) {
        return Optional.ofNullable(mapper.selectVersion(policyVersion));
    }

    @Override
    public ActivationResult activateAtomically(PreparedActivation activation) {
        try {
            return transactionTemplate.execute(status -> activateInTransaction(activation));
        } catch (DataIntegrityViolationException ex) {
            throw new WriteConflictException("policy version or active epoch conflicts", ex);
        }
    }

    private ActivationResult activateInTransaction(PreparedActivation activation) {
        StoredAgentSecurityPolicy locked = mapper.selectActiveForUpdate();
        long actualStateVersion = locked == null ? 0 : locked.stateVersion();
        String actualDigest = locked == null ? null : locked.policyDigest();
        if (actualStateVersion != activation.expectedStateVersion()
                || !java.util.Objects.equals(actualDigest, activation.fromPolicyDigest())
                || !java.util.Objects.equals(
                        locked == null ? null : locked.schemaVersion(), activation.fromSchemaVersion())
                || !java.util.Objects.equals(
                        locked == null ? null : locked.policyPayload(), activation.fromPolicyPayload())) {
            throw new WriteConflictException("active policy state changed");
        }
        if (activation.createVersion()) {
            requireOne(mapper.insertVersion(
                    activation.target(), activation.approvalRef(), activation.actorRefDigest(), activation.occurredAt()));
        } else {
            StoredPolicyVersion stored = mapper.selectVersion(activation.target().policyVersion());
            if (stored == null
                    || !stored.policyDigest().equals(activation.target().policyDigest())
                    || !stored.schemaVersion().equals(activation.target().schemaVersion())
                    || !stored.policyPayload().equals(activation.target().policyPayload())) {
                throw new WriteConflictException("target policy version changed or disappeared");
            }
        }

        long newEpoch;
        long newStateVersion;
        if (locked == null) {
            requireOne(mapper.insertInitialActive(
                    activation.target().policyVersion(), activation.target().policyDigest(),
                    activation.occurredAt(), activation.actorRefDigest()));
            newEpoch = 1;
            newStateVersion = 1;
        } else {
            requireOne(mapper.casUpdateActive(
                    activation.target().policyVersion(), activation.target().policyDigest(),
                    activation.expectedStateVersion(), activation.fromPolicyDigest(),
                    activation.occurredAt(), activation.actorRefDigest()));
            newEpoch = locked.policyEpoch() + 1;
            newStateVersion = locked.stateVersion() + 1;
        }
        try {
            int auditRows = mapper.insertActivationAudit(
                    UUID.randomUUID().toString(), activation.fromPolicyVersion(),
                    activation.target().policyVersion(), activation.target().policyDigest(), newEpoch,
                    activation.target().changeClass(), activation.approvalRef(), activation.approvalEvidenceDigest(),
                    activation.actorType(), activation.actorRefDigest(),
                    activation.correlationId(), activation.occurredAt());
            if (auditRows != 1) {
                throw new AuditUnavailableException("activation audit affected an unexpected row count");
            }
        } catch (DataAccessException ex) {
            throw new AuditUnavailableException("activation audit write failed", ex);
        }
        return new ActivationResult(
                activation.target().policyVersion(), activation.target().policyDigest(), newEpoch, newStateVersion);
    }

    private static void requireOne(int affectedRows) {
        if (affectedRows != 1) {
            throw new WriteConflictException("atomic policy write affected an unexpected row count");
        }
    }
}
