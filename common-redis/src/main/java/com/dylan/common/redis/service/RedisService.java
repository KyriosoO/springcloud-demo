package com.dylan.common.redis.service;

import org.redisson.api.RBloomFilter;
import org.redisson.api.RedissonClient;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.data.redis.core.*;
import org.springframework.stereotype.Service;

import java.time.Duration;
import java.time.Instant;
import java.time.temporal.ChronoUnit;
import java.util.*;
import java.util.concurrent.TimeUnit;

@Service
public class RedisService {

	@Autowired
	private RedisTemplate<String, Object> redisTemplate;
	@Autowired
	RedissonClient redissonClient;

	@Value("${redis.key-prefix:}") // 默认空前缀
	private String keyPrefix;

	// ======= Key 前缀处理 =======
	private String buildKey(String key) {
		return keyPrefix + key;
	}

	private Collection<String> buildKeys(Collection<String> keys) {
		if (keys == null)
			return null;
		List<String> prefixed = new ArrayList<>();
		for (String key : keys) {
			prefixed.add(buildKey(key));
		}
		return prefixed;
	}

	// =================== Key 操作 ===================
	public boolean exists(String key) {
		Boolean exist = redisTemplate.hasKey(buildKey(key));
		return exist != null && exist;
	}

	public void delete(String key) {
		redisTemplate.delete(buildKey(key));
	}

	public void delete(Collection<String> keys) {
		redisTemplate.delete(buildKeys(keys));
	}

	public boolean expire(String key, long timeout, TimeUnit unit) {
		Boolean result = redisTemplate.expire(buildKey(key), timeout, unit);
		return result != null && result;
	}

	public Long ttl(String key, TimeUnit unit) {
		return redisTemplate.getExpire(buildKey(key), unit);
	}

	// =================== Value ===================
	public void set(String key, Object value) {
		redisTemplate.opsForValue().set(buildKey(key), value);
	}

	public void set(String key, Object value, long timeoutSeconds) {
		redisTemplate.opsForValue().set(buildKey(key), value, timeoutSeconds, TimeUnit.SECONDS);
	}

	public Object get(String key) {
		return redisTemplate.opsForValue().get(buildKey(key));
	}

	public Long increment(String key, long delta) {
		return redisTemplate.opsForValue().increment(buildKey(key), delta);
	}

	public Double increment(String key, double delta) {
		return redisTemplate.opsForValue().increment(buildKey(key), delta);
	}

	// =================== Hash ===================
	public void hSet(String key, String hashKey, Object value) {
		redisTemplate.opsForHash().put(buildKey(key), hashKey, value);
	}

	public Object hGet(String key, String hashKey) {
		return redisTemplate.opsForHash().get(buildKey(key), hashKey);
	}

	public Map<Object, Object> hGetAll(String key) {
		return redisTemplate.opsForHash().entries(buildKey(key));
	}

	public void hDelete(String key, Object... hashKeys) {
		redisTemplate.opsForHash().delete(buildKey(key), hashKeys);
	}

	public boolean hExists(String key, String hashKey) {
		Boolean exist = redisTemplate.opsForHash().hasKey(buildKey(key), hashKey);
		return exist != null && exist;
	}

	public Long hIncrement(String key, String hashKey, long delta) {
		return redisTemplate.opsForHash().increment(buildKey(key), hashKey, delta);
	}

	// =================== List ===================
	public void lPush(String key, Object value) {
		redisTemplate.opsForList().leftPush(buildKey(key), value);
	}

	public void rPush(String key, Object value) {
		redisTemplate.opsForList().rightPush(buildKey(key), value);
	}

	public Object lPop(String key) {
		return redisTemplate.opsForList().leftPop(buildKey(key));
	}

	public Object rPop(String key) {
		return redisTemplate.opsForList().rightPop(buildKey(key));
	}

	public List<Object> lRange(String key, long start, long end) {
		return redisTemplate.opsForList().range(buildKey(key), start, end);
	}

	public Long lLen(String key) {
		return redisTemplate.opsForList().size(buildKey(key));
	}

	// =================== Set ===================
	public void sAdd(String key, Object... values) {
		redisTemplate.opsForSet().add(buildKey(key), values);
	}

	public Set<Object> sMembers(String key) {
		return redisTemplate.opsForSet().members(buildKey(key));
	}

	public boolean sIsMember(String key, Object value) {
		Boolean exist = redisTemplate.opsForSet().isMember(buildKey(key), value);
		return exist != null && exist;
	}

	public void sRemove(String key, Object... values) {
		redisTemplate.opsForSet().remove(buildKey(key), values);
	}

	public Long sSize(String key) {
		return redisTemplate.opsForSet().size(buildKey(key));
	}

	// =================== Sorted Set ===================
	public void zAdd(String key, Object value, double score) {
		redisTemplate.opsForZSet().add(buildKey(key), value, score);
	}

	public Set<Object> zRange(String key, long start, long end) {
		return redisTemplate.opsForZSet().range(buildKey(key), start, end);
	}

	public Set<Object> zRangeByScore(String key, double min, double max) {
		return redisTemplate.opsForZSet().rangeByScore(buildKey(key), min, max);
	}

	public void zRemove(String key, Object... values) {
		redisTemplate.opsForZSet().remove(buildKey(key), values);
	}

	public Double zScore(String key, Object value) {
		return redisTemplate.opsForZSet().score(buildKey(key), value);
	}

	public Long zSize(String key) {
		return redisTemplate.opsForZSet().size(buildKey(key));
	}

	// =================== 批量 Value ===================

	// 批量获取
	public List<Object> multiGet(Collection<String> keys) {
		Collection<String> realKeys = buildKeys(keys);
		return redisTemplate.opsForValue().multiGet(realKeys);
	}

	// 批量设置
	public void multiSet(Map<String, Object> map) {
		Map<String, Object> newMap = new HashMap<>();
		for (Map.Entry<String, Object> entry : map.entrySet()) {
			newMap.put(buildKey(entry.getKey()), entry.getValue());
		}
		redisTemplate.opsForValue().multiSet(newMap);
	}

	// 批量设置（带过期时间）
	public void multiSetWithExpire(Map<String, Object> map, long timeout, TimeUnit unit) {
		for (Map.Entry<String, Object> entry : map.entrySet()) {
			set(entry.getKey(), entry.getValue(), unit.toSeconds(timeout));
		}
	}

	// =================== Scan Key ===================
	public Set<String> scan(String pattern) {
		Set<String> keys = new HashSet<>();

		ScanOptions options = ScanOptions.scanOptions().match(keyPrefix + pattern).count(1000).build();

		Cursor<byte[]> cursor = redisTemplate.getConnectionFactory().getConnection().keyCommands().scan(options);

		while (cursor.hasNext()) {
			keys.add(new String(cursor.next()));
		}

		return keys;
	}

	// =================== 模糊删除 ===================
	public long deleteByPattern(String pattern) {
		Set<String> keys = scan(pattern);
		if (keys == null || keys.isEmpty()) {
			return 0;
		}
		redisTemplate.delete(keys);
		return keys.size();
	}

	// =================== 增减操作 ===================
	/**
	 * 原子自增（整数）
	 */
	public Long increase(String key, long delta) {
		return redisTemplate.opsForValue().increment(key, delta);
	}

	/**
	 * 原子自减（整数）
	 */
	public Long decrease(String key, long delta) {
		return redisTemplate.opsForValue().increment(key, -delta);
	}

	/**
	 * 原子自增（浮点数）
	 */
	public Double increase(String key, double delta) {
		return redisTemplate.opsForValue().increment(key, delta);
	}

	/**
	 * 原子自减（浮点数）
	 */
	public Double decrease(String key, double delta) {
		return redisTemplate.opsForValue().increment(key, -delta);
	}

	// ---------------- 锁/库存常用方法 ----------------

	/**
	 * 原子自减库存，如果库存不足返回false
	 */
	public boolean decreaseStock(String key, long delta) {
		Long result = redisTemplate.opsForValue().increment(key, -delta);
		if (result == null || result < 0) {
			// 回退
			redisTemplate.opsForValue().increment(key, delta);
			return false;
		}
		return true;
	}

	/**
	 * 初始化 Bloom Filter，如果已存在则忽略异常
	 *
	 * @param bloomKey           Bloom Key
	 * @param expectedInsertions 预计元素数
	 * @param falsePositiveRate  误判率
	 */
	public void initBloomIfAbsent(String bloomKey, long expectedInsertions, double falsePositiveRate) {
		RBloomFilter<String> bloomFilter = redissonClient.getBloomFilter(bloomKey);
		try {
			if (!bloomFilter.isExists()) {
				bloomFilter.tryInit(expectedInsertions, falsePositiveRate);
			}
		} catch (Exception ignored) {
			// 已存在 Bloom，忽略异常
		}
	}

	/**
	 * 判断元素是否存在 Bloom
	 */
	public boolean existsInBloom(String bloomKey, String value) {
		RBloomFilter<String> bloomFilter = redissonClient.getBloomFilter(bloomKey);
		return bloomFilter.contains(value);
	}

	/**
	 * 添加元素到 Bloom
	 */
	public void addToBloom(String bloomKey, String value) {
		RBloomFilter<String> bloomFilter = redissonClient.getBloomFilter(bloomKey);
		bloomFilter.add(value);
	}

	/**
	 * 设置 Bloom 过期
	 */
	public void expire(String bloomKey, long time, ChronoUnit unit) {
		RBloomFilter<String> bloomFilter = redissonClient.getBloomFilter(bloomKey);
		bloomFilter.expire(Duration.of(time, unit));
	}

	/**
	 * 获取全局 seq_no 自增起点
	 */
	public long incrementGlobalSeq(String key, long delta) {
		return redissonClient.getAtomicLong(key).addAndGet(delta);
	}

	/**
	 * 获取全局 seq_no 当前值（可选）
	 */
	public long getGlobalSeq(String key) {
		return redissonClient.getAtomicLong(key).get();
	}
}