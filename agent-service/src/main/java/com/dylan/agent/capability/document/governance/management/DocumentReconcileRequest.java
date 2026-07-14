package com.dylan.agent.capability.document.governance.management;
import java.time.Instant;
public record DocumentReconcileRequest(String idempotencyKey,Instant deadline){public DocumentReconcileRequest{if(idempotencyKey==null||idempotencyKey.isBlank()||idempotencyKey.length()>255||deadline==null)throw new IllegalArgumentException("idempotencyKey/deadline required");}@com.fasterxml.jackson.annotation.JsonAnySetter public void rejectUnknown(String name,Object value){throw new IllegalArgumentException("unknown management request field: "+name);}}
