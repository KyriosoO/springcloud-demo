package com.dylan.common.security;

public interface SecretMaterialProvider {
	SecretMaterial requireSecret(SecretKeyRef ref);
}
