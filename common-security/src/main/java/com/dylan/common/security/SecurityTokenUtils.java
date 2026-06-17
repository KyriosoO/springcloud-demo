package com.dylan.common.security;

import org.springframework.security.oauth2.jwt.Jwt;

/**
 * 安全 token 工具类，统一识别用户 token 和服务 token。
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
		return SERVICE_TOKEN_TYPE.equals(tokenType(jwt));
	}

	/**
	 * 判断是否为用户 token。
	 */
	public static boolean isUserToken(Jwt jwt) {
		return USER_TOKEN_TYPE.equals(tokenType(jwt));
	}

	/**
	 * 返回 token 类型；缺少 token_type 时兼容为 user。
	 */
	public static String tokenType(Jwt jwt) {
		if (jwt == null) {
			return USER_TOKEN_TYPE;
		}
		String tokenType = jwt.getClaimAsString(TOKEN_TYPE_CLAIM);
		return tokenType == null || tokenType.isBlank() ? USER_TOKEN_TYPE : tokenType;
	}

	/**
	 * 返回 token 主体标识。
	 */
	public static String subject(Jwt jwt) {
		return jwt == null ? null : jwt.getSubject();
	}
}
