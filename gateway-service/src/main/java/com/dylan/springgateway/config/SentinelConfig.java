package com.dylan.springgateway.config;

import java.util.Collections;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;

import org.springframework.beans.factory.ObjectProvider;
import org.springframework.cloud.gateway.filter.GlobalFilter;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.core.annotation.Order;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.http.codec.ServerCodecConfigurer;
import org.springframework.web.reactive.function.server.ServerResponse;
import org.springframework.web.reactive.result.view.ViewResolver;

import com.alibaba.csp.sentinel.adapter.gateway.common.rule.GatewayFlowRule;
import com.alibaba.csp.sentinel.adapter.gateway.common.rule.GatewayRuleManager;
import com.alibaba.csp.sentinel.adapter.gateway.sc.SentinelGatewayFilter;
import com.alibaba.csp.sentinel.adapter.gateway.sc.callback.GatewayCallbackManager;
import com.alibaba.csp.sentinel.adapter.gateway.sc.exception.SentinelGatewayBlockExceptionHandler;

import jakarta.annotation.PostConstruct;

@Configuration
public class SentinelConfig {
	private final List<ViewResolver> viewResolvers;
	private final ServerCodecConfigurer serverCodecConfigurer;

	public SentinelConfig(ObjectProvider<List<ViewResolver>> viewResolversProvider,
			ServerCodecConfigurer serverCodecConfigurer) {
		this.viewResolvers = viewResolversProvider.getIfAvailable(Collections::emptyList);
		this.serverCodecConfigurer = serverCodecConfigurer;
	}

	@Bean
	@Order(-10)
	public SentinelGatewayBlockExceptionHandler sentinelGatewayBlockExceptionHandler() {
		// Register the block exception handler for Spring Cloud Gateway.
		return new SentinelGatewayBlockExceptionHandler(viewResolvers, serverCodecConfigurer);
	}

	@Bean
	@Order(-1)
	public GlobalFilter sentinelGatewayFilter() {
		return new SentinelGatewayFilter();
	}

	@PostConstruct
	public void doInit() {
		GatewayCallbackManager.setBlockHandler((exchange, throwable) ->
				ServerResponse.status(HttpStatus.TOO_MANY_REQUESTS)
						.contentType(MediaType.APPLICATION_JSON)
						.bodyValue(Map.of(
								"code", 429,
								"message", "请求过于频繁，请稍后重试。")));
		initGatewayRules();
	}

	private void initGatewayRules() {
		Set<GatewayFlowRule> rules = new HashSet<>();
		rules.add(new GatewayFlowRule("hello_route")// 对应gateway中的router name
				.setCount(5) // 时间窗口内，平均允许的请求数
				.setIntervalSec(10) // 时间窗口 10 秒
				.setBurst(5)// 桶容量（突发流量）
		);
		rules.add(new GatewayFlowRule("auth_route")// 对应gateway中的router name
				.setCount(5) // 时间窗口内，平均允许的请求数
				.setIntervalSec(10) // 时间窗口 10 秒
				.setBurst(5)// 桶容量（突发流量）
		);
		rules.add(new GatewayFlowRule("direct_route")// 对应gateway中的router name
				.setCount(5) // 时间窗口内，平均允许的请求数
				.setIntervalSec(10) // 时间窗口 10 秒
				.setBurst(5)// 桶容量（突发流量）
		);
		rules.add(new GatewayFlowRule("agent_api")// Agent API 路由限流
				.setCount(5)
				.setIntervalSec(10)
				.setBurst(2));
		GatewayRuleManager.loadRules(rules);
	}
}
