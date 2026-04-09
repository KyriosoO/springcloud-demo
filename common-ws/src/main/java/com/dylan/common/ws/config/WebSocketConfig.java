package com.dylan.common.ws.config;

import java.util.HashMap;
import java.util.Map;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.web.reactive.handler.SimpleUrlHandlerMapping;
import org.springframework.web.reactive.socket.WebSocketHandler;
import org.springframework.web.reactive.socket.server.support.WebSocketHandlerAdapter;
import com.dylan.common.ws.support.CommonWebSocketHandler;
import com.dylan.common.ws.support.OrderWebSocketHandler;
import com.dylan.common.ws.support.TransWebSocketHandler;

@Configuration
public class WebSocketConfig {

	@Autowired
	OrderWebSocketHandler orderWebSocketHandler;
	@Autowired
	TransWebSocketHandler transWebSocketHandler;

	// 1️ 注册 WebSocketHandlerAdapter
	@Bean
	public WebSocketHandlerAdapter webSocketHandlerAdapter() {
		return new WebSocketHandlerAdapter();
	}

	// 2️ 注册 WebSocket 路径
	@Bean
	public SimpleUrlHandlerMapping webSocketHandlerMapping() {
		Map<String, WebSocketHandler> map = new HashMap<>();
		map.put("/ws/order", new CookieAuthWebSocketHandler(orderWebSocketHandler)); // 注册 WebSocket 端点
		map.put("/ws/trans", new CookieAuthWebSocketHandler(transWebSocketHandler));
		SimpleUrlHandlerMapping mapping = new SimpleUrlHandlerMapping();
		mapping.setUrlMap(map);
		mapping.setOrder(-1); // 优先级高
		return mapping;
	}
}
