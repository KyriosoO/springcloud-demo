package com.dylan.baseline.agent.security.policy.admin;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import com.dylan.baseline.agent.security.policy.StoredAgentSecurityPolicy;
import com.dylan.baseline.agent.security.policy.admin.SecurityChangeApprovalEvidencePort.ApprovalVerificationRequest;
import com.dylan.baseline.agent.security.policy.admin.SecurityChangeApprovalEvidencePort.VerifiedApprovalEvidence;
import com.dylan.baseline.agent.security.policy.admin.SecurityPolicyAdministrationRepository.ActivationResult;
import com.dylan.baseline.agent.security.policy.admin.SecurityPolicyAdministrationRepository.PreparedActivation;
import com.dylan.baseline.agent.security.policy.admin.SecurityPolicyAdministrationRepository.StoredPolicyVersion;
import com.dylan.baseline.agent.security.policy.admin.SecurityPolicyAdministrationService.ActivationCommand;
import com.dylan.baseline.agent.security.policy.admin.SecurityPolicyAdministrationService.AuthenticatedActor;
import com.dylan.baseline.agent.security.policy.admin.SecurityPolicyAdministrationService.ChangeClass;
import com.dylan.baseline.agent.security.policy.admin.SecurityPolicyAdministrationService.Operation;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.time.Clock;
import java.time.Instant;
import java.time.ZoneOffset;
import java.util.HashMap;
import java.util.Map;
import java.util.Optional;
import org.junit.jupiter.api.Test;

class SecurityPolicyAdministrationServiceTest {

    private static final Instant NOW = Instant.parse("2026-07-22T08:00:00Z");
    private static final String ACTOR = "a".repeat(64);
    private static final String APPROVER = "b".repeat(64);
    private static final String EVIDENCE = "e".repeat(64);
    private final AuthFieldPolicyPayloadValidator validator =
            new AuthFieldPolicyPayloadValidator(new ObjectMapper());

    @Test
    void createsInitialPolicyOnlyAfterIndependentBoundApproval() {
        InMemoryRepository repository = new InMemoryRepository();
        SecurityPolicyAdministrationService service = service(repository, this::approve);
        ActivationCommand command = createCommand("policy-v1", payload("name"), ChangeClass.INITIAL, 0);

        ActivationResult result = service.activate(command);

        assertThat(result.policyVersion()).isEqualTo("policy-v1");
        assertThat(result.policyEpoch()).isEqualTo(1);
        assertThat(repository.active).isNotNull();
        assertThat(repository.lastActivation.approvalEvidenceDigest()).isEqualTo(EVIDENCE);
    }

    @Test
    void unavailableOrNonIndependentApprovalFailsClosedWithoutWrite() {
        InMemoryRepository repository = new InMemoryRepository();
        ActivationCommand command = createCommand("policy-v1", payload("name"), ChangeClass.INITIAL, 0);

        assertThatThrownBy(() -> service(repository, new FailClosedSecurityChangeApprovalEvidencePort())
                .activate(command))
                .isInstanceOfSatisfying(PolicyAdministrationException.class,
                        ex -> assertThat(ex.code()).isEqualTo("SECURITY_POLICY_APPROVAL_UNAVAILABLE"));

        SecurityChangeApprovalEvidencePort sameActor = request -> new VerifiedApprovalEvidence(
                request.approvalRef(), EVIDENCE, request.operation(), request.fromPolicyDigest(), request.toPolicyDigest(),
                request.changeClass(), request.expectedStateVersion(), ACTOR, NOW.plusSeconds(60));
        assertThatThrownBy(() -> service(repository, sameActor).activate(command))
                .isInstanceOfSatisfying(PolicyAdministrationException.class,
                        ex -> assertThat(ex.code()).isEqualTo("SECURITY_POLICY_APPROVAL_INVALID"));

        SecurityChangeApprovalEvidencePort wrongOperation = request -> new VerifiedApprovalEvidence(
                request.approvalRef(), EVIDENCE, Operation.ROLLBACK.name(), request.fromPolicyDigest(),
                request.toPolicyDigest(), request.changeClass(), request.expectedStateVersion(),
                APPROVER, NOW.plusSeconds(60));
        assertThatThrownBy(() -> service(repository, wrongOperation).activate(command))
                .isInstanceOfSatisfying(PolicyAdministrationException.class,
                        ex -> assertThat(ex.code()).isEqualTo("SECURITY_POLICY_APPROVAL_INVALID"));
        assertThat(repository.active).isNull();
    }

    @Test
    void recomputesExpansionAndRejectsCallerMisclassificationBeforeWrite() {
        InMemoryRepository repository = new InMemoryRepository();
        service(repository, this::approve).activate(
                createCommand("policy-v1", payload("name"), ChangeClass.INITIAL, 0));
        String expanded = payload("name", "email");
        String digest = validator.validate(AuthFieldPolicyPayloadValidator.SCHEMA_VERSION, expanded).digest();
        ActivationCommand misclassified = new ActivationCommand(
                Operation.CREATE_AND_ACTIVATE, "policy-v2", AuthFieldPolicyPayloadValidator.SCHEMA_VERSION,
                expanded, digest, ChangeClass.TIGHTENING, 1, "approval-2", actor(), "corr-2");

        assertThatThrownBy(() -> service(repository, this::approve).activate(misclassified))
                .isInstanceOfSatisfying(PolicyAdministrationException.class,
                        ex -> assertThat(ex.code()).isEqualTo("SECURITY_POLICY_CHANGE_CLASS_MISMATCH"));
        assertThat(repository.versions).doesNotContainKey("policy-v2");
        assertThat(repository.active.policyVersion()).isEqualTo("policy-v1");
    }

    @Test
    void staleStateAndCanonicalDigestMismatchFailBeforeApprovalOrWrite() {
        InMemoryRepository repository = new InMemoryRepository();
        service(repository, this::approve).activate(
                createCommand("policy-v1", payload("name"), ChangeClass.INITIAL, 0));

        assertThatThrownBy(() -> service(repository, request -> {
                    throw new AssertionError("approval must not be called");
                }).activate(createCommand("policy-v2", payload("name"), ChangeClass.TIGHTENING, 0)))
                .isInstanceOfSatisfying(PolicyAdministrationException.class,
                        ex -> assertThat(ex.code()).isEqualTo("SECURITY_POLICY_CONFLICT"));

        ActivationCommand badDigest = new ActivationCommand(
                Operation.CREATE_AND_ACTIVATE, "policy-v2", AuthFieldPolicyPayloadValidator.SCHEMA_VERSION,
                payload("name"), "f".repeat(64), ChangeClass.TIGHTENING, 1,
                "approval-2", actor(), "corr-2");
        assertThatThrownBy(() -> service(repository, this::approve).activate(badDigest))
                .isInstanceOfSatisfying(PolicyAdministrationException.class,
                        ex -> assertThat(ex.code()).isEqualTo("SECURITY_POLICY_PAYLOAD_INVALID"));
        assertThat(repository.versions).hasSize(1);
    }

    @Test
    void alreadyActiveVersionCannotAdvanceEpochAsANoOp() {
        InMemoryRepository repository = new InMemoryRepository();
        service(repository, this::approve).activate(
                createCommand("policy-v1", payload("name"), ChangeClass.INITIAL, 0));
        ActivationCommand noOp = new ActivationCommand(
                Operation.ACTIVATE_EXISTING, "policy-v1", null, null, repository.active.policyDigest(),
                ChangeClass.TIGHTENING, 1, "approval-2", actor(), "corr-2");

        assertThatThrownBy(() -> service(repository, request -> {
                    throw new AssertionError("approval must not be called");
                }).activate(noOp))
                .isInstanceOfSatisfying(PolicyAdministrationException.class,
                        ex -> assertThat(ex.code()).isEqualTo("SECURITY_POLICY_NO_CHANGE"));
        assertThat(repository.active.policyEpoch()).isEqualTo(1);
    }

    @Test
    void auditFailureUsesStableAuditUnavailableCode() {
        InMemoryRepository repository = new InMemoryRepository();
        repository.auditUnavailable = true;

        assertThatThrownBy(() -> service(repository, this::approve).activate(
                createCommand("policy-v1", payload("name"), ChangeClass.INITIAL, 0)))
                .isInstanceOfSatisfying(PolicyAdministrationException.class,
                        ex -> assertThat(ex.code()).isEqualTo("SECURITY_AUDIT_UNAVAILABLE"));
    }

    private SecurityPolicyAdministrationService service(
            InMemoryRepository repository, SecurityChangeApprovalEvidencePort approvalPort) {
        return new SecurityPolicyAdministrationService(
                repository, approvalPort, validator, Clock.fixed(NOW, ZoneOffset.UTC));
    }

    private VerifiedApprovalEvidence approve(ApprovalVerificationRequest request) {
        return new VerifiedApprovalEvidence(
                request.approvalRef(), EVIDENCE, request.operation(), request.fromPolicyDigest(), request.toPolicyDigest(),
                request.changeClass(), request.expectedStateVersion(), APPROVER, NOW.plusSeconds(60));
    }

    private ActivationCommand createCommand(
            String version, String payload, ChangeClass changeClass, long expectedStateVersion) {
        String digest = validator.validate(AuthFieldPolicyPayloadValidator.SCHEMA_VERSION, payload).digest();
        return new ActivationCommand(
                Operation.CREATE_AND_ACTIVATE, version, AuthFieldPolicyPayloadValidator.SCHEMA_VERSION,
                payload, digest, changeClass, expectedStateVersion, "approval-1", actor(), "corr-1");
    }

    private static AuthenticatedActor actor() {
        return new AuthenticatedActor("SERVICE", ACTOR, true);
    }

    private static String payload(String... fields) {
        return """
                {"fieldPolicies":{"agent-viewer":{
                  "filterableFields":{"employee":%s},
                  "displayableFields":{"employee":%s},
                  "allowedOperators":{},"allowedFunctions":{}}}}
                """.formatted(jsonArray(fields), jsonArray(fields));
    }

    private static String jsonArray(String[] values) {
        return java.util.Arrays.stream(values)
                .map(value -> "\"" + value + "\"")
                .collect(java.util.stream.Collectors.joining(",", "[", "]"));
    }

    private static final class InMemoryRepository implements SecurityPolicyAdministrationRepository {
        private final Map<String, StoredPolicyVersion> versions = new HashMap<>();
        private StoredAgentSecurityPolicy active;
        private PreparedActivation lastActivation;
        private boolean auditUnavailable;

        @Override
        public Optional<StoredPolicyVersion> findVersion(String policyVersion) {
            return Optional.ofNullable(versions.get(policyVersion));
        }

        @Override
        public Optional<StoredAgentSecurityPolicy> findActive() {
            return Optional.ofNullable(active);
        }

        @Override
        public ActivationResult activateAtomically(PreparedActivation activation) {
            if (auditUnavailable) {
                throw new AuditUnavailableException("audit down");
            }
            long actual = active == null ? 0 : active.stateVersion();
            if (actual != activation.expectedStateVersion()) {
                throw new WriteConflictException("stale");
            }
            if (activation.createVersion() && versions.putIfAbsent(
                    activation.target().policyVersion(), activation.target()) != null) {
                throw new WriteConflictException("duplicate version");
            }
            long epoch = active == null ? 1 : active.policyEpoch() + 1;
            long state = active == null ? 1 : active.stateVersion() + 1;
            active = new StoredAgentSecurityPolicy(
                    activation.target().policyVersion(), activation.target().schemaVersion(),
                    activation.target().policyPayload(), activation.target().policyDigest(), epoch, state);
            lastActivation = activation;
            return new ActivationResult(active.policyVersion(), active.policyDigest(), epoch, state);
        }
    }
}
