package com.dylan.baseline.agent.security.policy.admin;

import com.dylan.baseline.agent.security.policy.StoredAgentSecurityPolicy;
import com.dylan.baseline.agent.security.policy.admin.AuthFieldPolicyPayloadValidator.ValidatedPolicy;
import com.dylan.baseline.agent.security.policy.admin.SecurityChangeApprovalEvidencePort.ApprovalVerificationRequest;
import com.dylan.baseline.agent.security.policy.admin.SecurityChangeApprovalEvidencePort.VerifiedApprovalEvidence;
import com.dylan.baseline.agent.security.policy.admin.SecurityPolicyAdministrationRepository.ActivationResult;
import com.dylan.baseline.agent.security.policy.admin.SecurityPolicyAdministrationRepository.AuditUnavailableException;
import com.dylan.baseline.agent.security.policy.admin.SecurityPolicyAdministrationRepository.PreparedActivation;
import com.dylan.baseline.agent.security.policy.admin.SecurityPolicyAdministrationRepository.StoredPolicyVersion;
import com.dylan.baseline.agent.security.policy.admin.SecurityPolicyAdministrationRepository.WriteConflictException;
import java.time.Clock;
import java.time.Instant;
import java.util.Objects;
import java.util.Optional;
import java.util.Set;

/** 策略创建、激活与回滚的唯一应用服务；不暴露业务流量入口。 */
public final class SecurityPolicyAdministrationService {

    private final SecurityPolicyAdministrationRepository repository;
    private final SecurityChangeApprovalEvidencePort approvalEvidencePort;
    private final AuthFieldPolicyPayloadValidator payloadValidator;
    private final Clock clock;

    public SecurityPolicyAdministrationService(
            SecurityPolicyAdministrationRepository repository,
            SecurityChangeApprovalEvidencePort approvalEvidencePort,
            AuthFieldPolicyPayloadValidator payloadValidator,
            Clock clock) {
        this.repository = repository;
        this.approvalEvidencePort = approvalEvidencePort;
        this.payloadValidator = payloadValidator;
        this.clock = clock;
    }

    public ActivationResult activate(ActivationCommand command) {
        requireAuthenticatedActor(command.actor());
        Optional<StoredAgentSecurityPolicy> current = repository.findActive();
        verifyExpectedState(command, current);

        StoredPolicyVersion target;
        ValidatedPolicy targetPolicy;
        boolean createVersion = command.policyPayload() != null;
        if (createVersion) {
            targetPolicy = payloadValidator.validate(command.schemaVersion(), command.policyPayload());
            requireEqual(command.targetPolicyDigest(), targetPolicy.digest(), "target digest");
            target = new StoredPolicyVersion(
                    command.policyVersion(), command.schemaVersion(), targetPolicy.canonicalJson(),
                    targetPolicy.digest(), command.expectedChangeClass().name());
        } else {
            target = repository.findVersion(command.policyVersion()).orElseThrow(() ->
                    new PolicyAdministrationException("SECURITY_POLICY_NOT_FOUND", "target policy version not found"));
            targetPolicy = payloadValidator.validate(target.schemaVersion(), target.policyPayload());
            requireEqual(target.policyDigest(), targetPolicy.digest(), "stored policy digest");
            requireEqual(command.targetPolicyDigest(), target.policyDigest(), "target digest");
        }

        ChangeClass actualChangeClass = classify(current, targetPolicy.atomicGrants());
        if (current.map(StoredAgentSecurityPolicy::policyDigest).filter(target.policyDigest()::equals).isPresent()) {
            throw new PolicyAdministrationException(
                    "SECURITY_POLICY_NO_CHANGE", "target policy is already active");
        }
        if (actualChangeClass != command.expectedChangeClass()) {
            throw new PolicyAdministrationException(
                    "SECURITY_POLICY_CHANGE_CLASS_MISMATCH",
                    "expected change class does not match current-to-target diff");
        }

        String fromDigest = current.map(StoredAgentSecurityPolicy::policyDigest).orElse(null);
        ApprovalVerificationRequest request = new ApprovalVerificationRequest(
                command.approvalRef(), command.operation().name(), fromDigest, target.policyDigest(),
                actualChangeClass.name(), command.expectedStateVersion(), command.actor().actorRefDigest());
        VerifiedApprovalEvidence approval = approvalEvidencePort.verify(request);
        Instant occurredAt = clock.instant();
        verifyApproval(request, approval, command.actor(), occurredAt);

        StoredPolicyVersion activationTarget = new StoredPolicyVersion(
                target.policyVersion(), target.schemaVersion(), target.policyPayload(),
                target.policyDigest(), actualChangeClass.name());
        PreparedActivation prepared = new PreparedActivation(
                activationTarget, createVersion, current.map(StoredAgentSecurityPolicy::policyVersion).orElse(null),
                current.map(StoredAgentSecurityPolicy::schemaVersion).orElse(null),
                current.map(StoredAgentSecurityPolicy::policyPayload).orElse(null),
                fromDigest, command.expectedStateVersion(), approval.approvalRef(), approval.evidenceDigest(),
                command.actor().actorType(), command.actor().actorRefDigest(), command.correlationId(), occurredAt);
        try {
            return repository.activateAtomically(prepared);
        } catch (AuditUnavailableException ex) {
            throw new PolicyAdministrationException(
                    "SECURITY_AUDIT_UNAVAILABLE", "policy activation audit is unavailable", ex);
        } catch (WriteConflictException ex) {
            throw new PolicyAdministrationException(
                    "SECURITY_POLICY_CONFLICT", "active policy changed concurrently", ex);
        }
    }

    private ChangeClass classify(Optional<StoredAgentSecurityPolicy> current, Set<String> targetGrants) {
        if (current.isEmpty()) {
            return ChangeClass.INITIAL;
        }
        StoredAgentSecurityPolicy active = current.orElseThrow();
        ValidatedPolicy currentPolicy = payloadValidator.validate(active.schemaVersion(), active.policyPayload());
        requireEqual(active.policyDigest(), currentPolicy.digest(), "active policy digest");
        Set<String> currentGrants = currentPolicy.atomicGrants();
        if (currentGrants.equals(targetGrants) || currentGrants.containsAll(targetGrants)) {
            return ChangeClass.TIGHTENING;
        }
        if (targetGrants.containsAll(currentGrants)) {
            return ChangeClass.EXPANSION;
        }
        return ChangeClass.MIXED;
    }

    private static void verifyExpectedState(
            ActivationCommand command, Optional<StoredAgentSecurityPolicy> current) {
        long actual = current.map(StoredAgentSecurityPolicy::stateVersion).orElse(0L);
        if (actual != command.expectedStateVersion()) {
            throw new PolicyAdministrationException("SECURITY_POLICY_CONFLICT", "stateVersion is stale");
        }
    }

    private static void verifyApproval(
            ApprovalVerificationRequest request,
            VerifiedApprovalEvidence approval,
            AuthenticatedActor actor,
            Instant now) {
        if (approval == null
                || !Objects.equals(request.approvalRef(), approval.approvalRef())
                || !isDigest(approval.evidenceDigest())
                || !Objects.equals(request.operation(), approval.operation())
                || !Objects.equals(request.fromPolicyDigest(), approval.fromPolicyDigest())
                || !Objects.equals(request.toPolicyDigest(), approval.toPolicyDigest())
                || !Objects.equals(request.changeClass(), approval.changeClass())
                || request.expectedStateVersion() != approval.expectedStateVersion()
                || !isDigest(approval.approverRefDigest())
                || approval.validUntil() == null
                || !approval.validUntil().isAfter(now)
                || actor.actorRefDigest().equals(approval.approverRefDigest())) {
            throw new PolicyAdministrationException(
                    "SECURITY_POLICY_APPROVAL_INVALID", "approval evidence is missing, stale, mismatched or not independent");
        }
    }

    private static void requireAuthenticatedActor(AuthenticatedActor actor) {
        if (actor == null || !actor.authenticated() || actor.actorType() == null
                || actor.actorType().isBlank() || actor.actorType().length() > 32
                || !isDigest(actor.actorRefDigest())) {
            throw new PolicyAdministrationException(
                    "SECURITY_POLICY_ACTOR_INVALID", "authenticated management actor is required");
        }
    }

    private static void requireEqual(String expected, String actual, String label) {
        if (!Objects.equals(expected, actual)) {
            throw new PolicyAdministrationException(
                    "SECURITY_POLICY_PAYLOAD_INVALID", label + " does not match canonical payload");
        }
    }

    private static boolean isDigest(String value) {
        return value != null && value.matches("[0-9a-f]{64}");
    }

    public enum Operation {
        CREATE_AND_ACTIVATE,
        ACTIVATE_EXISTING,
        ROLLBACK
    }

    public enum ChangeClass {
        INITIAL,
        TIGHTENING,
        EXPANSION,
        MIXED
    }

    public record AuthenticatedActor(String actorType, String actorRefDigest, boolean authenticated) {
    }

    public record ActivationCommand(
            Operation operation,
            String policyVersion,
            String schemaVersion,
            String policyPayload,
            String targetPolicyDigest,
            ChangeClass expectedChangeClass,
            long expectedStateVersion,
            String approvalRef,
            AuthenticatedActor actor,
            String correlationId) {

        public ActivationCommand {
            Objects.requireNonNull(operation, "operation");
            requireText(policyVersion, "policyVersion", 128);
            requireText(targetPolicyDigest, "targetPolicyDigest");
            Objects.requireNonNull(expectedChangeClass, "expectedChangeClass");
            requireText(approvalRef, "approvalRef", 128);
            requireText(correlationId, "correlationId", 128);
            if (expectedStateVersion < 0) {
                throw new IllegalArgumentException("expectedStateVersion must be non-negative");
            }
            if (operation == Operation.CREATE_AND_ACTIVATE) {
                requireText(schemaVersion, "schemaVersion", 32);
                requireText(policyPayload, "policyPayload");
            } else if (policyPayload != null || schemaVersion != null) {
                throw new IllegalArgumentException("existing-version operations must not supply payload or schema");
            }
        }

        private static void requireText(String value, String name) {
            if (value == null || value.isBlank()) {
                throw new IllegalArgumentException(name + " must not be blank");
            }
        }

        private static void requireText(String value, String name, int maxLength) {
            requireText(value, name);
            if (value.length() > maxLength) {
                throw new IllegalArgumentException(name + " exceeds " + maxLength + " characters");
            }
        }
    }
}
