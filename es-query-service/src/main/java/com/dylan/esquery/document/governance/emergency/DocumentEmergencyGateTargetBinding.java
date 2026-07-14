package com.dylan.esquery.document.governance.emergency;

import java.util.Objects;

public record DocumentEmergencyGateTargetBinding(DocumentEmergencyTargetType targetType,String targetKeyDigest)
        implements Comparable<DocumentEmergencyGateTargetBinding> {
    public DocumentEmergencyGateTargetBinding {
        Objects.requireNonNull(targetType,"targetType must not be null");
        if(targetKeyDigest==null||!targetKeyDigest.matches("[0-9a-f]{64}"))throw new IllegalArgumentException("targetKeyDigest must be SHA-256 hex");
    }
    @Override public int compareTo(DocumentEmergencyGateTargetBinding other){int type=targetType.compareTo(other.targetType);return type!=0?type:targetKeyDigest.compareTo(other.targetKeyDigest);}
}
