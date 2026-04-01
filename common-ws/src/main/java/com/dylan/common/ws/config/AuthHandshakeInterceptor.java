package com.dylan.common.ws.config;

import java.util.Arrays;
import java.util.List;
import java.util.Map;

import org.springframework.http.HttpCookie;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpStatus;
import org.springframework.http.server.ServerHttpRequest;
import org.springframework.http.server.ServerHttpResponse;
import org.springframework.web.socket.WebSocketHandler;
import org.springframework.web.socket.server.HandshakeInterceptor;

public class AuthHandshakeInterceptor implements HandshakeInterceptor {

	@Override
	public boolean beforeHandshake(ServerHttpRequest request, ServerHttpResponse response, WebSocketHandler wsHandler,
			Map<String, Object> attributes) throws Exception {
		// 从 Cookie 获取 token
		String token = request.getHeaders().getOrEmpty(HttpHeaders.COOKIE).stream()
				.flatMap(c -> Arrays.stream(c.split(";"))) // 拆分多个 Cookie
				.map(String::trim) // 去掉空格
				.filter(c -> c.startsWith("AUTH_TOKEN=")) // 找到 AUTH_TOKEN
				.map(c -> c.split("=", 2)[1]) // 取值，防止 Cookie 值中有等号
				.findFirst().orElse(null);
		if (token != null) {
			attributes.put("token", token);
			return true;
		} else {
			response.setStatusCode(HttpStatus.UNAUTHORIZED);
			return false;
		}
	}

	@Override
	public void afterHandshake(ServerHttpRequest request, ServerHttpResponse response, WebSocketHandler wsHandler,
			Exception ex) {
		// 握手后处理
	}
}