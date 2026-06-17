package com.dylan.common.ws.support;

import org.springframework.stereotype.Component;
import org.springframework.web.reactive.socket.WebSocketMessage;
import org.springframework.web.reactive.socket.WebSocketSession;

import com.dylan.common.model.WsMessage;
import com.fasterxml.jackson.databind.ObjectMapper;

import reactor.core.publisher.Mono;

@Component
public class WsSender {
	private final ObjectMapper objectMapper = new ObjectMapper();

	public <T> Mono<Void> send(CommonWebSocketHandler handler, String userId, String type, T data) {
		WebSocketSession session = handler.getSession(userId);
		if (session == null || !session.isOpen()) {
			return Mono.empty();
		}
		WsMessage<T> message = new WsMessage<>();
		message.setUserId(userId);
		message.setType(type);
		message.setData(data);

		try {
			String payload = objectMapper.writeValueAsString(message);
			WebSocketMessage webSocketMessage = session.textMessage(payload);
			return session.send(Mono.just(webSocketMessage));
		} catch (Exception e) {
			e.printStackTrace();
			return Mono.empty();
		}
	}
}
