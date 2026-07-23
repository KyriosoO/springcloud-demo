package com.dylan.common.security;

import java.util.Locale;

import org.springframework.boot.actuate.endpoint.SanitizableData;
import org.springframework.boot.actuate.endpoint.SanitizingFunction;
import org.springframework.boot.autoconfigure.AutoConfiguration;
import org.springframework.boot.autoconfigure.condition.ConditionalOnClass;
import org.springframework.boot.autoconfigure.condition.ConditionalOnMissingBean;
import org.springframework.context.annotation.Bean;

@AutoConfiguration
@ConditionalOnClass(SanitizingFunction.class)
public class SecretSanitizingConfiguration {

	@Bean
	@ConditionalOnMissingBean(name = "secretSanitizingFunction")
	SanitizingFunction secretSanitizingFunction() {
		return data -> shouldSanitize(data) ? data.withSanitizedValue() : data;
	}

	private static boolean shouldSanitize(SanitizableData data) {
		String key = data.getKey();
		if (key == null) {
			return false;
		}
		String normalized = key.toLowerCase(Locale.ROOT).replace('_', '.').replace('-', '.');
		return normalized.startsWith("common.security.secrets.")
				|| normalized.startsWith("common.security.jwt.hmac.key.")
				|| normalized.contains(".secret.")
				|| normalized.endsWith(".secret")
				|| normalized.contains(".password.")
				|| normalized.endsWith(".password")
				|| normalized.contains(".token.")
				|| normalized.endsWith(".token")
				|| normalized.contains(".key.")
				|| normalized.endsWith(".key");
	}
}
