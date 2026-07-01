package com.dylan.mqprocedureserver.ws;

import org.springframework.stereotype.Component;

import com.dylan.common.ws.support.WsSender;

import reactor.core.publisher.Mono;

@Component
public class MqProcedureWsSender {
	private final WsSender wsSender;
	private final OrderWebSocketHandler orderHandler;
	private final TransWebSocketHandler transHandler;

	public MqProcedureWsSender(WsSender wsSender, OrderWebSocketHandler orderHandler,
			TransWebSocketHandler transHandler) {
		this.wsSender = wsSender;
		this.orderHandler = orderHandler;
		this.transHandler = transHandler;
	}

	public <T> Mono<Void> sendOrder(String userId, String type, T data) {
		return wsSender.send(orderHandler, userId, type, data);
	}

	public <T> Mono<Void> sendTrans(String userId, String type, T data) {
		return wsSender.send(transHandler, userId, type, data);
	}
}
