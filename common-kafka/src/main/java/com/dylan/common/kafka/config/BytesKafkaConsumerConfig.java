package com.dylan.common.kafka.config;

import java.util.HashMap;
import java.util.Map;

import org.apache.kafka.clients.consumer.ConsumerConfig;
import org.apache.kafka.clients.producer.ProducerConfig;
import org.apache.kafka.common.TopicPartition;
import org.apache.kafka.common.serialization.ByteArrayDeserializer;
import org.apache.kafka.common.serialization.ByteArraySerializer;
import org.apache.kafka.common.serialization.StringDeserializer;
import org.apache.kafka.common.serialization.StringSerializer;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.context.annotation.Lazy;
import org.springframework.kafka.config.ConcurrentKafkaListenerContainerFactory;
import org.springframework.kafka.core.ConsumerFactory;
import org.springframework.kafka.core.DefaultKafkaConsumerFactory;
import org.springframework.kafka.core.DefaultKafkaProducerFactory;
import org.springframework.kafka.core.KafkaTemplate;
import org.springframework.kafka.core.ProducerFactory;
import org.springframework.kafka.listener.ContainerProperties;
import org.springframework.kafka.listener.DeadLetterPublishingRecoverer;
import org.springframework.kafka.listener.DefaultErrorHandler;
import org.springframework.util.backoff.FixedBackOff;

@Configuration
public class BytesKafkaConsumerConfig {
	@Bean
	public ConsumerFactory<String, byte[]> byteConsumerFactory() {
		Map<String, Object> props = new HashMap<>();
		props.put(ConsumerConfig.BOOTSTRAP_SERVERS_CONFIG, "localhost:9092");
		props.put(ConsumerConfig.GROUP_ID_CONFIG, "byte-consumer-group");
		props.put(ConsumerConfig.ENABLE_AUTO_COMMIT_CONFIG, false);
		props.put(ConsumerConfig.MAX_POLL_RECORDS_CONFIG, 100);
		return new DefaultKafkaConsumerFactory<>(props, new StringDeserializer(), // key 反序列化
				new ByteArrayDeserializer() // value 反序列化
		);
	}

	// 3. 错误处理器
	@Bean
	public DefaultErrorHandler byteErrorHandler(
			@Lazy @Qualifier("byteKafkaTemplate") KafkaTemplate<String, byte[]> kafkaTemplate) {

		FixedBackOff backOff = new FixedBackOff(2000L, 3L); // 每 2 秒重试 3 次

		DeadLetterPublishingRecoverer recoverer = new DeadLetterPublishingRecoverer(kafkaTemplate,
				(record, ex) -> new TopicPartition(record.topic() + "-DLT", record.partition()));

		return new DefaultErrorHandler(recoverer, backOff);
	}

	// 4. ListenerContainerFactory
	@Bean
	public ConcurrentKafkaListenerContainerFactory<String, byte[]> byteKafkaListenerContainerFactory(
			@Qualifier("defaultErrorHandler") DefaultErrorHandler byteErrorHandler) {
		ConcurrentKafkaListenerContainerFactory<String, byte[]> factory = new ConcurrentKafkaListenerContainerFactory<>();
		factory.setConsumerFactory(byteConsumerFactory());
		factory.setBatchListener(true); // 批量消费
		factory.setCommonErrorHandler(byteErrorHandler);
		factory.getContainerProperties().setAckMode(ContainerProperties.AckMode.MANUAL);
		return factory;
	}
}
