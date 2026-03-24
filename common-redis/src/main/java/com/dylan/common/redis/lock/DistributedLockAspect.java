package com.dylan.common.redis.lock;

import org.aspectj.lang.ProceedingJoinPoint;
import org.aspectj.lang.annotation.Around;
import org.aspectj.lang.annotation.Aspect;
import org.aspectj.lang.reflect.MethodSignature;
import org.redisson.api.RLock;
import org.redisson.api.RedissonClient;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.expression.EvaluationContext;
import org.springframework.expression.ExpressionParser;
import org.springframework.expression.spel.standard.SpelExpressionParser;
import org.springframework.expression.spel.support.StandardEvaluationContext;
import org.springframework.stereotype.Component;

@Aspect
@Component
public class DistributedLockAspect {
	private static final String LOCK = "lock:";
	@Autowired
	private RedissonClient redissonClient;

	@Around("@annotation(distributedLock)")
	public Object around(ProceedingJoinPoint joinPoint, DistributedLock distributedLock) throws Throwable {
		String key = parseKey(distributedLock.prefix(), distributedLock.key(), joinPoint);
		RLock lock = redissonClient.getLock(key);
		boolean success = false;
		try {
			success = lock.tryLock(distributedLock.waitTime(), distributedLock.leaseTime(), distributedLock.timeUnit());
			if (!success) {
				if (distributedLock.throwException()) {
					throw new RuntimeException("获取锁失败: " + key);
				}
				return null;
			}
			return joinPoint.proceed();
		} finally {
			if (success && lock.isHeldByCurrentThread()) {
				lock.unlock();
			}
		}
	}

	// SpEL 解析
	private String parseKey(String prefix, String key, ProceedingJoinPoint joinPoint) {
		prefix = null == prefix ? "" : prefix;
		MethodSignature signature = (MethodSignature) joinPoint.getSignature();
		Object[] args = joinPoint.getArgs();
		String[] paramNames = signature.getParameterNames();
		EvaluationContext context = new StandardEvaluationContext();
		for (int i = 0; i < paramNames.length; i++) {
			context.setVariable(paramNames[i], args[i]);
		}
		ExpressionParser parser = new SpelExpressionParser();
		return LOCK + prefix + parser.parseExpression(key).getValue(context, String.class);
	}
}
