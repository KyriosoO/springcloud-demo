package com.dylan.feignService.decorator;

import java.util.function.Function;
import java.util.function.Supplier;

public class ResilienceCommand<T> {
	private String retryName;
	private String circuitBreakerName;
	private String rateLimiterName;
	private Supplier<T> supplier;
	private final Function<Throwable, T> fallback;

	public String getRetryName() {
		return retryName;
	}

	public String getCircuitBreakerName() {
		return circuitBreakerName;
	}

	public Supplier<T> getSupplier() {
		return supplier;
	}

	
	public String getRateLimiterName() {
		return rateLimiterName;
	}

	public Function<Throwable, T> getFallback() {
		return fallback;
	}

	private ResilienceCommand(Builder<T> builder) {
		this.retryName = builder.retryName;
		this.circuitBreakerName = builder.circuitBreakerName;
		this.rateLimiterName = builder.rateLimiterName;
		this.supplier = builder.supplier;
		this.fallback = builder.fallback;
	}

	public static <T> Builder<T> builder() {
		return new Builder<>();
	}

	public static class Builder<T> {
		private String retryName;
		private String circuitBreakerName;
		private String rateLimiterName;
		private Supplier<T> supplier;
		private Function<Throwable, T> fallback;

		public Builder<T> retry(String retryName) {
			this.retryName = retryName;
			return this;
		}

		public Builder<T> circuitBreaker(String cbName) {
			this.circuitBreakerName = cbName;
			return this;
		}
		
		public Builder<T> rateLimiterName(String rbName){
			this.rateLimiterName = rbName;
			return this;
		}

		public Builder<T> run(Supplier<T> supplier) {
			this.supplier = supplier;
			return this;
		}

		public Builder<T> fallback(Function<Throwable, T> fallback) {
			this.fallback = fallback;
			return this;
		}

		public ResilienceCommand<T> build() {
			return new ResilienceCommand<>(this);
		}
	}
}
