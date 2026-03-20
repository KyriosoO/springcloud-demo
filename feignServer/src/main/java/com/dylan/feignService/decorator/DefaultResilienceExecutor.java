package com.dylan.feignService.decorator;

import java.util.function.Supplier;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Component;

import io.github.resilience4j.circuitbreaker.CallNotPermittedException;
import io.github.resilience4j.circuitbreaker.CircuitBreaker;
import io.github.resilience4j.circuitbreaker.CircuitBreakerRegistry;
import io.github.resilience4j.ratelimiter.RateLimiter;
import io.github.resilience4j.ratelimiter.RateLimiterRegistry;
import io.github.resilience4j.ratelimiter.RequestNotPermitted;
import io.github.resilience4j.retry.Retry;
import io.github.resilience4j.retry.RetryRegistry;

@Component
public class DefaultResilienceExecutor implements ResilienceExecutor {
	@Autowired
	RetryRegistry retryRegistry;
	@Autowired
	CircuitBreakerRegistry cbRegistry;
	@Autowired
	RateLimiterRegistry rlRegistry;

	@Override
	public <T> T execute(ResilienceCommand<T> command) {
		Retry retry = retryRegistry.retry(command.getRetryName());
		CircuitBreaker cb = cbRegistry.circuitBreaker(command.getCircuitBreakerName());
		RateLimiter rl = rlRegistry.rateLimiter(command.getRateLimiterName());
//		Supplier<T> decorated = Retry.decorateSupplier(retry,
//				CircuitBreaker.decorateSupplier(cb, command.getSupplier()));
		Supplier<T> decorated = RateLimiter.decorateSupplier(rl,
				Retry.decorateSupplier(retry, CircuitBreaker.decorateSupplier(cb, command.getSupplier())));
		try {
			return decorated.get();
		} catch (RequestNotPermitted e) {
			log.warn("RateLimiter OPEN [{}]", command.getRateLimiterName());
			return command.getFallback().apply(e);
		} catch (CallNotPermittedException e) {
			log.warn("CircuitBreaker OPEN [{}]", command.getCircuitBreakerName());
			return command.getFallback().apply(e);
		} catch (Exception e) {
			log.error("Retry exhausted [{}]", command.getRetryName(), e);
			return command.getFallback().apply(e);
		}
	}

}
