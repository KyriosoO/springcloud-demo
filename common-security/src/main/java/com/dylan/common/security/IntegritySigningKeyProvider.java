package com.dylan.common.security;

import java.security.PrivateKey;

/** 签发侧私钥端口；实现必须按 exact keyId/keyVersion fail closed。 */
public interface IntegritySigningKeyProvider {
    PrivateKey requireEd25519PrivateKey(IntegrityKeyRef keyRef);
}
