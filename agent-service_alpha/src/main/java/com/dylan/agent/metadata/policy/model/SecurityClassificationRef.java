package com.dylan.agent.metadata.policy.model;

import java.nio.ByteBuffer;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.HexFormat;
import java.util.Objects;

/** 权威安全分类的不可变引用；分类名称本身不产生外部处理许可。 */
public record SecurityClassificationRef(String namespace, String classificationId, String version) {

    public SecurityClassificationRef {
        namespace = requireNonBlank(namespace, "namespace");
        classificationId = requireNonBlank(classificationId, "classificationId");
        version = requireNonBlank(version, "version");
    }

    public String canonicalDigest() {
        try {
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            update(digest, "SCR-1");
            update(digest, namespace);
            update(digest, classificationId);
            update(digest, version);
            return HexFormat.of().formatHex(digest.digest());
        } catch (NoSuchAlgorithmException ex) {
            throw new IllegalStateException("SHA-256 unavailable", ex);
        }
    }

    private static void update(MessageDigest digest, String value) {
        byte[] bytes = value.getBytes(StandardCharsets.UTF_8);
        digest.update(ByteBuffer.allocate(Integer.BYTES).putInt(bytes.length).array());
        digest.update(bytes);
    }

    private static String requireNonBlank(String value, String name) {
        Objects.requireNonNull(value, name + " must not be null");
        String normalized = value.trim();
        if (normalized.isEmpty()) throw new IllegalArgumentException(name + " must not be blank");
        return normalized;
    }
}
