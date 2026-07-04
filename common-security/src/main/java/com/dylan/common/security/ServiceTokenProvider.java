package com.dylan.common.security;

import java.time.Duration;
import java.time.Instant;
import java.util.List;
import java.util.stream.Collectors;

import org.springframework.core.env.Environment;
import org.springframework.security.oauth2.jwt.JwsHeader;
import org.springframework.security.oauth2.jwt.JwtClaimsSet;
import org.springframework.security.oauth2.jwt.JwtEncoder;
import org.springframework.security.oauth2.jwt.JwtEncoderParameters;

/**
 * 服务 token 提供器，负责为无用户上下文的服务间调用签发短时 JWT。
 */
public class ServiceTokenProvider {
	private static final Duration REFRESH_SKEW = Duration.ofSeconds(30);
	private final JwtEncoder jwtEncoder;
	private final ServiceTokenProperties properties;
	private final Environment environment;
	private final JwtKeyProvider jwtKeyProvider;
	private volatile CachedToken cachedToken;

	/**
	 * 创建服务 token 提供器。
	 */
	public ServiceTokenProvider(
			JwtEncoder jwtEncoder,
			ServiceTokenProperties properties,
			Environment environment,
			JwtKeyProvider jwtKeyProvider) {
		this.jwtEncoder = jwtEncoder;
		this.properties = properties;
		this.environment = environment;
		this.jwtKeyProvider = jwtKeyProvider;
	}

	/**
	 * 返回可用于 Feign 调用的 Bearer token。
	 */
	public String token() {
		CachedToken current = cachedToken;
		Instant now = Instant.now();
		if (current != null && current.expiresAt().isAfter(now.plus(REFRESH_SKEW))) {
			return current.value();
		}
		synchronized (this) {
			current = cachedToken;
			now = Instant.now();
			if (current != null && current.expiresAt().isAfter(now.plus(REFRESH_SKEW))) {
				return current.value();
			}
			cachedToken = createToken(now);
			return cachedToken.value();
		}
	}

	/**
	 * 签发新的服务 token。
	 */
	private CachedToken createToken(Instant now) {
		Instant expiresAt = now.plus(ttl());
		JwtClaimsSet.Builder claimsBuilder = JwtClaimsSet.builder()
				.subject(serviceId())
				.issuedAt(now)
				.expiresAt(expiresAt)
				.claim(SecurityTokenUtils.TOKEN_TYPE_CLAIM, SecurityTokenUtils.SERVICE_TOKEN_TYPE);
		String scope = scope();
		if (!scope.isBlank()) {
			claimsBuilder.claim("scope", scope);
		}
		JwsHeader header = JwsHeader.with(() -> "HS256")
				.keyId(jwtKeyProvider.current().activeKeyId())
				.build();
		String value = jwtEncoder.encode(JwtEncoderParameters.from(header, claimsBuilder.build())).getTokenValue();
		return new CachedToken(value, expiresAt);
	}

	/**
	 * 返回服务 token 有效期。
	 */
	private Duration ttl() {
		Duration ttl = properties.getTtl();
		return ttl == null || ttl.isNegative() || ttl.isZero() ? Duration.ofSeconds(300) : ttl;
	}

	/**
	 * 返回服务身份标识。
	 */
	private String serviceId() {
		if (properties.getServiceId() != null && !properties.getServiceId().isBlank()) {
			return properties.getServiceId();
		}
		String applicationName = environment.getProperty("spring.application.name");
		return applicationName == null || applicationName.isBlank() ? "unknown-service" : applicationName;
	}

	/**
	 * 返回空格分隔的 scope 字符串。
	 */
	private String scope() {
		List<String> scopes = properties.getScopes();
		if (scopes == null || scopes.isEmpty()) {
			return "";
		}
		return scopes.stream()
				.filter(scope -> scope != null && !scope.isBlank())
				.map(String::trim)
				.collect(Collectors.joining(" "));
	}

	/**
	 * 缓存中的服务 token 及其过期时间。
	 */
	private record CachedToken(String value, Instant expiresAt) {
	}
}
