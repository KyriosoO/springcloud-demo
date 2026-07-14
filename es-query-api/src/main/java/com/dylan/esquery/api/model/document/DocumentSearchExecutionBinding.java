package com.dylan.esquery.api.model.document;

/** 文档检索 wire 完整性绑定。 */
public record DocumentSearchExecutionBinding(
        String profileName,
        String documentProfileVersion,
        String profileProjectionDigest,
        ResourceLimitBindingDto resourceLimit,
        String authorizationBindingDigest,
        String aclEvidenceDigest) {
    public DocumentSearchExecutionBinding {
        if(profileName==null||profileName.isBlank()||documentProfileVersion==null||documentProfileVersion.isBlank()
                ||resourceLimit==null)throw new IllegalArgumentException("document search execution binding incomplete");
        requireDigest(profileProjectionDigest,"profileProjectionDigest"); requireDigest(authorizationBindingDigest,"authorizationBindingDigest");
        requireDigest(aclEvidenceDigest,"aclEvidenceDigest");
    }
    private static void requireDigest(String v,String n){if(v==null||!v.matches("[0-9a-f]{64}"))throw new IllegalArgumentException(n+" invalid");}
}
