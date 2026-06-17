package com.dylan.mqprocedureserver.disruptor;

import java.util.concurrent.ExecutorService;
import java.util.concurrent.LinkedBlockingQueue;
import java.util.concurrent.ThreadFactory;
import java.util.concurrent.ThreadPoolExecutor;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicInteger;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.DisposableBean;
import org.springframework.stereotype.Component;

/**
 * 订单 MQ 异步发送专用线程池，与 Disruptor RingBuffer 线程隔离。
 * <p>MQ 发送可能因网络抖动、broker 繁忙而阻塞；若使用共用 ForkJoinPool
 * 或 Disruptor 自身线程，会拖慢其他业务。此独立线程池保证隔离。
 * <p>核心线程 4、最大线程 8、有界队列 2000，拒绝策略为 CallerRunsPolicy
 * （队列满时由调用方线程执行，防止消息丢失）。
 */
@Component
public class OrderMqAsyncExecutor implements DisposableBean {
	private static final Logger log = LoggerFactory.getLogger(OrderMqAsyncExecutor.class);

	private static final int CORE_POOL_SIZE = 4;
	private static final int MAX_POOL_SIZE = 8;
	private static final int QUEUE_CAPACITY = 2000;
	private static final long KEEP_ALIVE_SECONDS = 60;

	private final ExecutorService executor;

	public OrderMqAsyncExecutor() {
		ThreadFactory threadFactory = new ThreadFactory() {
			private final AtomicInteger counter = new AtomicInteger(1);

			@Override
			public Thread newThread(Runnable r) {
				Thread t = new Thread(r, "order-mq-async-" + counter.getAndIncrement());
				t.setDaemon(true);
				return t;
			}
		};
		this.executor = new ThreadPoolExecutor(
				CORE_POOL_SIZE,
				MAX_POOL_SIZE,
				KEEP_ALIVE_SECONDS, TimeUnit.SECONDS,
				new LinkedBlockingQueue<>(QUEUE_CAPACITY),
				threadFactory,
				new ThreadPoolExecutor.CallerRunsPolicy());
		log.info("OrderMqAsyncExecutor started core={} max={} queue={}",
				CORE_POOL_SIZE, MAX_POOL_SIZE, QUEUE_CAPACITY);
	}

	/**
	 * 提交 MQ 发送任务到专用线程池。
	 *
	 * @param task 发送任务
	 */
	public void execute(Runnable task) {
		executor.execute(task);
	}

	@Override
	public void destroy() {
		log.info("OrderMqAsyncExecutor shutting down");
		executor.shutdown();
		try {
			if (!executor.awaitTermination(5, TimeUnit.SECONDS)) {
				executor.shutdownNow();
			}
		} catch (InterruptedException e) {
			executor.shutdownNow();
			Thread.currentThread().interrupt();
		}
	}
}
