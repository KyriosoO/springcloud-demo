package com.dylan.feignService.service;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import org.springframework.web.bind.annotation.RequestParam;

import com.dylan.feignService.client.IndexFeignClient;
import com.dylan.feignService.client.MQProducerClient;
import com.dylan.feignService.client.MyFeignClient;
import com.dylan.feignService.decorator.ResilienceCommand;
import com.dylan.feignService.decorator.ResilienceExecutor;

import io.github.resilience4j.circuitbreaker.CallNotPermittedException;
import io.github.resilience4j.ratelimiter.RequestNotPermitted;

@Service
public class DecoratorService {
	Logger log = LoggerFactory.getLogger(DecoratorService.class);
	@Autowired
	IndexFeignClient indexFeignClient;
	@Autowired
	MyFeignClient myFeignClient;
	@Autowired
	MQProducerClient mqProducerClient;
	@Autowired
	ResilienceExecutor resilienceExecutor;

	public String indexService(String user) {
		return resilienceExecutor.execute(
				ResilienceCommand.<String>builder().rateLimiterName("feignServiceRL").retry("feignServiceRetry")
						.circuitBreaker("feignServiceCB").run(() -> indexFeignClient.index(user)).fallback(ex -> {
							if (ex instanceof CallNotPermittedException) {
								return "系统繁忙（熔断中），请稍后再试";
							}
							if (ex instanceof feign.RetryableException) {
								return "网络异常，请检查网络";
							}
							if (ex instanceof RequestNotPermitted) {
								return "系统繁忙（限流），请稍后再试";
							}
							return "服务暂不可用";
						}).build());
	}

	public String myService() {
		return resilienceExecutor.execute(
				ResilienceCommand.<String>builder().rateLimiterName("feignServiceRL").retry("feignServiceRetry")
						.circuitBreaker("feignServiceCB").run(() -> myFeignClient.my()).fallback(ex -> {
							if (ex instanceof CallNotPermittedException) {
								return "系统繁忙（熔断中），请稍后再试";
							}
							if (ex instanceof feign.RetryableException) {
								return "网络异常，请检查网络";
							}
							if (ex instanceof RequestNotPermitted) {
								return "系统繁忙（限流），请稍后再试";
							}
							return ex.toString();
						}).build());
	}

	public String mqCreateOrderService(String userId, Integer quantity, String productId) {
		return resilienceExecutor.execute(ResilienceCommand.<String>builder().rateLimiterName("feignServiceRL")
				.retry("feignServiceRetry").circuitBreaker("feignServiceCB")
				.run(() -> mqProducerClient.createOrders(userId, quantity, productId)).fallback(ex -> {
					if (ex instanceof CallNotPermittedException) {
						return "系统繁忙（熔断中），请稍后再试";
					}
					if (ex instanceof feign.RetryableException) {
						return "网络异常，请检查网络";
					}
					if (ex instanceof RequestNotPermitted) {
						return "系统繁忙（限流），请稍后再试";
					}
					return ex.toString();
				}).build());
	}

	public String mqMyTestService(String orderId, Integer quantity) {
		return resilienceExecutor.execute(ResilienceCommand.<String>builder().rateLimiterName("feignServiceRL")
				.retry("feignServiceRetry").circuitBreaker("feignServiceCB")
				.run(() -> mqProducerClient.mqTest(orderId, quantity)).fallback(ex -> {
					if (ex instanceof CallNotPermittedException) {
						return "系统繁忙（熔断中），请稍后再试";
					}
					if (ex instanceof feign.RetryableException) {
						return "网络异常，请检查网络";
					}
					if (ex instanceof RequestNotPermitted) {
						return "系统繁忙（限流），请稍后再试";
					}
					return ex.toString();
				}).build());
	}
}
