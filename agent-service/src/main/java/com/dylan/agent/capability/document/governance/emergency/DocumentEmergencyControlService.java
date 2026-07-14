package com.dylan.agent.capability.document.governance.emergency;

import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.transaction.annotation.Transactional;

import java.sql.Timestamp;
import java.nio.ByteBuffer;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.time.Clock;
import java.time.Instant;
import java.util.HexFormat;
import java.util.List;
import java.util.UUID;
import com.dylan.agent.adapter.api.operation.CapabilityOperationType;
import com.dylan.agent.capability.document.governance.provider.DocumentProviderActivationCoordinator;
import com.dylan.agent.capability.document.governance.management.DocumentApprovalEvidence;
import com.dylan.agent.capability.document.governance.management.DocumentApprovalKind;
import com.dylan.agent.capability.document.governance.management.DocumentManagementAuthorizationContext;
import com.dylan.agent.capability.document.governance.management.DocumentManagementScope;

/** 07 emergency authoritative write；状态、Provider 强制失活与事件在同一 DB 事务提交。 */
public final class DocumentEmergencyControlService {
    private final JdbcTemplate jdbc;
    private final Clock clock;
    private final DocumentProviderActivationCoordinator providerActivations;

    public DocumentEmergencyControlService(JdbcTemplate jdbc, Clock clock,
                                           DocumentProviderActivationCoordinator providerActivations) {
        this.jdbc = jdbc;
        this.clock = clock;
        this.providerActivations = providerActivations;
    }

    @Transactional
    public DocumentEmergencyChangeResponse disable(
            DocumentEmergencyDisableRequest request,
            DocumentManagementAuthorizationContext authorization,
            DocumentApprovalEvidence approval) {
        java.util.Objects.requireNonNull(request,"request must not be null");
        validateAuthorization(authorization,approval,DocumentManagementScope.EMERGENCY_DISABLE,true,request.deadline());
        var target=request.target();
        var binding=DocumentEmergencyGateCanonicalizer.targetBinding(target);
        String digest=binding.targetKeyDigest();
        String requestDigest=canonical("DGC-EMERGENCY-1","DISABLE",target.type(),digest,
                Long.toString(request.expectedRowVersion()),request.reasonCode().name(),request.deadline().toString(),
                authorization.actorSafeRef(),approval.evidenceRef());
        String changeId=prepareChange(request.idempotencyKey(),requestDigest,"DISABLE",digest,
                request.expectedRowVersion(),"ACTIVE",request.deadline(),authorization,approval);
        var current = lock(target.type(), digest);
        if (current != null && "ACTIVE".equals(current.state())) {
            if (changeId.equals(current.activeChangeId())) return response(changeId,binding,current.rowVersion(),DocumentEmergencyControlState.ACTIVE,target);
            throw new IllegalStateException("emergency target already active under another change");
        }
        if ((current == null && request.expectedRowVersion() != -1)
                || (current != null && current.rowVersion() != request.expectedRowVersion())) {
            throw new IllegalStateException("emergency disable expected rowVersion mismatch");
        }
        long nextVersion;
        if (current == null) {
            jdbc.update("INSERT INTO document_emergency_control(target_type,target_key_digest,target_canonical,state,reason_code,active_change_id,cleared_change_id,effective_at,row_version) VALUES(?,?,?,?,?,?,?,?,0)",
                    target.type(), digest, target.key(), "ACTIVE", request.reasonCode().name(), changeId, null,
                    Timestamp.from(clock.instant()));
            nextVersion = 0;
        } else {
            int updated = jdbc.update("UPDATE document_emergency_control SET state='ACTIVE',reason_code=?,active_change_id=?,cleared_change_id=NULL,effective_at=?,row_version=row_version+1 WHERE target_type=? AND target_key_digest=? AND row_version=?",
                    request.reasonCode().name(), changeId, Timestamp.from(clock.instant()), target.type(), digest, current.rowVersion());
            if (updated != 1) throw new IllegalStateException("emergency disable CAS conflict");
            nextVersion = current.rowVersion() + 1;
        }
        CapabilityOperationType providerOperation = affectedProviderOperation(target);
        if (providerOperation != null) {
            providerActivations.deactivateForEmergency(providerOperation,
                    "emergency-" + changeId, changeId, request.reasonCode().name(), target.type() + ":" + digest);
        }
        appendEvent(changeId, "EMERGENCY_DISABLED", "SUCCEEDED", target.type() + ":" + digest, request.reasonCode().name(),
                authorization.authenticationEvidenceDigest().substring(0,12)+","+approval.canonicalDigest().substring(0,12));
        completeChange(changeId,canonical("EMERGENCY-TARGET-1","ACTIVE",digest));
        return response(changeId,binding,nextVersion,DocumentEmergencyControlState.ACTIVE,target);
    }

    @Transactional
    public DocumentEmergencyChangeResponse clear(
            DocumentEmergencyClearRequest request,String causeResolvedEvidenceRef,
            DocumentManagementAuthorizationContext authorization,DocumentApprovalEvidence approval) {
        java.util.Objects.requireNonNull(request,"request must not be null");requireText(causeResolvedEvidenceRef,"causeResolvedEvidenceRef");
        validateAuthorization(authorization,approval,DocumentManagementScope.EMERGENCY_CLEAR,false,request.deadline());
        var target=request.target();var binding=DocumentEmergencyGateCanonicalizer.targetBinding(target);String digest=binding.targetKeyDigest();
        String requestDigest=canonical("DGC-EMERGENCY-1","CLEAR",target.type(),digest,
                Long.toString(request.expectedActiveRowVersion()),request.resolutionEvidenceId(),request.deadline().toString(),
                authorization.actorSafeRef(),approval.evidenceRef(),causeResolvedEvidenceRef);
        String changeId=prepareChange(request.idempotencyKey(),requestDigest,"CLEAR",digest,
                request.expectedActiveRowVersion(),"CLEARED",request.deadline(),authorization,approval);
        var current = lock(target.type(), digest);
        if (current == null) {
            throw new IllegalStateException("emergency clear requires an active target");
        }
        if ("CLEARED".equals(current.state())) {
            if(changeId.equals(current.clearedChangeId()))return response(changeId,binding,current.rowVersion(),DocumentEmergencyControlState.CLEARED,target);
            throw new IllegalStateException("emergency target already cleared under another change");
        }
        if (current.rowVersion() != request.expectedActiveRowVersion()) {
            throw new IllegalStateException("emergency clear expected rowVersion mismatch");
        }
        int updated = jdbc.update("UPDATE document_emergency_control SET state='CLEARED',cleared_change_id=?,effective_at=?,row_version=row_version+1 WHERE target_type=? AND target_key_digest=? AND row_version=?",
                changeId, Timestamp.from(clock.instant()), target.type(), digest, current.rowVersion());
        if (updated != 1) throw new IllegalStateException("emergency clear CAS conflict");
        appendEvent(changeId, "EMERGENCY_CLEARED", "SUCCEEDED", target.type() + ":" + digest,
                "APPROVED_CLEAR", authorization.authenticationEvidenceDigest().substring(0,12)+","+approval.canonicalDigest().substring(0,12));
        completeChange(changeId,canonical("EMERGENCY-TARGET-1","CLEARED",digest));
        return response(changeId,binding,current.rowVersion()+1,DocumentEmergencyControlState.CLEARED,target);
    }

    private Row lock(String type, String digest) {
        List<Row> rows = jdbc.query("SELECT state,active_change_id,cleared_change_id,row_version FROM document_emergency_control WHERE target_type=? AND target_key_digest=? FOR UPDATE",
                (rs, row) -> new Row(rs.getString(1), rs.getString(2),rs.getString(3), rs.getLong(4)), type, digest);
        return rows.isEmpty() ? null : rows.getFirst();
    }

    private String prepareChange(String idempotencyKey,String requestDigest,String kind,String targetDigest,
                                 long expectedRowVersion,String targetState,Instant deadline,
                                 DocumentManagementAuthorizationContext authorization,DocumentApprovalEvidence approval){
        String idempotencyDigest=canonical("IDEMPOTENCY-1",idempotencyKey);
        List<ExistingChange> existing=jdbc.query("SELECT change_id,request_digest,status FROM document_governance_change WHERE unit_type='EMERGENCY_CONTROL' AND unit_key_digest=? AND idempotency_digest=? FOR UPDATE",
                (rs,row)->new ExistingChange(rs.getString(1),rs.getString(2),rs.getString(3)),targetDigest,idempotencyDigest);
        if(!existing.isEmpty()){
            ExistingChange current=existing.getFirst();
            if(!current.requestDigest().equals(requestDigest))throw new IllegalStateException("emergency idempotency conflict");
            return current.changeId();
        }
        String changeId=UUID.randomUUID().toString();Instant now=clock.instant();
        jdbc.update("INSERT INTO document_governance_change(change_id,unit_type,unit_key_digest,idempotency_digest,request_digest,change_kind,expected_state_digest,target_state_digest,gate_evidence_ref,actor_safe_ref,approval_safe_ref,authentication_evidence_digest,status,deadline,row_version,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,0,?,?)",
                changeId,"EMERGENCY_CONTROL",targetDigest,idempotencyDigest,requestDigest,kind,
                canonical("EMERGENCY-EXPECTED-1",Long.toString(expectedRowVersion)),
                canonical("EMERGENCY-TARGET-1",targetState,targetDigest),approval.evidenceRef(),
                authorization.actorSafeRef(),approval.approverSafeRef(),authorization.authenticationEvidenceDigest(),
                "PREPARED",Timestamp.from(deadline),Timestamp.from(now),Timestamp.from(now));
        return changeId;
    }

    private void completeChange(String changeId,String currentDigest){
        int updated=jdbc.update("UPDATE document_governance_change SET status='SUCCEEDED',current_state_digest=?,row_version=row_version+1,updated_at=? WHERE change_id=? AND status IN ('PREPARED','SUCCEEDED')",
                currentDigest,Timestamp.from(clock.instant()),changeId);
        if(updated!=1)throw new IllegalStateException("emergency change completion CAS conflict");
    }

    private void validateAuthorization(DocumentManagementAuthorizationContext authorization,
                                       DocumentApprovalEvidence approval,DocumentManagementScope scope,
                                       boolean allowBreakGlass,Instant deadline){
        java.util.Objects.requireNonNull(authorization).require(scope);java.util.Objects.requireNonNull(approval);
        Instant now=clock.instant();
        if(!now.isBefore(deadline))throw new IllegalStateException("emergency change deadline reached");
        if(!now.isBefore(approval.validUntil()))throw new SecurityException("document governance approval expired");
        if(authorization.actorSafeRef().equals(approval.approverSafeRef()))throw new SecurityException("separated approval identity required");
        if(approval.kind()!=DocumentApprovalKind.STANDARD_APPROVAL
                &&!(allowBreakGlass&&approval.kind()==DocumentApprovalKind.BREAK_GLASS_DISABLE_ONLY)){
            throw new SecurityException("approval kind is not allowed for emergency operation");
        }
    }

    private DocumentEmergencyChangeResponse response(String changeId,DocumentEmergencyGateTargetBinding binding,
                                                       long rowVersion,DocumentEmergencyControlState state,
                                                       DocumentEmergencyTargetRef target){
        DocumentEmergencyPropagationStatus propagation=target.type().startsWith("PROVIDER_")&&state==DocumentEmergencyControlState.ACTIVE
                ?DocumentEmergencyPropagationStatus.PROPAGATING:DocumentEmergencyPropagationStatus.COMMITTED;
        return new DocumentEmergencyChangeResponse(changeId,binding.targetType(),binding.targetKeyDigest(),state,rowVersion,propagation,clock.instant());
    }

    private CapabilityOperationType affectedProviderOperation(DocumentEmergencyTargetRef target) {
        if ("PROVIDER_OPERATION".equals(target.type())) {
            return CapabilityOperationType.of(target.key());
        }
        if (!"PROVIDER_BINDING".equals(target.type())) return null;
        List<String> operations = jdbc.query(
                "SELECT operation_type FROM document_provider_activation WHERE state='ACTIVE' AND provider_binding_digest=? FOR UPDATE",
                (rs, row) -> rs.getString(1), target.key());
        if (operations.size() > 1) throw new IllegalStateException("provider binding resolves to multiple active operations");
        return operations.isEmpty() ? null : CapabilityOperationType.of(operations.getFirst());
    }

    private static String canonical(String... values){
        try{MessageDigest digest=MessageDigest.getInstance("SHA-256");for(String value:values){byte[] bytes=value.getBytes(StandardCharsets.UTF_8);digest.update(ByteBuffer.allocate(4).putInt(bytes.length).array());digest.update(bytes);}return HexFormat.of().formatHex(digest.digest());}
        catch(Exception ex){throw new IllegalStateException(ex);}
    }

    private void appendEvent(String changeId, String eventType, String status, String refs,
                             String reason, String digestPrefixes) {
        jdbc.update("INSERT INTO document_governance_event(event_id,change_id,event_type,status,safe_refs,reason_code,digest_prefixes,occurred_at,delivery_status,delivery_attempt,row_version) VALUES(?,?,?,?,?,?,?,?,?,?,0)",
                UUID.randomUUID().toString(), changeId, eventType, status, refs, reason,
                digestPrefixes.length() > 255 ? digestPrefixes.substring(0, 255) : digestPrefixes,
                Timestamp.from(clock.instant()), "PENDING", 0);
    }

    private static void requireText(String value, String name) {
        if (value == null || value.isBlank()) throw new IllegalArgumentException(name + " must not be blank");
    }

    private record Row(String state, String activeChangeId,String clearedChangeId, long rowVersion) {}
    private record ExistingChange(String changeId,String requestDigest,String status) {}
}
