package com.dylan.esquery.service;

import com.dylan.esquery.config.EsQueryProperties;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Component;
import org.springframework.web.server.ResponseStatusException;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;

/** ES 管理接口访问门禁，避免重建和 alias 操作被外部请求直接调用。 */
@Component
public class EsManagementAccessGuard {

	public static final String TOKEN_HEADER = "X-Es-Management-Token";

	private final EsQueryProperties properties;

	public EsManagementAccessGuard(EsQueryProperties properties) {
		this.properties = properties;
	}

	public void requireServiceToken(String token) {
		String expected = properties.getManagementServiceToken();
		if (expected == null || expected.isBlank() || token == null || token.isBlank()
				|| !constantTimeEquals(expected, token)) {
			throw new ResponseStatusException(HttpStatus.FORBIDDEN, "ES management service token is required");
		}
	}

	private static boolean constantTimeEquals(String expected, String actual) {
		return MessageDigest.isEqual(
				expected.getBytes(StandardCharsets.UTF_8),
				actual.getBytes(StandardCharsets.UTF_8));
	}
}
