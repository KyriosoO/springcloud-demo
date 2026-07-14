package com.dylan.agent.capability.document.governance.provider;

import com.dylan.agent.adapter.api.document.provider.DocumentProviderActivationSnapshot;
import com.dylan.agent.adapter.api.operation.CapabilityOperationType;
import com.dylan.agent.capability.document.governance.management.*;
import com.dylan.agent.capability.document.governance.validation.*;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.transaction.annotation.Transactional;

import java.nio.ByteBuffer;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.sql.Timestamp;
import java.time.Clock;
import java.time.Instant;
import java.util.*;

public final class DocumentProviderManagementService {
    private final JdbcTemplate jdbc; private final Clock clock;
    private final JdbcDocumentValidationReportRepository reports;
    private final DocumentReleaseGateEvaluator gates;
    private final DocumentProviderActivationCoordinator coordinator;
    private final DocumentApprovalEvidencePort approvals;
    private final DocumentProviderConsumerCoveragePort coverage;

    public DocumentProviderManagementService(JdbcTemplate jdbc,Clock clock,
            JdbcDocumentValidationReportRepository reports,DocumentReleaseGateEvaluator gates,
            DocumentProviderActivationCoordinator coordinator,DocumentApprovalEvidencePort approvals,
            DocumentProviderConsumerCoveragePort coverage){
        this.jdbc=jdbc;this.clock=clock;this.reports=reports;this.gates=gates;
        this.coordinator=coordinator;this.approvals=approvals;this.coverage=coverage;
    }

    @Transactional
    public DocumentGovernanceChangeResponse activate(DocumentProviderActivateRequest request,DocumentManagementAuthorizationContext authorization){
        authorization.require(DocumentManagementScope.PROVIDER_ACTIVATE);requireDeadline(request.deadline());
        var report=reports.findPassedProviderById(request.validationReportId(),request.operationType(),clock.instant())
                .orElseThrow(()->new IllegalStateException("current PASSED provider validation report required"));
        String current=currentDigest(request.operationType());requireExpected(current,request.expectedCurrentSnapshotDigest());
        String unit=DocumentProviderActivationCoordinator.unitKeyDigest(request.operationType());
        String authorizationDigest=canonical("DMA-REQUEST-1","PROVIDER_ACTIVATE",request.idempotencyKey(),unit,current,
                report.binding().canonicalDigest(),report.reportId(),request.deadline().toString());
        var approval=approvals.requireApproval(new DocumentApprovalVerificationRequest(
                DocumentManagementOperation.PROVIDER_ACTIVATE,unit,current,report.binding().canonicalDigest(),
                Optional.of(report.reportId()),authorizationDigest,request.deadline()),authorization);
        requireStandard(authorization,approval);
        var gate=gates.evaluate("PROVIDER_OPERATION",unit,report.binding().canonicalDigest(),
                report.reportCanonicalDigest(),report.subjectDigest(),approval.evidenceRef());
        PreparedChange prepared=prepare(request.idempotencyKey(),authorizationDigest,"ACTIVATE",unit,current,
                report.binding().canonicalDigest(),gate.canonicalDigest(),authorization,approval,request.deadline(),null);
        if(!prepared.created())return existingResponse(prepared.changeId(),unit);
        String changeId=prepared.changeId();
        DocumentProviderActivationSnapshot snapshot=coordinator.activate(report.binding(),changeId,changeId,gate,
                coverage.requiredConsumers(request.operationType()));
        return verifying(changeId,unit,current,report.binding().canonicalDigest(),snapshot.canonicalDigest());
    }

    @Transactional
    public DocumentGovernanceChangeResponse rollback(DocumentProviderRollbackRequest request,DocumentManagementAuthorizationContext authorization){
        authorization.require(DocumentManagementScope.PROVIDER_ROLLBACK);requireDeadline(request.deadline());
        var report=reports.findPassedProviderById(request.validationReportId(),request.operationType(),clock.instant())
                .orElseThrow(()->new IllegalStateException("current PASSED provider rollback report required"));
        requireRollbackHistory(request.operationType(),request.relatedChangeId(),report.binding().canonicalDigest());
        String current=currentDigest(request.operationType());requireExpected(current,request.expectedCurrentSnapshotDigest());
        String unit=DocumentProviderActivationCoordinator.unitKeyDigest(request.operationType());
        String authorizationDigest=canonical("DMA-REQUEST-1","PROVIDER_ROLLBACK",request.idempotencyKey(),unit,current,
                report.binding().canonicalDigest(),report.reportId(),request.relatedChangeId(),request.deadline().toString());
        var approval=approvals.requireApproval(new DocumentApprovalVerificationRequest(DocumentManagementOperation.PROVIDER_ROLLBACK,
                unit,current,report.binding().canonicalDigest(),Optional.of(report.reportId()),authorizationDigest,request.deadline()),authorization);
        requireStandard(authorization,approval);
        var gate=gates.evaluate("PROVIDER_OPERATION",unit,report.binding().canonicalDigest(),report.reportCanonicalDigest(),
                report.subjectDigest(),approval.evidenceRef());
        PreparedChange prepared=prepare(request.idempotencyKey(),authorizationDigest,"ROLLBACK",unit,current,
                report.binding().canonicalDigest(),gate.canonicalDigest(),authorization,approval,request.deadline(),request.relatedChangeId());
        if(!prepared.created())return existingResponse(prepared.changeId(),unit);
        String changeId=prepared.changeId();
        DocumentProviderActivationSnapshot snapshot=coordinator.activate(report.binding(),changeId,changeId,gate,
                coverage.requiredConsumers(request.operationType()));
        return verifying(changeId,unit,current,report.binding().canonicalDigest(),snapshot.canonicalDigest());
    }

    @Transactional
    public DocumentGovernanceChangeResponse deactivate(DocumentProviderDeactivateRequest request,DocumentManagementAuthorizationContext authorization){
        authorization.require(DocumentManagementScope.PROVIDER_DEACTIVATE);requireDeadline(request.deadline());
        String current=currentDigest(request.operationType());requireExpected(current,request.expectedCurrentSnapshotDigest());
        String unit=DocumentProviderActivationCoordinator.unitKeyDigest(request.operationType());
        String target=canonical("PROVIDER-INACTIVE-1",request.operationType().value());
        String authorizationDigest=canonical("DMA-REQUEST-1","PROVIDER_DEACTIVATE",request.idempotencyKey(),unit,current,target,
                request.reasonCode().name(),request.deadline().toString());
        var approval=approvals.requireApproval(new DocumentApprovalVerificationRequest(DocumentManagementOperation.PROVIDER_DEACTIVATE,
                unit,current,target,Optional.empty(),authorizationDigest,request.deadline()),authorization);
        requireStandard(authorization,approval);
        PreparedChange prepared=prepare(request.idempotencyKey(),authorizationDigest,"DEACTIVATE",unit,current,target,
                approval.canonicalDigest(),authorization,approval,request.deadline(),null);
        if(!prepared.created())return existingResponse(prepared.changeId(),unit);
        String changeId=prepared.changeId();
        DocumentProviderActivationSnapshot snapshot=coordinator.deactivate(request.operationType(),changeId,changeId,request.reasonCode().name());
        return verifying(changeId,unit,current,target,snapshot.canonicalDigest());
    }

    public DocumentGovernanceChangeResponse status(String changeId,DocumentManagementAuthorizationContext authorization){
        authorization.require(DocumentManagementScope.GOVERNANCE_READ);
        return existingResponse(changeId,requireUnit(changeId));
    }

    @Transactional
    public DocumentGovernanceChangeResponse reconcile(String changeId,DocumentReconcileRequest request,
            DocumentManagementAuthorizationContext authorization){
        authorization.require(DocumentManagementScope.GOVERNANCE_RECONCILE);requireDeadline(request.deadline());
        var history=jdbc.query("SELECT h.operation_type,h.snapshot_digest,c.deadline,c.status FROM document_provider_activation_history h JOIN document_governance_change c ON c.change_id=h.change_id WHERE h.change_id=? AND c.unit_type='PROVIDER_OPERATION' ORDER BY h.created_at DESC LIMIT 1",
                (rs,row)->new ReconcileAuthority(CapabilityOperationType.of(rs.getString(1)),rs.getString(2),rs.getTimestamp(3).toInstant(),DocumentGovernanceChangeStatus.valueOf(rs.getString(4))),changeId);
        if(history.size()!=1)throw new IllegalStateException("provider governance reconcile authority unavailable");
        ReconcileAuthority authority=history.getFirst();
        if(!Set.of(DocumentGovernanceChangeStatus.VERIFYING,DocumentGovernanceChangeStatus.UNKNOWN,
                DocumentGovernanceChangeStatus.FROZEN).contains(authority.status()))throw new IllegalStateException("provider change is not reconcilable");
        String current=currentDigest(authority.operationType());
        DocumentGovernanceChangeStatus resolved;
        if(!current.equals(authority.snapshotDigest()))resolved=DocumentGovernanceChangeStatus.FROZEN;
        else if(coverageObserved(authority.operationType(),authority.snapshotDigest()))resolved=DocumentGovernanceChangeStatus.SUCCEEDED;
        else resolved=clock.instant().isBefore(authority.changeDeadline())?DocumentGovernanceChangeStatus.VERIFYING:DocumentGovernanceChangeStatus.FROZEN;
        jdbc.update("UPDATE document_governance_change SET status=?,current_state_digest=?,row_version=row_version+1,updated_at=? WHERE change_id=? AND status IN ('VERIFYING','UNKNOWN','FROZEN')",
                resolved.name(),current,Timestamp.from(clock.instant()),changeId);
        appendEvent(changeId,"PROVIDER_CHANGE_RECONCILED",resolved.name(),authority.operationType().value(),current);
        return existingResponse(changeId,DocumentProviderActivationCoordinator.unitKeyDigest(authority.operationType()));
    }

    private PreparedChange prepare(String idempotencyKey,String requestDigest,String kind,String unit,String expected,String target,
                           String gateRef,DocumentManagementAuthorizationContext authorization,DocumentApprovalEvidence approval,
                           Instant deadline,String related){
        String idem=canonical("IDEMPOTENCY-1",idempotencyKey);
        var existing=jdbc.query("SELECT change_id,request_digest FROM document_governance_change WHERE unit_type='PROVIDER_OPERATION' AND unit_key_digest=? AND idempotency_digest=? FOR UPDATE",
                (rs,row)->Map.entry(rs.getString(1),rs.getString(2)),unit,idem);
        if(!existing.isEmpty()){if(!existing.getFirst().getValue().equals(requestDigest))throw new IllegalStateException("provider idempotency conflict");return new PreparedChange(existing.getFirst().getKey(),false);}
        String changeId=UUID.randomUUID().toString();Instant now=clock.instant();
        jdbc.update("INSERT INTO document_governance_change(change_id,unit_type,unit_key_digest,idempotency_digest,request_digest,change_kind,expected_state_digest,target_state_digest,gate_evidence_ref,actor_safe_ref,approval_safe_ref,authentication_evidence_digest,status,related_change_id,deadline,row_version,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,0,?,?)",
                changeId,"PROVIDER_OPERATION",unit,idem,requestDigest,kind,expected,target,gateRef,
                authorization.actorSafeRef(),approval.approverSafeRef(),authorization.authenticationEvidenceDigest(),
                "PREPARED",related,Timestamp.from(deadline),Timestamp.from(now),Timestamp.from(now));
        appendEvent(changeId,"PROVIDER_CHANGE_PREPARED","PREPARED",unit,target);
        return new PreparedChange(changeId,true);
    }

    private DocumentGovernanceChangeResponse verifying(String changeId,String unit,String expected,String target,String actual){
        jdbc.update("UPDATE document_governance_change SET status='VERIFYING',current_state_digest=?,row_version=row_version+1,updated_at=? WHERE change_id=? AND status IN ('PREPARED','VERIFYING')",
                actual,Timestamp.from(clock.instant()),changeId);
        appendEvent(changeId,"PROVIDER_CHANGE_VERIFYING","VERIFYING",unit,actual);
        return new DocumentGovernanceChangeResponse(changeId,DocumentRolloutUnitType.PROVIDER_OPERATION,unit,
                DocumentGovernanceChangeStatus.VERIFYING,expected,target,Optional.of(actual),clock.instant());
    }

    private DocumentGovernanceChangeResponse existingResponse(String changeId,String unit){
        var rows=jdbc.query("SELECT status,expected_state_digest,target_state_digest,current_state_digest,updated_at FROM document_governance_change WHERE change_id=?",
                (rs,row)->new DocumentGovernanceChangeResponse(changeId,DocumentRolloutUnitType.PROVIDER_OPERATION,unit,
                        DocumentGovernanceChangeStatus.valueOf(rs.getString(1)),rs.getString(2),rs.getString(3),
                        Optional.ofNullable(rs.getString(4)),rs.getTimestamp(5).toInstant()),changeId);
        if(rows.size()!=1)throw new IllegalStateException("provider governance change unavailable");
        return rows.getFirst();
    }

    private String currentDigest(CapabilityOperationType operationType){
        List<String> rows=jdbc.query("SELECT snapshot_digest FROM document_provider_activation WHERE operation_type=?",
                (rs,row)->rs.getString(1),operationType.value());
        if(rows.size()>1)throw new IllegalStateException("duplicate provider activation current row");
        return rows.isEmpty()?canonical("PROVIDER-MISSING-1",operationType.value()):rows.getFirst();
    }
    private String requireUnit(String changeId){
        var rows=jdbc.query("SELECT unit_key_digest FROM document_governance_change WHERE change_id=? AND unit_type='PROVIDER_OPERATION'",(rs,row)->rs.getString(1),changeId);
        if(rows.size()!=1)throw new IllegalStateException("provider governance change unavailable");return rows.getFirst();
    }
    private void requireRollbackHistory(CapabilityOperationType operationType,String relatedChangeId,String targetBindingDigest){
        var rows=jdbc.query("SELECT previous.provider_binding_digest FROM document_provider_activation_history related JOIN document_provider_activation_history previous ON previous.operation_type=related.operation_type AND previous.state='ACTIVE' AND previous.created_at<related.created_at WHERE related.change_id=? AND related.operation_type=? ORDER BY previous.created_at DESC LIMIT 1",
                (rs,row)->rs.getString(1),relatedChangeId,operationType.value());
        if(rows.size()!=1||!targetBindingDigest.equals(rows.getFirst()))throw new IllegalStateException("provider rollback target is not the related change previous binding");
    }
    private boolean coverageObserved(CapabilityOperationType operationType,String activationDigest){
        Map<String,String> required=coverage.requiredConsumers(operationType);if(required==null||required.isEmpty())return false;
        for(var entry:required.entrySet()){
            Integer count=jdbc.queryForObject("SELECT COUNT(*) FROM document_provider_activation_ack WHERE consumer_id=? AND operation_type=? AND deployment_digest=? AND activation_digest=? AND observed_at>?",Integer.class,
                    entry.getKey(),operationType.value(),entry.getValue(),activationDigest,Timestamp.from(clock.instant().minusSeconds(300)));
            if(count==null||count!=1)return false;
        }
        return true;
    }
    private void appendEvent(String changeId,String eventType,String status,String safeRef,String digest){
        jdbc.update("INSERT INTO document_governance_event(event_id,change_id,event_type,status,safe_refs,reason_code,digest_prefixes,occurred_at,delivery_status,delivery_attempt,row_version) VALUES(?,?,?,?,?,?,?,?,?,?,0)",
                UUID.randomUUID().toString(),changeId,eventType,status,safeRef,status,digest.substring(0,12),Timestamp.from(clock.instant()),"PENDING",0);
    }
    private void requireExpected(String actual,String expected){if(!actual.equals(expected))throw new IllegalStateException("provider expected current snapshot mismatch");}
    private void requireDeadline(Instant deadline){if(!clock.instant().isBefore(deadline))throw new IllegalStateException("provider management deadline reached");}
    private void requireStandard(DocumentManagementAuthorizationContext authorization,DocumentApprovalEvidence approval){if(authorization.actorSafeRef().equals(approval.approverSafeRef())||approval.kind()!=DocumentApprovalKind.STANDARD_APPROVAL||!clock.instant().isBefore(approval.validUntil()))throw new SecurityException("valid separated standard approval required");}
    private static String canonical(String... values){try{MessageDigest digest=MessageDigest.getInstance("SHA-256");for(String value:values){byte[] bytes=value.getBytes(StandardCharsets.UTF_8);digest.update(ByteBuffer.allocate(4).putInt(bytes.length).array());digest.update(bytes);}return HexFormat.of().formatHex(digest.digest());}catch(Exception ex){throw new IllegalStateException(ex);}}
    private record PreparedChange(String changeId,boolean created){}
    private record ReconcileAuthority(CapabilityOperationType operationType,String snapshotDigest,Instant changeDeadline,DocumentGovernanceChangeStatus status){}
}
