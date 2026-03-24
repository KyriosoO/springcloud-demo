package com.dylan.common.redis.service;

public interface RedisKeyExpiredListener {
	/**
	 * 处理过期事件
	 * 
	 * @param key 过期的 key
	 */
	void onMessage(String key);
}
