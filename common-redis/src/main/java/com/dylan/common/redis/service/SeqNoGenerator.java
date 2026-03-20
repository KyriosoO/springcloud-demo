package com.dylan.common.redis.service;

import java.util.List;
import java.util.Map;
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
			long startSeqNo = endSeqNo - groupItems.size() + 1;
			for (int i = 0; i < groupItems.size(); i++) {
				seqSetter.accept(groupItems.get(i), (Long) (startSeqNo + i));
			}
		});
	}
}
