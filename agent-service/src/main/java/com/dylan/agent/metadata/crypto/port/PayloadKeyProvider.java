package com.dylan.agent.metadata.crypto.port;

import javax.crypto.SecretKey;

/** Resolves payload encryption keys by stable key id. */
public interface PayloadKeyProvider {
    SecretKey requireKey(String keyId);
}
