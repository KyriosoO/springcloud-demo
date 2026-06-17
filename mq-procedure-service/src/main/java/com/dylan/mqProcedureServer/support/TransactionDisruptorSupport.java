package com.dylan.mqprocedureserver.support;

import java.util.concurrent.Executors;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.kafka.core.KafkaTemplate;
import org.springframework.stereotype.Component;

import com.dylan.common.kafka.util.KryoUtils;
import com.dylan.transaction.api.model.TransactionLog;
import com.dylan.common.redis.service.RedisService;
import com.dylan.transaction.api.support.TransactionEvent;
import com.lmax.disruptor.BusySpinWaitStrategy;
import com.lmax.disruptor.EventHandler;
import com.lmax.disruptor.RingBuffer;
import com.lmax.disruptor.dsl.Disruptor;
import com.lmax.disruptor.dsl.ProducerType;

@Component
public class TransactionDisruptorSupport {

	private final Disruptor<TransactionEvent> disruptor;
	private final RingBuffer<TransactionEvent> ringBuffer;

	@Autowired
	private RedisService redisService;

	@Autowired
	private KafkaTemplate<String, byte[]> bytesKafkaTemplate;

	public TransactionDisruptorSupport() {
		int bufferSize = 1024 * 1024;
		disruptor = new Disruptor<>(TransactionEvent::new, bufferSize, Executors.defaultThreadFactory(),
				ProducerType.SINGLE, new BusySpinWaitStrategy());

		// Handler1: Redis 缓存
		EventHandler<TransactionEvent> redisHandler = (event, sequence, endOfBatch) -> {
			TransactionLog op = event.get();
			if (op == null)
				return;
			String dirtyKey = "dirty:txn:" + op.getTransId();
			redisService.set(dirtyKey, op.getPayload());
			// 不清理event，让下一个handler 使用
		};

		// Handler2: Kafka 发消息
		EventHandler<TransactionEvent> kafkaHandler = (event, sequence, endOfBatch) -> {
			TransactionLog op = event.get();
			if (op == null)
				return;
			byte[] payloads = KryoUtils.serialize(op);
			bytesKafkaTemplate.send("transaction-topic", op.getTransId(), payloads);
			// 清理槽位对象
			event.set(null);
		};

		// 串联流水表
		disruptor.handleEventsWith(redisHandler).then(kafkaHandler);
		disruptor.start();
		ringBuffer = disruptor.getRingBuffer();
	}

	// 生产事件入口
	public void publishEvent(TransactionLog op) {
		long sequence = ringBuffer.next();
		try {
			TransactionEvent event = ringBuffer.get(sequence);
			event.set(op);
		} finally {
			ringBuffer.publish(sequence);
		}
	}
}
