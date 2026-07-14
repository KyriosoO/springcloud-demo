package com.dylan.esquery.api.model.document;

/** 跨服务传输的 Effective ResourceLimit 安全引用。 */
public record ResourceLimitBindingDto(
        String contractNamespace,
        String contractName,
        String contractVersion,
        String canonicalDigest,
        String invocationId,
        String registrationIdentity) {
    public ResourceLimitBindingDto {
        requireText(contractNamespace, "contractNamespace"); requireText(contractName, "contractName");
        requireText(contractVersion, "contractVersion"); requireText(invocationId, "invocationId");
        requireText(registrationIdentity, "registrationIdentity"); requireDigest(canonicalDigest, "canonicalDigest");
    }
    private static void requireText(String v,String n){if(v==null||v.isBlank())throw new IllegalArgumentException(n+" required");}
    private static void requireDigest(String v,String n){if(v==null||!v.matches("[0-9a-f]{64}"))throw new IllegalArgumentException(n+" invalid");}
}
