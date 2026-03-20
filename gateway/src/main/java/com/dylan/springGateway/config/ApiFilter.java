package com.dylan.springGateway.config;

import org.springframework.cloud.gateway.filter.GatewayFilterChain;
import org.springframework.cloud.gateway.filter.GlobalFilter;
import org.springframework.context.annotation.Configuration;
import org.springframework.core.Ordered;
import org.springframework.core.annotation.Order;
import org.springframework.web.server.ServerWebExchange;

import reactor.core.publisher.Mono;

@Configuration
@Order(Ordered.HIGHEST_PRECEDENCE) // 顺序很重要，数字越小越靠前
public class ApiFilter implements GlobalFilter {

	@Override
	public Mono<Void> filter(ServerWebExchange exchange, GatewayFilterChain chain) {
		return chain.filter(exchange);
//		ServerHttpResponse response = exchange.getResponse();
//		response.setStatusCode(HttpStatus.UNAUTHORIZED);
//		return response.setComplete(); // 直接结束
//		return chain.filter(exchange).then(Mono.fromRunnable(() -> {
//			HttpStatusCode status = exchange.getResponse().getStatusCode();
//			if (status == HttpStatus.TOO_MANY_REQUESTS) {
//				// 这里可以记录日志、打点、埋监控
//				System.out.println("下游服务返回 500");
//			}
//		}));
	}

}
