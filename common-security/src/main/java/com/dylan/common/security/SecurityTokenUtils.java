package com.dylan.common.security;

import java.util.Set;

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
	 * 判断是否为最终用户 token。
	 */
	public static boolean isUserToken(Jwt jwt) {
		return jwt != null && USER_TOKEN_TYPE.equals(jwt.getClaimAsString(TOKEN_TYPE_CLAIM));
	}

	/**
	 * 返回 token 主体标识。
	 */
	public static String subject(Jwt jwt) {
		return jwt == null ? null : jwt.getSubject();
	}

	/**
	 * 校验服务 token 的主体和单个 scope。
	 */
	public static boolean isServiceTokenAuthorized(Jwt jwt, String expectedSubject, String requiredScope) {
		return isServiceToken(jwt)
				&& expectedSubject != null
				&& expectedSubject.equals(subject(jwt))
				&& scopes(jwt).contains(requiredScope);
	}

	/**
	 * 统一业务接口既允许已认证用户访问，也允许具备指定 scope 的受信服务访问。
	 */
	public static boolean isUserOrAuthorizedService(Jwt jwt, String expectedService, String requiredScope) {
		return isUserToken(jwt) || isServiceTokenAuthorized(jwt, expectedService, requiredScope);
	}

	/**
	 * 解析 OAuth2 空格分隔的 scope claim。
	 */
	public static Set<String> scopes(Jwt jwt) {
		String scope = jwt == null ? null : jwt.getClaimAsString("scope");
		if (scope == null || scope.isBlank()) {
			return Set.of();
		}
		return Set.of(scope.trim().split("\\s+"));
	}
}
