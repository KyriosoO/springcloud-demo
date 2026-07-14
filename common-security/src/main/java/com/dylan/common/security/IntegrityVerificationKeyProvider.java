package com.dylan.common.security;

import java.security.PublicKey;

/** 验证侧公钥端口；不得持有或派生签发私钥。 */
public interface IntegrityVerificationKeyProvider {
    PublicKey requireEd25519PublicKey(IntegrityKeyRef keyRef);
}
