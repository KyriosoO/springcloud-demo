package com.dylan.common.redis.service;

import java.util.Collections;
import java.util.concurrent.TimeUnit;

import org.redisson.api.RLock;
import org.redisson.api.RedissonClient;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.data.redis.core.RedisTemplate;
import org.springframework.data.redis.core.script.DefaultRedisScript;
import org.springframework.stereotype.Service;

@Service
public class RedisLockService {

	@Autowired
	private RedisTemplate<String, Object> redisTemplate;
	@Autowired
	private RedissonClient redissonClient;

	private static final String LOCK_PREFIX = "lock:";

	// 加锁
	public boolean tryLock(String key, String requestId, long timeoutSeconds) {
		String lockKey = LOCK_PREFIX + key;
		Boolean success = redisTemplate.opsForValue().setIfAbsent(lockKey, requestId, timeoutSeconds, TimeUnit.SECONDS);
		return Boolean.TRUE.equals(success);
	}

	// 解锁（Lua保证原子性）
	public void unlock(String key, String requestId) {
		String lockKey = LOCK_PREFIX + key;
		String script = "if redis.call('get', KEYS[1]) == ARGV[1] then return redis.call('del', KEYS[1]) else return 0 end";
		redisTemplate.execute(new DefaultRedisScript<>(script, Long.class), Collections.singletonList(lockKey),
				requestId);
	}

	public void testLock() {
		RLock lock = redissonClient.getLock("lock:order");
		lock.lock(); // 自动续期（看门狗）
		try {
			System.out.println("执行业务");
		} finally {
			lock.unlock();
		}
	}
}