package com.dylan.agent.capability.document.governance.provider;
import com.dylan.agent.adapter.api.operation.CapabilityOperationType;
import java.time.Instant;
public record DocumentProviderDeactivateRequest(String idempotencyKey,CapabilityOperationType operationType,String expectedCurrentSnapshotDigest,DocumentGovernanceReasonCode reasonCode,Instant deadline){public DocumentProviderDeactivateRequest{DocumentProviderActivateRequest.validate(idempotencyKey,"no-report",expectedCurrentSnapshotDigest,operationType,deadline);if(reasonCode==null)throw new IllegalArgumentException("reasonCode required");}@com.fasterxml.jackson.annotation.JsonAnySetter public void rejectUnknown(String name,Object value){throw new IllegalArgumentException("unknown management request field: "+name);}}
