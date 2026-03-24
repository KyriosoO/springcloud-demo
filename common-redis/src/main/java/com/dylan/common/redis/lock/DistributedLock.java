package com.dylan.common.redis.lock;

import java.lang.annotation.Retention;
import java.lang.annotation.RetentionPolicy;
import java.util.concurrent.TimeUnit;

@Retention(RetentionPolicy.RUNTIME)
public @interface DistributedLock {
	// 支持 SpEL
	String key();

	// 自动lock前缀
	String prefix() default "";

	// 等待时间
	long waitTime() default 5;

	// 锁持有时间
	long leaseTime() default 10;

	TimeUnit timeUnit() default TimeUnit.SECONDS;

	// 获取失败是否抛异常
	boolean throwException() default true;
}
