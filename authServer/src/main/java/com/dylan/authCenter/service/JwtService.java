package com.dylan.authCenter.service;

import java.time.Instant;

import org.springframework.security.oauth2.jwt.JwsHeader;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.security.oauth2.jwt.JwtClaimsSet;
import org.springframework.security.oauth2.jwt.JwtDecoder;
import org.springframework.security.oauth2.jwt.JwtEncoder;
import org.springframework.security.oauth2.jwt.JwtEncoderParameters;
import org.springframework.security.oauth2.jwt.JwtException;
import org.springframework.stereotype.Service;

@Service
public class JwtService {

	private final JwtEncoder jwtEncoder;
	private final JwtDecoder jwtDecoder;

	// JWT 有效期，单位秒（1小时）
	private final long expiration = 3600;

	public JwtService(JwtEncoder jwtEncoder, JwtDecoder jwtDecoder) {
		this.jwtEncoder = jwtEncoder;
		this.jwtDecoder = jwtDecoder;
	}

	/**
	 * 生成 token
	 */
	public String generateToken(String username) {
		Instant now = Instant.now();
		Instant exp = now.plusSeconds(expiration);

		// 使用 Spring Security 的 JwtEncoder
		JwsHeader jwsHeader = JwsHeader.with(() -> "HS256").build();
		JwtClaimsSet claimsSet = JwtClaimsSet.builder().claims(claims -> {
			claims.put("sub", username);
			claims.put("iat", now.getEpochSecond());
			claims.put("exp", exp.getEpochSecond());
		}).issuedAt(now).expiresAt(exp).build();
		return jwtEncoder.encode(JwtEncoderParameters.from(jwsHeader, claimsSet)).getTokenValue();
	}

	/**
	 * 验证 token 是否有效
	 */
	public boolean validateToken(String token) {
		try {
			Jwt jwt = jwtDecoder.decode(token);
			Instant now = Instant.now();
			return jwt.getExpiresAt().isAfter(now);
		} catch (JwtException e) {
			return false;
		}
	}

	/**
	 * 从 token 获取用户名
	 */
	public String getUsernameFromToken(String token) {
		try {
			Jwt jwt = jwtDecoder.decode(token);
			return jwt.getSubject();
		} catch (JwtException e) {
			return null;
		}
	}
}