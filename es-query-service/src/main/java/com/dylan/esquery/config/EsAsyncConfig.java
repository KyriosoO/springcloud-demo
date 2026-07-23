package com.dylan.esquery.config;

import java.util.concurrent.Executor;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.scheduling.concurrent.ThreadPoolTaskExecutor;

/**
 * ES 异步配置，定义索引重建线程池。
 */
@Configuration
public class EsAsyncConfig {

	/**
	 * 处理 esRebuildExecutor 相关逻辑。
	 */
	@Bean("esRebuildExecutor")
	public Executor esRebuildExecutor() {
		ThreadPoolTaskExecutor executor = new ThreadPoolTaskExecutor();
		executor.setThreadNamePrefix("es-rebuild-");
		executor.setCorePoolSize(2);
		executor.setMaxPoolSize(4);
		executor.setQueueCapacity(100);
		executor.initialize();
		return executor;
	}
}
