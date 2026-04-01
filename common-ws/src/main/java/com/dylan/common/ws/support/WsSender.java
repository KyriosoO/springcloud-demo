package com.dylan.common.ws.support;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Component;
import org.springframework.web.socket.WebSocketSession;

import com.dylan.common.model.WsMessage;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.web.socket.TextMessage;

@Component
public class WsSender {
	@Autowired
	private CommonWebSocketHandler handler;

	private final ObjectMapper objectMapper = new ObjectMapper();

	public <T> void send(String userId, String type, T data) {
		WebSocketSession session = handler.getSession(userId);

		if (session == null || !session.isOpen()) {
			return;
		}

		WsMessage<T> message = new WsMessage<>();
		message.setUserId(userId);
		message.setType(type);
		message.setData(data);

		try {
			session.sendMessage(new TextMessage(objectMapper.writeValueAsString(message)));
		} catch (Exception e) {
			e.printStackTrace();
		}
	}
}
