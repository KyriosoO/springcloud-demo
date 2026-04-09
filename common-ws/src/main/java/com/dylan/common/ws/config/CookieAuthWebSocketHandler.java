package com.dylan.common.ws.config;

import java.util.Arrays;

import org.springframework.http.HttpHeaders;
import org.springframework.web.reactive.socket.WebSocketHandler;
import org.springframework.web.reactive.socket.WebSocketSession;

import reactor.core.publisher.Mono;

public class CookieAuthWebSocketHandler implements WebSocketHandler {
	private final WebSocketHandler delegate;

	public CookieAuthWebSocketHandler(WebSocketHandler delegate) {
		this.delegate = delegate;
	}

	@Override
	public Mono<Void> handle(WebSocketSession session) {

		// 从原始请求头获取 Cookie
		String cookieHeader = session.getHandshakeInfo().getHeaders().getFirst(HttpHeaders.COOKIE);

		String token = null;
		if (cookieHeader != null) {
			token = Arrays.stream(cookieHeader.split(";")).map(String::trim).filter(c -> c.startsWith("AUTH_TOKEN="))
					.map(c -> c.split("=", 2)[1]).findFirst().orElse(null);
		}

		if (token == null) {
			// token 不存在，关闭连接
			return session.close();
		}

		// 保存 token 到 session attributes
		session.getAttributes().put("token", token);

		// 交给原来的 Handler 处理
		return delegate.handle(session);
	}

}