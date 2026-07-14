package com.dylan.agent.adapter.api.document;

import com.dylan.agent.adapter.api.operation.ResourceLimitReference;

/** 当前 Invocation 内冻结的检索完整性绑定。 */
public record DocumentRetrievalExecutionBinding(
        String profileName,
        String documentProfileVersion,
        String profileProjectionDigest,
        ResourceLimitReference resourceLimitReference,
        String authorizationBindingDigest,
        String aclEvidenceDigest) {
    public DocumentRetrievalExecutionBinding {
        requireText(profileName, "profileName");
        requireText(documentProfileVersion, "documentProfileVersion");
        requireDigest(profileProjectionDigest, "profileProjectionDigest");
        if (resourceLimitReference == null) throw new IllegalArgumentException("resourceLimitReference required");
        requireDigest(authorizationBindingDigest, "authorizationBindingDigest");
        requireDigest(aclEvidenceDigest, "aclEvidenceDigest");
    }
    private static void requireText(String value,String name){if(value==null||value.isBlank())throw new IllegalArgumentException(name+" required");}
    private static void requireDigest(String value,String name){if(value==null||!value.matches("[0-9a-f]{64}"))throw new IllegalArgumentException(name+" invalid");}
}
