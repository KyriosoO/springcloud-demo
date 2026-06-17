package com.dylan.common.redis.service;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.lang.reflect.Field;
import java.lang.reflect.InvocationTargetException;
import java.lang.reflect.Method;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

/**
 * RedisService key 前缀语义单元测试，覆盖 buildKey 空/非空前缀、幂等保护、
 * scan pattern 拼接。
 * <p>使用反射绕过 Spring 容器，纯粹测试 key 前缀逻辑。
 */
class RedisServiceKeyPrefixTest {

	private RedisService redisService;
	private Method buildKey;
	private Field keyPrefixField;

	@BeforeEach
	void setUp() throws Exception {
		redisService = new RedisService();
		buildKey = RedisService.class.getDeclaredMethod("buildKey", String.class);
		buildKey.setAccessible(true);
		keyPrefixField = RedisService.class.getDeclaredField("keyPrefix");
		keyPrefixField.setAccessible(true);
	}

	private String callBuildKey(String key) {
		try {
			return (String) buildKey.invoke(redisService, key);
		} catch (Exception e) {
			throw new RuntimeException(e);
		}
	}

	private void setKeyPrefix(String prefix) throws Exception {
		keyPrefixField.set(redisService, prefix);
	}

	// ---- 默认前缀（空） ----

	@Test
	void buildKeyReturnsOriginalWhenPrefixEmpty() throws Exception {
		setKeyPrefix("");
		assertEquals("order:123", callBuildKey("order:123"));
	}

	@Test
	void buildKeyReturnsOriginalWhenPrefixNull() throws Exception {
		setKeyPrefix(null);
		assertEquals("order:456", callBuildKey("order:456"));
	}

	// ---- 非空前缀 — 正常拼接 ----

	@Test
	void buildKeyPrependsPrefixToBareKey() throws Exception {
		setKeyPrefix("order:");
		assertEquals("order:789", callBuildKey("789"));
	}

	// ---- 幂等保护 — 不重复拼接 ----

	@Test
	void buildKeyDoesNotDuplicatePrefix() throws Exception {
		setKeyPrefix("order:");
		assertEquals("order:205433", callBuildKey("order:205433"));
	}

	@Test
	void buildKeyWithPrefixEqualToPartialPrefixDoesNotMatch() throws Exception {
		setKeyPrefix("order:");
		// "ord" 不以 "order:" 开头，应正常拼接
		assertEquals("order:ord", callBuildKey("ord"));
	}

	@Test
	void buildKeyWithLongerPrefixDoesNotOverMatch() throws Exception {
		setKeyPrefix("myapp:order:");
		assertEquals("myapp:order:order:123", callBuildKey("order:123")); // 不以 myapp:order: 开头,正常拼接
	}
}
