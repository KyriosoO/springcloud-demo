package com.dylan.esquery.document;

import java.util.Arrays;

/** 仅供 connector 使用的受保护游标密文；禁止日志化或解释。 */
public final class ProtectedSourceCursor {
    private final byte[] ciphertext;

    public ProtectedSourceCursor(byte[] ciphertext) {
        this.ciphertext = ciphertext == null ? new byte[0] : ciphertext.clone();
        if (this.ciphertext.length > 4096) throw new IllegalArgumentException("protected cursor exceeds limit");
    }

    public byte[] ciphertext() { return ciphertext.clone(); }
    public boolean isInitial() { return ciphertext.length == 0; }

    @Override public boolean equals(Object other) {
        return other instanceof ProtectedSourceCursor cursor && Arrays.equals(ciphertext, cursor.ciphertext);
    }

    @Override public int hashCode() { return Arrays.hashCode(ciphertext); }
    @Override public String toString() { return "ProtectedSourceCursor[redacted]"; }
}
