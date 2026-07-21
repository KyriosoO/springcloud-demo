package com.dylan.agent.metadata.crypto.port;

import javax.crypto.SecretKey;

/** 按稳定 key id 解析 payload encryption key。 */
public interface PayloadKeyProvider {
    SecretKey requireKey(String keyId);
}
