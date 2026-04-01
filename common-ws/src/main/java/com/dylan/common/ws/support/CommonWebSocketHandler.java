package com.dylan.common.ws.support;

import java.io.IOException;
import java.util.concurrent.ConcurrentHashMap;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.security.oauth2.jwt.JwtDecoder;
import org.springframework.security.oauth2.jwt.JwtException;
import org.springframework.stereotype.Component;
import org.springframework.web.socket.CloseStatus;
import org.springframework.web.socket.WebSocketSession;
import org.springframework.web.socket.handler.TextWebSocketHandler;

@Component
public class CommonWebSocketHandler extends TextWebSocketHandler {
	@Autowired
	private JwtDecoder jwtDecoder;

	private static final ConcurrentHashMap<String, WebSocketSession> SESSION_MAP = new ConcurrentHashMap<>();

	@Override
	public void afterConnectionEstablished(WebSocketSession session) {
		// 从 attributes 获取 token
		String token = (String) session.getAttributes().get("token");
		if (token == null) {
			try {
				session.close(CloseStatus.NOT_ACCEPTABLE.withReason("Missing token"));
			} catch (IOException ignored) {
			}
			return;
		}

		// 解析 token 获取 userId
		String userId = parseUserIdFromToken(token);
		if (userId != null) {
			SESSION_MAP.put(userId, session);
		} else {
			try {
				session.close(CloseStatus.NOT_ACCEPTABLE.withReason("Invalid token"));
			} catch (IOException ignored) {
			}
		}
	}

	@Override
	public void afterConnectionClosed(WebSocketSession session, CloseStatus status) {
		String userId = (String) session.getAttributes().get("userId");
		if (userId != null) {
			SESSION_MAP.remove(userId);
			System.out.println("WebSocket 关闭：" + userId);
		} else {
			SESSION_MAP.remove(session.getId());
			System.out.println("WebSocket 关闭，但 userId 为 null，sessionId=" + session.getId());
		}
	}

	public WebSocketSession getSession(String userId) {
		return SESSION_MAP.get(userId);
	}

	private String parseUserIdFromToken(String token) {
		try {
			// 解码 JWT
			Jwt jwt = jwtDecoder.decode(token);

			// 假设 userId 存在 claim "sub" 或自定义 "userId"
			return jwt.getSubject(); // 如果你存的是 sub，也可以用 jwt.getSubject()
		} catch (JwtException e) {
			// token 无效或过期
			return null;
		}
	}
}
