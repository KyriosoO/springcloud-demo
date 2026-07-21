package com.dylan.agent.metadata;

import com.dylan.agent.metadata.crypto.model.PayloadProtectionContext;
import com.dylan.agent.metadata.crypto.model.ProtectedPayload;
import com.dylan.agent.metadata.crypto.port.ProtectedPayloadCodec;

final class PlainCodec implements ProtectedPayloadCodec {
    @Override
    public ProtectedPayload encrypt(byte[] plaintext, PayloadProtectionContext context) {
        return new ProtectedPayload(plaintext, "ACTIVE", new byte[] {1}, "plain");
    }

    @Override
    public byte[] decrypt(ProtectedPayload payload, PayloadProtectionContext context) {
        return payload.ciphertext();
    }
}
