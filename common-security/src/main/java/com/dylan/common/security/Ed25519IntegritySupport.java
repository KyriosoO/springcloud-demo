package com.dylan.common.security;

import java.security.GeneralSecurityException;
import java.security.PrivateKey;
import java.security.PublicKey;
import java.security.Signature;
import java.util.Base64;
import java.util.Objects;

/** Ed25519 固定算法 primitive；不拥有业务 canonical 或授权语义。 */
public final class Ed25519IntegritySupport {
    public static final String ALGORITHM = "Ed25519";

    private Ed25519IntegritySupport() {
    }

    public static String signBase64Url(byte[] canonicalBytes, PrivateKey privateKey) {
        Objects.requireNonNull(canonicalBytes, "canonicalBytes must not be null");
        Objects.requireNonNull(privateKey, "privateKey must not be null");
        try {
            Signature signature = Signature.getInstance(ALGORITHM);
            signature.initSign(privateKey);
            signature.update(canonicalBytes);
            return Base64.getUrlEncoder().withoutPadding().encodeToString(signature.sign());
        } catch (GeneralSecurityException ex) {
            throw new IllegalStateException("Ed25519 signing failed", ex);
        }
    }

    public static boolean verifyBase64Url(byte[] canonicalBytes, String signatureBase64Url, PublicKey publicKey) {
        Objects.requireNonNull(canonicalBytes, "canonicalBytes must not be null");
        Objects.requireNonNull(publicKey, "publicKey must not be null");
        if (signatureBase64Url == null || !signatureBase64Url.matches("[A-Za-z0-9_-]{86}")) {
            return false;
        }
        try {
            Signature signature = Signature.getInstance(ALGORITHM);
            signature.initVerify(publicKey);
            signature.update(canonicalBytes);
            return signature.verify(Base64.getUrlDecoder().decode(signatureBase64Url));
        } catch (GeneralSecurityException | IllegalArgumentException ex) {
            return false;
        }
    }
}
