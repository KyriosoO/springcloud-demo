package com.dylan.common.redis.service;

import java.util.List;
import java.util.Map;
import java.util.concurrent.TimeUnit;
import java.util.function.BiConsumer;
import java.util.function.Function;
import java.util.stream.Collectors;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Component;

@Component
public class SeqNoGenerator {
	private static final String SEQ_KEY_PREFIX = "seq:";
	@Autowired
	RedisService redisService;

	/**
	 * 通用批量 seq_no 分配
	 * 
	 * @param items     数据类型前缀
	 * @param items     消息对象列表
	 * @param keyMapper Lambda：根据对象获取唯一 key，用于 Redis INCR
	 * @param seqSetter Lambda：给对象设置 seq_no
	 * @param <T>       对象类型
	 */
	public <T> void assignBatchSeqNo(String itemKeyPrefix, List<T> items, Function<T, String> keyMapper,
			BiConsumer<T, Long> seqSetter) {
		// 按 key 分组
		Map<String, List<T>> grouped = items.stream().collect(Collectors.groupingBy(keyMapper));
		grouped.forEach((key, groupItems) -> {
			// Redis INCRBY 批量分配 seq_no
			String redisKey = SEQ_KEY_PREFIX + itemKeyPrefix + key;
			Long endSeqNo = redisService.increment(redisKey, groupItems.size());
			redisService.expire(redisKey, 3, TimeUnit.DAYS);
			long startSeqNo = endSeqNo - groupItems.size() + 1;
			for (int i = 0; i < groupItems.size(); i++) {
				seqSetter.accept(groupItems.get(i), (Long) (startSeqNo + i));
			}
		});
	}

	/**
	 * 全局 Bloom 分配批量 seq_no
	 *
	 * @param itemKeyPrefix 数据类型前缀，用于构建全局 Bloom Key
	 * @param items         批次消息对象列表
	 * @param keyMapper     Lambda：获取交易唯一 id（用于 Bloom 判重）
	 * @param seqSetter     Lambda：给对象设置 seq_no
	 * @param <T>           对象类型
	 */
	public <T> void assignBatchSeqNoWithGlobalBloom(String itemKeyPrefix, List<T> items, Function<T, String> keyMapper,
			BiConsumer<T, Long> seqSetter) {

		if (items == null || items.isEmpty()) {
			return;
		}

		String bloomKey = SEQ_KEY_PREFIX + "bloom:" + itemKeyPrefix;

		// 初始化 Bloom
		redisService.initBloomIfAbsent(bloomKey, items.size(), 0.001);

		for (T item : items) {
			String txnId = keyMapper.apply(item);
			if (!redisService.existsInBloom(bloomKey, txnId)) { // 全局 seq_no 自增
				long seqNo = redisService.incrementGlobalSeq(bloomKey, 1);
				seqSetter.accept(item, seqNo);
				// 添加到 Bloom
				redisService.addToBloom(bloomKey, txnId);
			}
		}

		// 可选：设置过期
		redisService.expire(bloomKey, 3, TimeUnit.DAYS);
	}
}
