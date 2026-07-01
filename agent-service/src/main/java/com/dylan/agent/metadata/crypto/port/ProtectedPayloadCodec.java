package com.dylan.agent.metadata.crypto.port;

import com.dylan.agent.metadata.crypto.model.PayloadProtectionContext;
import com.dylan.agent.metadata.crypto.model.ProtectedPayload;

public interface ProtectedPayloadCodec {
    ProtectedPayload encrypt(byte[] plaintext, PayloadProtectionContext context);
    byte[] decrypt(ProtectedPayload payload, PayloadProtectionContext context);
}
