package com.dylan.agent.adapter.api.document;
public record DocumentTargetBindingReference(String schemaVersion, String contentDigest, String manifestDigest, String attestationDigest) {
    public DocumentTargetBindingReference { if(schemaVersion==null||schemaVersion.isBlank()||!digest(contentDigest)||!digest(manifestDigest)||!digest(attestationDigest)) throw new IllegalArgumentException("target binding must be complete"); }
    private static boolean digest(String value){return value!=null&&value.matches("[0-9a-f]{64}");}
}
