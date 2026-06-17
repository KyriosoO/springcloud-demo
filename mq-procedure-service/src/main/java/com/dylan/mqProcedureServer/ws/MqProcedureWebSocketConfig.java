package com.dylan.mqprocedureserver.ws;

import java.util.HashMap;
import java.util.Map;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.web.reactive.handler.SimpleUrlHandlerMapping;
import org.springframework.web.reactive.socket.WebSocketHandler;

import com.dylan.common.ws.config.CookieAuthWebSocketHandler;

@Configuration
public class MqProcedureWebSocketConfig {
	private final OrderWebSocketHandler orderWebSocketHandler;
	private final TransWebSocketHandler transWebSocketHandler;

	public MqProcedureWebSocketConfig(OrderWebSocketHandler orderWebSocketHandler,
			TransWebSocketHandler transWebSocketHandler) {
		this.orderWebSocketHandler = orderWebSocketHandler;
		this.transWebSocketHandler = transWebSocketHandler;
	}

	@Bean
	public SimpleUrlHandlerMapping mqProcedureWebSocketHandlerMapping() {
		Map<String, WebSocketHandler> map = new HashMap<>();
		map.put("/ws/order", new CookieAuthWebSocketHandler(orderWebSocketHandler));
		map.put("/ws/trans", new CookieAuthWebSocketHandler(transWebSocketHandler));

		SimpleUrlHandlerMapping mapping = new SimpleUrlHandlerMapping();
		mapping.setUrlMap(map);
		mapping.setOrder(-1);
		return mapping;
	}
}
