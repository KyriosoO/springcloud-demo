package com.dylan.feignService.config;

import java.time.Duration;
import java.util.concurrent.TimeUnit;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.http.HttpHeaders;
import org.springframework.web.context.request.RequestContextHolder;
import org.springframework.web.context.request.ServletRequestAttributes;

import feign.Request;
import feign.RequestInterceptor;
import feign.codec.ErrorDecoder;
import io.github.resilience4j.circuitbreaker.CallNotPermittedException;
import io.github.resilience4j.circuitbreaker.CircuitBreaker;
import io.github.resilience4j.circuitbreaker.CircuitBreakerConfig;
import io.github.resilience4j.ratelimiter.RateLimiter;
import io.github.resilience4j.ratelimiter.RateLimiterConfig;
import io.github.resilience4j.ratelimiter.RateLimiterRegistry;
import io.github.resilience4j.ratelimiter.RequestNotPermitted;
import io.github.resilience4j.circuitbreaker.CircuitBreakerRegistry;
import io.github.resilience4j.retry.Retry;
import io.github.resilience4j.retry.RetryConfig;
import io.github.resilience4j.retry.RetryRegistry;
import jakarta.servlet.http.HttpServletRequest;

@Configuration
public class FeignConfig {
	Logger log = LoggerFactory.getLogger(FeignConfig.class);

	@Bean
	public Request.Options feignRequestOptions() {
		return new Request.Options(2, TimeUnit.SECONDS, // 连接超时
				5, TimeUnit.SECONDS, // 读取超时
				true // 是否允许重定向
		);
	}

	@Bean
	public Retry feignServiceRetry(RetryRegistry retryRegistry) {
		RetryConfig config = RetryConfig.custom().maxAttempts(3) // 最大重试次数
				.waitDuration(Duration.ofMillis(500)) // 每次重试间隔
				.retryExceptions(RuntimeException.class)
				.ignoreExceptions(RequestNotPermitted.class, CallNotPermittedException.class).build();
		Retry retry = retryRegistry.retry("feignServiceRetry", config);
		retry.getEventPublisher().onEvent(event -> {
			log.warn("Retry 重试 | name={} | 第 {} 次 | 上次异常={}", event.getName(), event.getNumberOfRetryAttempts(),
					event.getLastThrowable().toString());
		});
		return retry;
	}

	@Bean
	public CircuitBreakerConfig defaultCircuitBreakerConfig() {
		return CircuitBreakerConfig.custom().slidingWindowType(CircuitBreakerConfig.SlidingWindowType.COUNT_BASED)
				.slidingWindowSize(100).failureRateThreshold(50).slowCallRateThreshold(50)
				.slowCallDurationThreshold(Duration.ofMillis(60000)).waitDurationInOpenState(Duration.ofSeconds(5))
				.permittedNumberOfCallsInHalfOpenState(3).automaticTransitionFromOpenToHalfOpenEnabled(true).build();
	}

	@Bean
	public CircuitBreaker feignServiceCB(CircuitBreakerRegistry circuitBreakerRegistry,
			CircuitBreakerConfig defaultCircuitBreakerConfig) {
		CircuitBreakerConfig config = CircuitBreakerConfig.from(defaultCircuitBreakerConfig).minimumNumberOfCalls(10)
				.failureRateThreshold(20)
//				.ignoreExceptions(RuntimeException.class)
//				.recordExceptions(feign.RetryableException.class, SocketTimeoutException.class, IOException.class)
				.waitDurationInOpenState(Duration.ofSeconds(10)).build();
		CircuitBreaker cb = circuitBreakerRegistry.circuitBreaker("feignServiceCB", config);
		cb.getEventPublisher().onEvent(event -> {
			log.warn("熔断 | name={} | 创建时间={}", event.getCircuitBreakerName(), event.getCreationTime());
		});
		return cb;
	}

	@Bean
	public RateLimiter feignServiceRL(RateLimiterRegistry rateLimiterRegistry) {
		RateLimiterConfig config = RateLimiterConfig.custom().limitForPeriod(50)
				.limitRefreshPeriod(Duration.ofSeconds(5)).timeoutDuration(Duration.ofSeconds(5)).build();
		RateLimiter rl = rateLimiterRegistry.rateLimiter("feignServiceRL", config);
		rl.getEventPublisher().onEvent(event -> {
			log.warn("限流 | name={} | 第 {} 次请求 | 创建时间={}", event.getRateLimiterName(), event.getNumberOfPermits(),
					event.getCreationTime());
		});
		return rl;
	}

//	@Bean
	public RequestInterceptor requestInterceptor() {
		return template -> {
			ServletRequestAttributes attributes = (ServletRequestAttributes) RequestContextHolder
					.getRequestAttributes();
			if (attributes == null) {
				return;
			}
			HttpServletRequest request = attributes.getRequest();
			String token = request.getHeader("Authorization");
			System.out.println("Feign token = " + token);
			template.headers();
			if (token != null) {
				template.header(HttpHeaders.AUTHORIZATION, token);
			}
		};
	}
}
