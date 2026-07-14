package com.dylan.esquery.document.governance.management;

import com.dylan.esquery.api.model.DocumentCorpusKeyDto;
import com.dylan.esquery.document.governance.emergency.DocumentEmergencyGateEvidence;
import java.time.Instant;

public record DocumentIndexRollbackRequest(String idempotencyKey,DocumentCorpusKeyDto corpusKey,
        String validationReportId,String expectedCurrentBindingDigest,String relatedChangeId,Instant deadline,
        DocumentEmergencyGateEvidence emergencyGateEvidence){
    public DocumentIndexRollbackRequest{DocumentIndexActivateRequest.requireText(idempotencyKey,"idempotencyKey");DocumentIndexActivateRequest.requireText(validationReportId,"validationReportId");DocumentIndexActivateRequest.requireText(relatedChangeId,"relatedChangeId");DocumentIndexActivateRequest.requireDigest(expectedCurrentBindingDigest,"expectedCurrentBindingDigest");if(corpusKey==null||deadline==null||emergencyGateEvidence==null)throw new IllegalArgumentException("corpusKey/deadline/emergencyGateEvidence required");}
    @com.fasterxml.jackson.annotation.JsonAnySetter public void rejectUnknown(String name,Object value){throw new IllegalArgumentException("unknown management request field: "+name);}
}
