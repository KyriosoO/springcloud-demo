package com.dylan.common.ws.support;

import java.util.concurrent.ConcurrentHashMap;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.security.oauth2.jwt.JwtDecoder;
import org.springframework.security.oauth2.jwt.JwtException;
import org.springframework.stereotype.Component;
import org.springframework.web.reactive.socket.WebSocketHandler;
import org.springframework.web.reactive.socket.WebSocketSession;

import reactor.core.publisher.Flux;
import reactor.core.publisher.Mono;

@Component
public class CommonWebSocketHandler implements WebSocketHandler {
	@Autowired
	private JwtDecoder jwtDecoder;

	private static final ConcurrentHashMap<String, WebSocketSession> SESSION_MAP = new ConcurrentHashMap<>();

	@Override
	public Mono<Void> handle(WebSocketSession session) {

		// 1️ 获取 token
		String token = (String) session.getAttributes().get("token");
		if (token == null) {
			return session.close(); // 立即关闭连接
		}

		// 2️ 验证 token
		String userId = parseUserIdFromToken(token);
		if (userId == null) {
			return session.close(); // token 无效，关闭连接
		}

		// 3️  保存 session
		SESSION_MAP.put(userId, session);
		session.getAttributes().put("userId", userId);

		// 4️  异步接收消息并处理
		Flux<String> inbound = session.receive().map(webSocketMessage -> webSocketMessage.getPayloadAsText())
				.flatMap(message -> handleMessageAsync(userId, message));

		// 5️  发送消息示例（Echo 或业务推送）
		Mono<Void> outbound = session.send(inbound.map(msg -> session.textMessage("回显：" + msg)));

		// 6️ 关闭连接时清理
		return outbound.doFinally(signalType -> {
			SESSION_MAP.remove(userId);
			System.out.println("WebSocket 关闭：" + userId);
		});
	}

	public WebSocketSession getSession(String userId) {
		return SESSION_MAP.get(userId);
	}

	private String parseUserIdFromToken(String token) {
		try {
			Jwt jwt = jwtDecoder.decode(token);
			return jwt.getSubject();
		} catch (JwtException e) {
			return null;
		}
	}

	/**
	 * 异步处理接收到的消息
	 */
	private Mono<String> handleMessageAsync(String userId, String message) {
		// 示例：可以在这里做异步 DB 或调用其他服务
		return Mono.just("处理完成: " + message);
	}
}