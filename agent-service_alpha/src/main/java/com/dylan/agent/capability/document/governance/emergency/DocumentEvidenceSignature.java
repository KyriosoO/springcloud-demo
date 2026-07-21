package com.dylan.agent.capability.document.governance.emergency;

import com.dylan.common.security.Ed25519IntegritySupport;

public record DocumentEvidenceSignature(
        String algorithm,
        String keyId,
        String keyVersion,
        String signatureBase64Url) {
    public DocumentEvidenceSignature {
        if (!Ed25519IntegritySupport.ALGORITHM.equals(algorithm)) {
            throw new IllegalArgumentException("only Ed25519 evidence signatures are allowed");
        }
        safe(keyId, "keyId");
        safe(keyVersion, "keyVersion");
        if (signatureBase64Url == null || !signatureBase64Url.matches("[A-Za-z0-9_-]{86}")) {
            throw new IllegalArgumentException("signatureBase64Url must be an Ed25519 Base64URL signature");
        }
    }

    private static void safe(String value, String name) {
        if (value == null || !value.matches("[A-Za-z0-9._-]{1,64}")) {
            throw new IllegalArgumentException(name + " must be a safe identifier");
        }
    }
}
