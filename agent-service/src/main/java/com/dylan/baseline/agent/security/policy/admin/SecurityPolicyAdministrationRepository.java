package com.dylan.baseline.agent.security.policy.admin;

import com.dylan.baseline.agent.security.policy.StoredAgentSecurityPolicy;
import java.time.Instant;
import java.util.Optional;

/** 策略版本、active pointer与激活审计的原子持久化端口。 */
public interface SecurityPolicyAdministrationRepository {

    Optional<StoredPolicyVersion> findVersion(String policyVersion);

    Optional<StoredAgentSecurityPolicy> findActive();

    ActivationResult activateAtomically(PreparedActivation activation);

    record StoredPolicyVersion(
            String policyVersion,
            String schemaVersion,
            String policyPayload,
            String policyDigest,
            String changeClass) {
    }

    record PreparedActivation(
            StoredPolicyVersion target,
            boolean createVersion,
            String fromPolicyVersion,
            String fromSchemaVersion,
            String fromPolicyPayload,
            String fromPolicyDigest,
            long expectedStateVersion,
            String approvalRef,
            String approvalEvidenceDigest,
            String actorType,
            String actorRefDigest,
            String correlationId,
            Instant occurredAt) {
    }

    record ActivationResult(String policyVersion, String policyDigest, long policyEpoch, long stateVersion) {
    }

    final class WriteConflictException extends RuntimeException {
        public WriteConflictException(String message) {
            super(message);
        }

        public WriteConflictException(String message, Throwable cause) {
            super(message, cause);
        }
    }

    final class AuditUnavailableException extends RuntimeException {
        public AuditUnavailableException(String message) {
            super(message);
        }

        public AuditUnavailableException(String message, Throwable cause) {
            super(message, cause);
        }
    }
}
