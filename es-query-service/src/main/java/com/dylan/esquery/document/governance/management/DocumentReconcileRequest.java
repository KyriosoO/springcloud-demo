package com.dylan.esquery.document.governance.management;

import java.time.Instant;

public record DocumentReconcileRequest(String idempotencyKey,Instant deadline){
    public DocumentReconcileRequest{DocumentIndexActivateRequest.requireText(idempotencyKey,"idempotencyKey");if(deadline==null)throw new IllegalArgumentException("deadline required");}
    @com.fasterxml.jackson.annotation.JsonAnySetter public void rejectUnknown(String name,Object value){throw new IllegalArgumentException("unknown management request field: "+name);}
}
