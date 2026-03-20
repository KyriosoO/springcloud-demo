package com.dylan.mqConsumerServer.service;

import java.util.Arrays;
import java.util.List;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.data.redis.core.script.DefaultRedisScript;
import org.springframework.stereotype.Component;

@Component
public class StockOperService {
	private final String STOCK_KEY_PREFIX = "stock:";
	private final String PROCESSED_KEY_PREFIX = "processed:";
	private final String ROLLBACK_KEY_PREFIX = "rollbacked:";
	@Autowired
	private StringRedisTemplate redisTemplate;

	private static final String LUA_DEDUCT_SCRIPT = "-- KEYS[1] = stockKey\r\n"
			+ "-- KEYS[2] = orderProcessedKey (幂等标记)\r\n" + "-- ARGV[1] = 扣减数量\r\n" + "-- 1. 幂等判断\r\n"
			+ "if redis.call(\"exists\", KEYS[2]) == 1 then\r\n" + "    return -2\r\n" + "end\r\n" + "-- 2. 获取库存\r\n"
			+ "local stock = tonumber(redis.call(\"get\", KEYS[1]))\r\n" + "if stock == nil then\r\n"
			+ "    return -3 -- 库存不存在\r\n" + "end\r\n" + "-- 3. 库存是否足够\r\n" + "if stock < tonumber(ARGV[1]) then\r\n"
			+ "    return -1\r\n" + "end\r\n" + "-- 4. 扣减库存\r\n" + "redis.call(\"decrby\", KEYS[1], ARGV[1])\r\n"
			+ "-- 5. 标记订单已处理\r\n" + "redis.call(\"set\", KEYS[2], 1, \"EX\", 3600)\r\n"
			+ "return stock - tonumber(ARGV[1])";

	private static final String LUA_INCREASE_SCRIPT = "-- KEYS[1] = stockKey          -- 商品库存 key\r\n"
			+ "-- KEYS[2] = orderProcessedKey -- 订单幂等标记 key（用于扣减时）\r\n"
			+ "-- KEYS[3] = orderRollbackKey  -- 回退幂等标记 key\r\n" + "-- ARGV[1] = 回退数量\r\n" + "-- 1. 判断是否已经回退过（幂等）\r\n"
			+ "if redis.call(\"exists\", KEYS[3]) == 1 then\r\n" + "    return -2 -- 已经回退过\r\n" + "end\r\n"
			+ "-- 2. 获取库存\r\n" + "local stock = tonumber(redis.call(\"get\", KEYS[1]))\r\n" + "if stock == nil then\r\n"
			+ "    return -3 -- 库存不存在\r\n" + "end\r\n" + "-- 3. 回退库存\r\n"
			+ "redis.call(\"incrby\", KEYS[1], ARGV[1])\r\n" + "-- 4. 标记回退已处理\r\n"
			+ "redis.call(\"set\", KEYS[3], 1, \"EX\", 3600) -- 可设置过期时间\r\n" + "-- 5. 可选：删除扣减标记，让同一订单允许再次扣减（如果业务需要）\r\n"
			+ "--redis.call(\"del\", KEYS[2])\r\n" + "-- 6. 返回回退后的库存\r\n" + "return stock + tonumber(ARGV[1])";

	public DeductResult deductStock(String productId, String orderId, long quantity) {
		String stockKey = STOCK_KEY_PREFIX + productId;
		String orderProcessedKey = STOCK_KEY_PREFIX + PROCESSED_KEY_PREFIX + orderId;
		List<String> keys = Arrays.asList(stockKey, orderProcessedKey);
		Long result = redisTemplate.execute(new DefaultRedisScript<>(LUA_DEDUCT_SCRIPT, Long.class), keys,
				String.valueOf(quantity));
		if (result == null) {
			throw new RuntimeException("扣库存失败");
		}
		switch (result.intValue()) {
		case -1:
			return DeductResult.OUT_OF_STOCK;
		case -2:
			return DeductResult.ALREADY_PROCESSED;
		case -3:
			return DeductResult.STOCK_NOT_EXIST;
		default:
			return DeductResult.SUCCESS;
		}
	}

	public IncreaseResult increaseStock(String productId, String orderId, long quantity) {
		String stockKey = STOCK_KEY_PREFIX + productId;
		String orderProcessedKey = STOCK_KEY_PREFIX + PROCESSED_KEY_PREFIX + orderId;
		String orderRollbackKey = STOCK_KEY_PREFIX + ROLLBACK_KEY_PREFIX + orderId;
		List<String> keys = Arrays.asList(stockKey, orderProcessedKey, orderRollbackKey);
		Long result = redisTemplate.execute(new DefaultRedisScript<>(LUA_INCREASE_SCRIPT, Long.class), keys,
				String.valueOf(quantity));
		if (result == null) {
			throw new RuntimeException("扣库存失败");
		}
		switch (result.intValue()) {
		case -2:
			return IncreaseResult.ALREADY_PROCESSED;
		case -3:
			return IncreaseResult.STOCK_NOT_EXIST;
		default:
			return IncreaseResult.SUCCESS;
		}
	}

	public enum DeductResult {
		SUCCESS, OUT_OF_STOCK, ALREADY_PROCESSED, STOCK_NOT_EXIST
	}

	public enum IncreaseResult {
		SUCCESS, ALREADY_PROCESSED, STOCK_NOT_EXIST
	}
}
