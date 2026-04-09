package com.dylan.common.ws.support;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Component;
import org.springframework.web.reactive.socket.WebSocketMessage;
import org.springframework.web.reactive.socket.WebSocketSession;

import com.dylan.common.model.WsMessage;
import com.fasterxml.jackson.databind.ObjectMapper;

import reactor.core.publisher.Mono;

@Component
public class WsSender {
	@Autowired
	private OrderWebSocketHandler orderHandler;
	@Autowired
	private TransWebSocketHandler transHandler;

	private final ObjectMapper objectMapper = new ObjectMapper();

	public <T> Mono<Void> sendOrder(String userId, String type, T data) {
		WebSocketSession session = orderHandler.getSession(userId);
		if (session == null || !session.isOpen()) {
			return Mono.empty(); // 不阻塞，直接返回
		}
		WsMessage<T> message = new WsMessage<>();
		message.setUserId(userId);
		message.setType(type);
		message.setData(data);

		try {
			String payload = objectMapper.writeValueAsString(message);
			WebSocketMessage webSocketMessage = session.textMessage(payload);
			// 异步发送
			return session.send(Mono.just(webSocketMessage));
		} catch (Exception e) {
			e.printStackTrace();
			return Mono.empty();
		}
	}

	public <T> Mono<Void> sendTrans(String userId, String type, T data) {
		WebSocketSession session = transHandler.getSession(userId);
		if (session == null || !session.isOpen()) {
			return Mono.empty(); // 不阻塞，直接返回
		}
		WsMessage<T> message = new WsMessage<>();
		message.setUserId(userId);
		message.setType(type);
		message.setData(data);

		try {
			String payload = objectMapper.writeValueAsString(message);
			WebSocketMessage webSocketMessage = session.textMessage(payload);
			// 异步发送
			return session.send(Mono.just(webSocketMessage));
		} catch (Exception e) {
			e.printStackTrace();
			return Mono.empty();
		}
	}
}
