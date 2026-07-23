package com.dylan.esquery.document.governance.management;

import com.dylan.esquery.api.model.DocumentCorpusKeyDto;
import com.dylan.esquery.document.governance.emergency.DocumentEmergencyGateEvidence;
import java.time.Instant;

public record DocumentIndexActivateRequest(String idempotencyKey,DocumentCorpusKeyDto corpusKey,
        String validationReportId,String expectedCurrentBindingDigest,Instant deadline,
        DocumentEmergencyGateEvidence emergencyGateEvidence){
    public DocumentIndexActivateRequest{requireText(idempotencyKey,"idempotencyKey");requireText(validationReportId,"validationReportId");requireDigest(expectedCurrentBindingDigest,"expectedCurrentBindingDigest");if(corpusKey==null||deadline==null||emergencyGateEvidence==null)throw new IllegalArgumentException("corpusKey/deadline/emergencyGateEvidence required");}
    @com.fasterxml.jackson.annotation.JsonAnySetter public void rejectUnknown(String name,Object value){throw new IllegalArgumentException("unknown management request field: "+name);}
    static void requireText(String value,String name){if(value==null||value.isBlank()||value.length()>255)throw new IllegalArgumentException(name+" invalid");}
    static void requireDigest(String value,String name){if(value==null||!value.matches("[0-9a-f]{64}"))throw new IllegalArgumentException(name+" must be SHA-256 hex");}
}
