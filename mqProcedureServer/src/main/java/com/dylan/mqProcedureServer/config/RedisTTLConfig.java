package com.dylan.mqProcedureServer.config;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.data.redis.connection.RedisConnectionFactory;
import org.springframework.data.redis.listener.PatternTopic;
import org.springframework.data.redis.listener.RedisMessageListenerContainer;

import com.dylan.mqProcedureServer.service.OrderTimeoutListener;

@Configuration
public class RedisTTLConfig {
	@Autowired
	OrderTimeoutListener orderTimeoutListener;

	@Bean
	public RedisMessageListenerContainer redisContainer(RedisConnectionFactory connectionFactory) {
		RedisMessageListenerContainer container = new RedisMessageListenerContainer();
		container.setConnectionFactory(connectionFactory);
		container.addMessageListener(orderTimeoutListener, new PatternTopic("__keyevent@0__:expired") // 数据库 0
																										// 的过期事件
		);
		return container;
	}
}