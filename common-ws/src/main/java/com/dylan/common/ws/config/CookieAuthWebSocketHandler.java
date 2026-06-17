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
		String token = tokenFromAuthorization(session);
		if (token == null) {
			token = tokenFromCookie(session);
		}
		if (token == null) {
			return session.close();
		}
		session.getAttributes().put("token", token);
		return delegate.handle(session);
	}

	private String tokenFromAuthorization(WebSocketSession session) {
		String authorization = session.getHandshakeInfo().getHeaders().getFirst(HttpHeaders.AUTHORIZATION);
		if (authorization != null && authorization.startsWith("Bearer ")) {
			return authorization.substring(7);
		}
		return null;
	}

	private String tokenFromCookie(WebSocketSession session) {
		String cookieHeader = session.getHandshakeInfo().getHeaders().getFirst(HttpHeaders.COOKIE);
		if (cookieHeader == null) {
			return null;
		}
		return Arrays.stream(cookieHeader.split(";"))
				.map(String::trim)
				.filter(cookie -> cookie.startsWith("AUTH_TOKEN="))
				.map(cookie -> cookie.split("=", 2)[1])
				.findFirst()
				.orElse(null);
	}
}
