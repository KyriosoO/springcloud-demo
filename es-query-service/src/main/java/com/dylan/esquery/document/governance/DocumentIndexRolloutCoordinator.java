package com.dylan.esquery.document.governance;

import com.dylan.esquery.api.model.DocumentCorpusKeyDto;
import com.dylan.esquery.document.DocumentCorpusCatalog;
import com.dylan.esquery.document.AuthorizedReleaseAttestationCommand;
import com.dylan.esquery.document.ReleaseAttestationTechnicalPort;
import com.dylan.esquery.service.EsIndexAliasService;
import com.dylan.esquery.document.governance.emergency.DocumentEmergencyGateEvidence;
import com.dylan.esquery.document.governance.emergency.DocumentEmergencyGateEvidenceVerifier;
import com.dylan.esquery.document.governance.emergency.DocumentEmergencyGateTargetBinding;
import com.dylan.esquery.document.governance.emergency.DocumentEmergencyRolloutBinding;
import com.dylan.esquery.document.governance.emergency.DocumentEmergencyTargetType;
import com.dylan.esquery.document.governance.emergency.DocumentEmergencyGateVerificationCode;
import com.dylan.esquery.document.governance.emergency.DocumentEmergencyGateExpectedBindings;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.support.TransactionTemplate;

import java.io.IOException;
import java.sql.Timestamp;
import java.time.Clock;
import java.time.Instant;
import java.time.Duration;
import java.util.List;
import java.util.UUID;
import java.nio.ByteBuffer;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.HexFormat;

/** 07 index rollout authority；01 alias service 只执行一次已授权 CAS 技术动作。 */
@Service
public final class DocumentIndexRolloutCoordinator {
    private static final Duration CHANGE_LEASE = Duration.ofSeconds(30);
    private final DocumentCorpusCatalog catalog;
    private final EsIndexAliasService aliasService;
    private final JdbcTemplate jdbc;
    private final ReleaseAttestationTechnicalPort attestations;
    private final TransactionTemplate transaction;
    private final Clock clock;
    private final DocumentEmergencyGateEvidenceVerifier emergencyEvidenceVerifier;
    private final JdbcDocumentIndexValidationReportRepository reports;

    public DocumentIndexRolloutCoordinator(DocumentCorpusCatalog catalog, EsIndexAliasService aliasService,
                                           JdbcTemplate jdbc, ReleaseAttestationTechnicalPort attestations,
                                           TransactionTemplate transaction, Clock clock,
                                           DocumentEmergencyGateEvidenceVerifier emergencyEvidenceVerifier,
                                           JdbcDocumentIndexValidationReportRepository reports) {
        this.catalog = catalog;
        this.aliasService = aliasService;
        this.jdbc = jdbc;
        this.attestations = attestations;
        this.transaction = transaction;
        this.clock = clock;
        this.emergencyEvidenceVerifier = emergencyEvidenceVerifier;
        this.reports = reports;
    }

    public ChangeResult activate(AuthorizedIndexChange command) {
        var corpus = catalog.require(command.corpusKey());
        var report = requireCurrentReport(command);
        List<String> expectedTargets = readActual(corpus.readAlias());
        validate(command, report, expectedTargets);
        requireCurrentEmergencyEvidence(command, report, expectedTargets);
        Intent intent = transaction.execute(status -> createIntent(command, report, expectedTargets));
        if (!"PREPARED".equals(intent.status())) {
            return new ChangeResult(intent.changeId(), intent.status(), readActual(corpus.readAlias()));
        }
        String changeId = intent.changeId();
        transaction.executeWithoutResult(status -> startExecution(changeId));
        try {
            var attestation = attestations.attach(new AuthorizedReleaseAttestationCommand(report.targetIndex(),
                    report.subjectDigest(), report.reportId(), report.reportDigest(), command.deadline()));
            if (!attestation.attestationDigest().equals(report.targetBinding().attestationDigest())) {
                throw new IllegalArgumentException("index target attestation binding mismatch");
            }
            aliasService.compareAndSwitch(new EsIndexAliasService.AuthorizedAliasChangeCommand(
                    changeId, command.corpusKey(), corpus.readAlias(), expectedTargets, report.targetIndex(),
                    report.subjectDigest(), report.reportId(), attestation.attestationDigest(),
                    command.gateEvidence().canonicalDigest(), command.deadline()));
        } catch (IOException | RuntimeException ignored) {
            // intent 已持久化；下面必须以 actual post-read 决定成功、失败安全或 UNKNOWN。
        }
        var actual = readActual(corpus.readAlias());
        String finalStatus = actual.equals(List.of(report.targetIndex())) ? "SUCCEEDED"
                : !actual.contains("__UNKNOWN__") && digestTargets(actual).equals(command.expectedCurrentBindingDigest())
                ? "FAILED_SAFE" : "UNKNOWN";
        String resolved = finalStatus;
        transaction.executeWithoutResult(status -> complete(changeId, command, report, resolved, actual));
        return new ChangeResult(changeId, resolved, actual);
    }

    public ChangeResult reconcile(String changeId, String alias, String targetIndex, String expectedStateDigest) {
        List<String> actual = readActual(alias);
        String status = actual.equals(List.of(targetIndex)) ? "SUCCEEDED"
                : !actual.contains("__UNKNOWN__") && digestTargets(actual).equals(expectedStateDigest)
                ? "FAILED_SAFE" : "FROZEN";
        int updated = jdbc.update("UPDATE document_governance_change SET status=?,current_state_digest=?,lease_owner=NULL,lease_expires_at=NULL,row_version=row_version+1,updated_at=? WHERE change_id=? AND (status IN ('UNKNOWN','FROZEN') OR (status IN ('PREPARED','EXECUTING') AND lease_expires_at<?))",
                status, digestTargets(actual), Timestamp.from(clock.instant()), changeId, Timestamp.from(clock.instant()));
        if (updated != 1) throw new IllegalStateException("index change is not reconcilable");
        return new ChangeResult(changeId, status, actual);
    }

    private void validate(AuthorizedIndexChange command, JdbcDocumentIndexValidationReportRepository.IndexReportAuthority report, List<String> expectedTargets) {
        if (!clock.instant().isBefore(command.deadline())) throw new IllegalStateException("index change deadline reached");
        if (expectedTargets.size() > 1 || expectedTargets.contains("__UNKNOWN__")) throw new IllegalArgumentException("read alias must have one readable state");
        if (!digestTargets(expectedTargets).equals(command.expectedCurrentBindingDigest())) {
            throw new IllegalArgumentException("index expected current binding mismatch");
        }
        if (!report.targetBinding().canonicalDigest().equals(canonical("ITB-1", report.targetBinding().schemaVersion(),
                report.targetBinding().contentDigest(), report.targetBinding().manifestDigest(),
                report.targetBinding().attestationDigest()))) {
            throw new IllegalArgumentException("index target binding canonical digest mismatch");
        }
        ReleaseGateEvidence gate = command.gateEvidence();
        if (gate == null || !"INDEX_TARGET".equals(gate.unitType())
                || !gate.unitKeyDigest().equals(unitKeyDigest(command))
                || !gate.expectedStateDigest().equals(command.expectedCurrentBindingDigest())
                || !gate.exactTargetStateDigest().equals(report.targetBinding().canonicalDigest())
                || !gate.reportCanonicalDigest().equals(report.reportDigest())
                || !gate.approvalSafeRef().equals(command.approvalSafeRef())
                || !clock.instant().isBefore(gate.expiresAt())
                || gate.issuedAt().isAfter(clock.instant())
                || !gate.canonicalDigest().equals(canonical("DRG-1", gate.unitType(), gate.unitKeyDigest(),
                gate.expectedStateDigest(), gate.exactTargetStateDigest(), gate.reportCanonicalDigest(), gate.approvalSafeRef(),
                gate.issuedAt().toString(), gate.expiresAt().toString()))) {
            throw new IllegalArgumentException("current index release gate evidence required");
        }
        requireText(command.actorSafeRef(), "actorSafeRef");
        requireText(command.approvalSafeRef(), "approvalSafeRef");
        requireDigest(command.authenticationEvidenceDigest(), "authenticationEvidenceDigest");
        if (command.actorSafeRef().equals(command.approvalSafeRef())) {
            throw new IllegalArgumentException("index change requires separated approval identity");
        }
        if (!List.of("ACTIVATE", "ROLLBACK").contains(command.changeKind())) {
            throw new IllegalArgumentException("unsupported index change kind");
        }
    }

    private JdbcDocumentIndexValidationReportRepository.IndexReportAuthority requireCurrentReport(AuthorizedIndexChange command) {
        return reports.requirePassed(command.validationReportId(), command.corpusKey(), clock.instant());
    }

    private void requireCurrentEmergencyEvidence(AuthorizedIndexChange command,JdbcDocumentIndexValidationReportRepository.IndexReportAuthority report,List<String> expectedTargets) {
        DocumentEmergencyRolloutBinding expectedRollout = new DocumentEmergencyRolloutBinding(
                "INDEX_TARGET", unitKeyDigest(command),
                digestTargets(expectedTargets), report.targetBinding().canonicalDigest(), report.reportId());
        List<DocumentEmergencyGateTargetBinding> expectedEmergencyTargets = DocumentEmergencyGateExpectedBindings.forIndex(
                command.corpusKey(), report.targetBinding().canonicalDigest());
        var verification = emergencyEvidenceVerifier.verify(
                command.emergencyGateEvidence(), expectedRollout, expectedEmergencyTargets, clock.instant());
        if (verification.code() != DocumentEmergencyGateVerificationCode.VERIFIED) {
            throw new IllegalArgumentException("current verified emergency gate evidence required");
        }
    }

    private Intent createIntent(AuthorizedIndexChange command, JdbcDocumentIndexValidationReportRepository.IndexReportAuthority report, List<String> expectedTargets) {
        List<ExistingIntent> existing = jdbc.query("SELECT change_id,request_digest,status FROM document_governance_change WHERE unit_type='INDEX_TARGET' AND unit_key_digest=? AND idempotency_digest=?",
                (rs, row) -> new ExistingIntent(rs.getString(1), rs.getString(2), rs.getString(3)),
                unitKeyDigest(command), command.idempotencyDigest());
        if (!existing.isEmpty()) {
            ExistingIntent intent = existing.getFirst();
            if (!intent.requestDigest().equals(command.requestDigest())) {
                throw new IllegalStateException("index change idempotency conflict");
            }
            return new Intent(intent.changeId(), intent.status());
        }
        String changeId = UUID.randomUUID().toString();
        List<ExistingActiveIntent> active = jdbc.query("SELECT change_id,idempotency_digest,request_digest,status FROM document_governance_change WHERE unit_type='INDEX_TARGET' AND unit_key_digest=? AND status IN ('PREPARED','EXECUTING','UNKNOWN','FROZEN') FOR UPDATE",
                (rs, row) -> new ExistingActiveIntent(rs.getString(1), rs.getString(2), rs.getString(3), rs.getString(4)),
                unitKeyDigest(command));
        if (!active.isEmpty()) {
            ExistingActiveIntent current = active.getFirst();
            if (current.idempotencyDigest().equals(command.idempotencyDigest())
                    && current.requestDigest().equals(command.requestDigest())) {
                return new Intent(current.changeId(), current.status());
            }
            throw new IllegalStateException("index rollout unit already has an active change");
        }
        Instant now = clock.instant();
        Instant leaseExpiresAt = now.plus(CHANGE_LEASE).isBefore(command.deadline())
                ? now.plus(CHANGE_LEASE) : command.deadline();
        jdbc.update("INSERT INTO document_governance_change(change_id,unit_type,unit_key_digest,idempotency_digest,request_digest,change_kind,expected_state_digest,target_state_digest,gate_evidence_ref,actor_safe_ref,approval_safe_ref,authentication_evidence_digest,emergency_evidence_id,emergency_evidence_digest,emergency_evidence_key_id,emergency_evidence_key_version,emergency_evidence_verification_code,status,related_change_id,deadline,lease_owner,lease_expires_at,row_version,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,0,?,?)",
                changeId, "INDEX_TARGET", unitKeyDigest(command), command.idempotencyDigest(),
                command.requestDigest(), command.changeKind(), digestTargets(expectedTargets),
                report.targetBinding().canonicalDigest(), command.gateEvidence().canonicalDigest(), command.actorSafeRef(),
                command.approvalSafeRef(), command.authenticationEvidenceDigest(), command.emergencyGateEvidence().evidenceId(),
                command.emergencyGateEvidence().canonicalDigest(), command.emergencyGateEvidence().signature().keyId(),
                command.emergencyGateEvidence().signature().keyVersion(), DocumentEmergencyGateVerificationCode.VERIFIED.name(),
                "PREPARED", command.relatedChangeId(), Timestamp.from(command.deadline()), changeId,
                Timestamp.from(leaseExpiresAt), Timestamp.from(now), Timestamp.from(now));
        appendEvent(changeId, "INDEX_CHANGE_PREPARED", "PREPARED", command, report, "PREPARED");
        return new Intent(changeId, "PREPARED");
    }

    private void startExecution(String changeId) {
        int updated = jdbc.update("UPDATE document_governance_change SET status='EXECUTING',row_version=row_version+1,updated_at=? WHERE change_id=? AND status='PREPARED' AND lease_expires_at>?",
                Timestamp.from(clock.instant()), changeId, Timestamp.from(clock.instant()));
        if (updated != 1) throw new IllegalStateException("index change execution lease unavailable");
    }

    private void complete(String changeId, AuthorizedIndexChange command, JdbcDocumentIndexValidationReportRepository.IndexReportAuthority report, String status, List<String> actual) {
        int updated = jdbc.update("UPDATE document_governance_change SET status=?,current_state_digest=?,lease_owner=NULL,lease_expires_at=NULL,row_version=row_version+1,updated_at=? WHERE change_id=? AND status='EXECUTING'",
                status, digestTargets(actual), Timestamp.from(clock.instant()), changeId);
        if (updated != 1) throw new IllegalStateException("index change completion CAS conflict");
        appendEvent(changeId, "INDEX_CHANGE_COMPLETED", status, command, report, status);
    }

    private void appendEvent(String changeId, String eventType, String status,
                             AuthorizedIndexChange command, JdbcDocumentIndexValidationReportRepository.IndexReportAuthority report, String reasonCode) {
        jdbc.update("INSERT INTO document_governance_event(event_id,change_id,event_type,status,safe_refs,reason_code,digest_prefixes,occurred_at,delivery_status,delivery_attempt,row_version) VALUES(?,?,?,?,?,?,?,?,?,?,0)",
                UUID.randomUUID().toString(), changeId, eventType, status,
                "INDEX_TARGET", reasonCode,
                unitKeyDigest(command).substring(0, 12) + "," + report.subjectDigest().substring(0, 12),
                Timestamp.from(clock.instant()), "PENDING", 0);
    }

    private List<String> readActual(String alias) {
        try { return aliasService.readCurrent(alias).targets(); }
        catch (IOException ex) { return List.of("__UNKNOWN__"); }
    }

    private static String digestTargets(List<String> targets) {
        return sha256(String.join("\u001f", targets.stream().sorted().toList()));
    }
    private static String sha256(String value) {
        try { return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256")
                .digest(value.getBytes(StandardCharsets.UTF_8))); }
        catch (Exception ex) { throw new IllegalStateException(ex); }
    }
    private static String unitKeyDigest(AuthorizedIndexChange command) {
        try { return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256")
                .digest(command.corpusKey().canonicalBytes())); }
        catch (Exception ex) { throw new IllegalStateException(ex); }
    }
    private static String canonical(String... values) {
        try {
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            for (String value : values) {
                byte[] bytes = value.getBytes(StandardCharsets.UTF_8);
                digest.update(ByteBuffer.allocate(4).putInt(bytes.length).array());
                digest.update(bytes);
            }
            return HexFormat.of().formatHex(digest.digest());
        } catch (Exception ex) { throw new IllegalStateException(ex); }
    }
    private static void requireDigest(String value, String name) {
        if (value == null || !value.matches("[0-9a-f]{64}")) throw new IllegalArgumentException(name + " must be SHA-256 hex");
    }
    private static void requireText(String value, String name) {
        if (value == null || value.isBlank()) throw new IllegalArgumentException(name + " must not be blank");
    }

    public record AuthorizedIndexChange(
            DocumentCorpusKeyDto corpusKey, String validationReportId, String expectedCurrentBindingDigest,
            ReleaseGateEvidence gateEvidence,
            DocumentEmergencyGateEvidence emergencyGateEvidence,
            String idempotencyDigest, String requestDigest, String changeKind, String actorSafeRef,
            String approvalSafeRef, String authenticationEvidenceDigest, String relatedChangeId, Instant deadline) {
        public AuthorizedIndexChange {
            requireText(validationReportId,"validationReportId");
            requireDigest(expectedCurrentBindingDigest,"expectedCurrentBindingDigest");
        }
    }
    public record ReleaseGateEvidence(String unitType, String unitKeyDigest, String expectedStateDigest, String exactTargetStateDigest,
                                      String reportCanonicalDigest, String approvalSafeRef,
                                      Instant issuedAt, Instant expiresAt, String canonicalDigest) {
        public ReleaseGateEvidence {
            requireText(unitType, "unitType"); requireDigest(unitKeyDigest, "unitKeyDigest");
            requireDigest(expectedStateDigest, "expectedStateDigest");
            requireDigest(exactTargetStateDigest, "exactTargetStateDigest");
            requireDigest(reportCanonicalDigest, "reportCanonicalDigest"); requireText(approvalSafeRef, "approvalSafeRef");
            if (issuedAt == null || expiresAt == null || !issuedAt.isBefore(expiresAt)) throw new IllegalArgumentException("release gate time range invalid");
            requireDigest(canonicalDigest, "canonicalDigest");
        }
    }
    public record ChangeResult(String changeId, String status, List<String> actualTargets) {
        public ChangeResult { actualTargets = List.copyOf(actualTargets); }
    }
    private record ExistingIntent(String changeId, String requestDigest, String status) {}
    private record ExistingActiveIntent(String changeId, String idempotencyDigest,
                                        String requestDigest, String status) {}
    private record Intent(String changeId, String status) {}
}
