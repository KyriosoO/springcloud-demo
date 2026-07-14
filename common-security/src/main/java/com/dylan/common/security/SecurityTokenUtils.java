package com.dylan.common.security;

import org.springframework.security.oauth2.jwt.Jwt;

/**
 * 安全 token 工具类，统一执行服务 token 的精确识别。
 */
public final class SecurityTokenUtils {
	/**
	 * token 类型 claim 名称。
	 */
	public static final String TOKEN_TYPE_CLAIM = "token_type";
	/**
	 * 用户 token 类型值。
	 */
	public static final String USER_TOKEN_TYPE = "user";
	/**
	 * 服务 token 类型值。
	 */
	public static final String SERVICE_TOKEN_TYPE = "service";

	private SecurityTokenUtils() {
	}

	/**
	 * 判断是否为服务 token。
	 */
	public static boolean isServiceToken(Jwt jwt) {
		return jwt != null && SERVICE_TOKEN_TYPE.equals(jwt.getClaimAsString(TOKEN_TYPE_CLAIM));
	}

	/**
	 * 返回 token 主体标识。
	 */
	public static String subject(Jwt jwt) {
		return jwt == null ? null : jwt.getSubject();
	}
}
