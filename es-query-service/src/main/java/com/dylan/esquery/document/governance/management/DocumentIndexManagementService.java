package com.dylan.esquery.document.governance.management;

import com.dylan.esquery.api.model.DocumentCorpusKeyDto;
import com.dylan.esquery.document.DocumentCorpusCatalog;
import com.dylan.esquery.document.governance.DocumentIndexRolloutCoordinator;
import com.dylan.esquery.document.governance.JdbcDocumentIndexValidationReportRepository;
import com.dylan.esquery.service.EsIndexAliasService;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;

import java.io.IOException;
import java.nio.ByteBuffer;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.time.Clock;
import java.time.Instant;
import java.util.HexFormat;
import java.util.List;
import java.util.Optional;

/** operation-specific management authority；caller不能提交physical index、actor或approval。 */
@Service
public final class DocumentIndexManagementService {
    private final JdbcTemplate jdbc; private final Clock clock; private final DocumentCorpusCatalog catalog;
    private final EsIndexAliasService aliases; private final JdbcDocumentIndexValidationReportRepository reports;
    private final DocumentIndexRolloutCoordinator coordinator; private final DocumentApprovalEvidencePort approvals;

    public DocumentIndexManagementService(JdbcTemplate jdbc,Clock clock,DocumentCorpusCatalog catalog,
            EsIndexAliasService aliases,JdbcDocumentIndexValidationReportRepository reports,
            DocumentIndexRolloutCoordinator coordinator,DocumentApprovalEvidencePort approvals){
        this.jdbc=jdbc;this.clock=clock;this.catalog=catalog;this.aliases=aliases;this.reports=reports;
        this.coordinator=coordinator;this.approvals=approvals;
    }

    public DocumentGovernanceChangeResponse activate(DocumentIndexActivateRequest request,DocumentManagementAuthorizationContext authorization){
        authorization.require(DocumentManagementScope.INDEX_ACTIVATE);
        return change(request.idempotencyKey(),request.corpusKey(),request.validationReportId(),
                request.expectedCurrentBindingDigest(),null,request.deadline(),request.emergencyGateEvidence(),
                DocumentManagementOperation.INDEX_ACTIVATE,"ACTIVATE",authorization);
    }

    public DocumentGovernanceChangeResponse rollback(DocumentIndexRollbackRequest request,DocumentManagementAuthorizationContext authorization){
        authorization.require(DocumentManagementScope.INDEX_ROLLBACK);
        return change(request.idempotencyKey(),request.corpusKey(),request.validationReportId(),
                request.expectedCurrentBindingDigest(),request.relatedChangeId(),request.deadline(),
                request.emergencyGateEvidence(),DocumentManagementOperation.INDEX_ROLLBACK,"ROLLBACK",authorization);
    }

    public DocumentGovernanceChangeResponse status(String changeId,DocumentManagementAuthorizationContext authorization){
        authorization.require(DocumentManagementScope.READ);return readChange(changeId);
    }

    public DocumentGovernanceChangeResponse reconcile(String changeId,DocumentReconcileRequest request,
            DocumentManagementAuthorizationContext authorization){
        authorization.require(DocumentManagementScope.RECONCILE);requireDeadline(request.deadline());
        ChangeRow row=readRow(changeId);
        if(!List.of(DocumentGovernanceChangeStatus.UNKNOWN,DocumentGovernanceChangeStatus.FROZEN,
                DocumentGovernanceChangeStatus.PREPARED,DocumentGovernanceChangeStatus.EXECUTING).contains(row.status()))
            throw new IllegalStateException("index change is not reconcilable");
        String safeCorpus=jdbc.queryForObject("SELECT safe_refs FROM document_governance_event WHERE change_id=? ORDER BY occurred_at ASC LIMIT 1",String.class,changeId);
        if(safeCorpus==null||safeCorpus.indexOf(':')<1)throw new IllegalStateException("index change corpus reference unavailable");
        String[] parts=safeCorpus.split(":",2);DocumentCorpusKeyDto corpus=new DocumentCorpusKeyDto(parts[0],parts[1]);
        var report=reports.requireByTarget(row.unitKeyDigest(),row.targetStateDigest());
        var result=coordinator.reconcile(changeId,catalog.require(corpus).readAlias(),report.targetIndex());
        return readChange(result.changeId());
    }

    private DocumentGovernanceChangeResponse change(String idempotencyKey,DocumentCorpusKeyDto corpus,String reportId,
            String expectedCurrent,String relatedChangeId,Instant deadline,
            com.dylan.esquery.document.governance.emergency.DocumentEmergencyGateEvidence emergency,
            DocumentManagementOperation operation,String kind,DocumentManagementAuthorizationContext authorization){
        requireDeadline(deadline);
        var report=reports.requirePassed(reportId,corpus,clock.instant());
        String unit=JdbcDocumentIndexValidationReportRepository.corpusKeyDigest(corpus);
        String actual=digestTargets(readActual(catalog.require(corpus).readAlias()));
        if(!actual.equals(expectedCurrent))throw new IllegalStateException("index expected current binding mismatch");
        if("ROLLBACK".equals(kind))requireRollbackHistory(relatedChangeId,unit,report.targetIndex());
        String authorizationDigest=canonical("DMA-REQUEST-1",operation.name(),idempotencyKey,unit,expectedCurrent,
                report.targetBinding().canonicalDigest(),report.reportId(),relatedChangeId==null?"":relatedChangeId,deadline.toString());
        DocumentApprovalEvidence approval=approvals.requireApproval(new DocumentApprovalVerificationRequest(operation,unit,
                expectedCurrent,report.targetBinding().canonicalDigest(),Optional.of(report.reportId()),authorizationDigest,deadline),authorization);
        requireApproval(authorization,approval);
        Instant issued=clock.instant();Instant expires=issued.plusSeconds(60).isBefore(report.expiresAt())?issued.plusSeconds(60):report.expiresAt();
        String gateDigest=canonical("DRG-1","INDEX_RELEASE",unit,report.targetBinding().canonicalDigest(),
                report.reportDigest(),approval.evidenceRef(),issued.toString(),expires.toString());
        var gate=new DocumentIndexRolloutCoordinator.ReleaseGateEvidence("INDEX_RELEASE",unit,
                report.targetBinding().canonicalDigest(),report.reportDigest(),approval.evidenceRef(),issued,expires,gateDigest);
        String idempotencyDigest=canonical("IDEMPOTENCY-1",idempotencyKey);
        String requestDigest=canonical("DGC-REQUEST-1",authorizationDigest,approval.canonicalDigest(),emergency.canonicalDigest());
        var result=coordinator.activate(new DocumentIndexRolloutCoordinator.AuthorizedIndexChange(corpus,reportId,
                expectedCurrent,gate,emergency,idempotencyDigest,requestDigest,kind,authorization.actorSafeRef(),
                approval.approverSafeRef(),authorization.authenticationEvidenceDigest(),relatedChangeId,deadline));
        return readChange(result.changeId());
    }

    private void requireRollbackHistory(String relatedChangeId,String unit,String targetIndex){
        DocumentIndexActivateRequest.requireText(relatedChangeId,"relatedChangeId");
        List<String> expected=jdbc.query("SELECT expected_state_digest FROM document_governance_change WHERE change_id=? AND unit_type='INDEX_TARGET' AND unit_key_digest=? AND status='SUCCEEDED'",
                (rs,row)->rs.getString(1),relatedChangeId,unit);
        if(expected.size()!=1||!expected.getFirst().equals(digestTargets(List.of(targetIndex))))
            throw new IllegalStateException("index rollback target is not the related change previous target");
    }

    private List<String> readActual(String alias){try{return aliases.readCurrent(alias).targets();}catch(IOException ex){throw new IllegalStateException("index actual state unavailable");}}
    private void requireDeadline(Instant deadline){if(deadline==null||!clock.instant().isBefore(deadline))throw new IllegalStateException("index management deadline reached");}
    private void requireApproval(DocumentManagementAuthorizationContext authorization,DocumentApprovalEvidence approval){
        if(approval==null||approval.evidenceRef()==null||approval.evidenceRef().isBlank()||approval.approverSafeRef()==null
                ||authorization.actorSafeRef().equals(approval.approverSafeRef())||approval.validUntil()==null
                ||!clock.instant().isBefore(approval.validUntil())||approval.canonicalDigest()==null
                ||!approval.canonicalDigest().matches("[0-9a-f]{64}"))throw new SecurityException("valid separated standard approval required");
    }

    private DocumentGovernanceChangeResponse readChange(String changeId){ChangeRow row=readRow(changeId);return new DocumentGovernanceChangeResponse(changeId,DocumentRolloutUnitType.INDEX_TARGET,row.unitKeyDigest(),row.status(),row.expectedStateDigest(),row.targetStateDigest(),Optional.ofNullable(row.currentStateDigest()),row.updatedAt());}
    private ChangeRow readRow(String changeId){
        List<ChangeRow> rows=jdbc.query("SELECT unit_key_digest,status,expected_state_digest,target_state_digest,current_state_digest,updated_at FROM document_governance_change WHERE change_id=? AND unit_type='INDEX_TARGET'",
                (rs,row)->new ChangeRow(rs.getString(1),DocumentGovernanceChangeStatus.valueOf(rs.getString(2)),rs.getString(3),rs.getString(4),rs.getString(5),rs.getTimestamp(6).toInstant()),changeId);
        if(rows.size()!=1)throw new IllegalStateException("index governance change unavailable");return rows.getFirst();
    }
    private static String digestTargets(List<String> targets){return sha256(String.join("\u001f",targets.stream().sorted().toList()).getBytes(StandardCharsets.UTF_8));}
    private static String canonical(String... values){try{MessageDigest d=MessageDigest.getInstance("SHA-256");for(String value:values){byte[] bytes=value.getBytes(StandardCharsets.UTF_8);d.update(ByteBuffer.allocate(4).putInt(bytes.length).array());d.update(bytes);}return HexFormat.of().formatHex(d.digest());}catch(Exception ex){throw new IllegalStateException(ex);}}
    private static String sha256(byte[] value){try{return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(value));}catch(Exception ex){throw new IllegalStateException(ex);}}
    private record ChangeRow(String unitKeyDigest,DocumentGovernanceChangeStatus status,String expectedStateDigest,String targetStateDigest,String currentStateDigest,Instant updatedAt){}
}
