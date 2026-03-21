package com.dylan.mqConsumerServer.service;

import java.util.Comparator;
import java.util.Date;
import java.util.List;
import java.util.Set;
import java.util.concurrent.CopyOnWriteArrayList;

import org.apache.rocketmq.spring.annotation.ConsumeMode;
import org.apache.rocketmq.spring.annotation.RocketMQMessageListener;
import org.apache.rocketmq.spring.core.RocketMQListener;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;
import org.springframework.transaction.annotation.Transactional;

import com.dylan.common.model.trans.Transaction;
import com.dylan.common.model.trans.TransactionLog;
import com.dylan.common.model.trans.TransactionLogArchive;
import com.dylan.common.redis.service.SeqNoGenerator;
import com.dylan.mqConsumerServer.trans.mapper.TransactionLogArchiveMapper;
import com.dylan.mqConsumerServer.trans.mapper.TransactionLogMapper;
import com.dylan.mqConsumerServer.trans.mapper.TransactionMapper;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;

@Component
@RocketMQMessageListener(topic = "transaction-topic", consumerGroup = "transaction-consumer-group", consumeMode = ConsumeMode.ORDERLY // 顺序消费
)
public class TransactionOperConsumer implements RocketMQListener<TransactionLog> {

//	@Autowired
	private SeqNoGenerator seqNoGenerator;

//	@Autowired
	private TransactionLogMapper transactionLogMapper;

//	@Autowired
	private TransactionLogArchiveMapper transactionLogArchiveMapper;

//	@Autowired
	private TransactionMapper transactionMapper;

	// 消息批量累积
	private final List<TransactionLog> batch = new CopyOnWriteArrayList<>();

	private static final int BATCH_SIZE = 500;

	@Override
	public void onMessage(TransactionLog log) {
		batch.add(log);
		if (batch.size() >= BATCH_SIZE) {
			flushBatch();
		}
	}

	@Scheduled(fixedDelay = 1000)
	public void flushBatchByTime() {
		if (!batch.isEmpty()) {
			flushBatch();
		}
	}

	/**
	 * flushBatch 全过程加入事务，异常回滚
	 */
	@Transactional(rollbackFor = Exception.class)
	private synchronized void flushBatch() {
		if (batch.isEmpty())
			return;

		try {
			// 1. 批量生成 seq_no
			seqNoGenerator.assignBatchSeqNo("txn:", batch, TransactionLog::getTransId, TransactionLog::setSeqNo);

			// 2. 按交易 + seq_no 排序
			batch.sort(Comparator.comparing(TransactionLog::getTransId).thenComparing(TransactionLog::getSeqNo));

			// 3. 批量插入日志表（幂等）
			List<TransactionLog> logs = batch.stream().map(this::toTransactionLog).toList();
			transactionLogMapper.insertBatchIfNotExist(logs);

			// 4. 获取新增交易集合（Set便于O(1)判断）
			Set<String> addTransIdSet = transactionLogMapper.fetchNewTransByIdentityAsSet();

			// 5. 分离新增和编辑交易
			List<TransactionLog> addTransactions = logs.stream().filter(l -> addTransIdSet.contains(l.getTransId()))
					.toList();

			List<TransactionLog> editTransactions = logs.stream().filter(l -> !addTransIdSet.contains(l.getTransId()))
					.toList();

			// 6. 落库交易表
			transactionMapper.insertAll(toTransactionObjects(addTransactions));
			transactionMapper.updateAll(toTransactionObjects(editTransactions));

			// 7. 更新日志表状态为已处理
			transactionLogMapper.updateProcessed(logs);

			// 8. 日志归档
			List<TransactionLogArchive> archiveList = logs.stream().map(this::toArchive).toList();
			transactionLogArchiveMapper.save(archiveList);

			// 9. 清理过期日志（可按时间或已处理）
			transactionLogMapper.deleteTimeoutProcessed();

			// 10. 清空 batch 内存
			batch.clear();

		} catch (Exception e) {
			// 异常抛出，事务回滚，batch 不清空，等待下次 flush
			throw e;
		}
	}

	private TransactionLog toTransactionLog(TransactionLog op) {
		TransactionLog log = new TransactionLog();
		log.setTransId(op.getTransId());
		log.setSeqNo(op.getSeqNo());
		log.setPayload(op.getPayload());
		log.setProcessed(false);
		log.setCreatedAt(new Date());
		return log;
	}

	private List<Transaction> toTransactionObjects(List<TransactionLog> logs) {
		return logs.stream().map(l -> {
			try {
				return new ObjectMapper().readValue(l.getPayload(),
						new TypeReference<com.dylan.common.model.trans.Transaction>() {
						});
			} catch (JsonProcessingException e) {
				throw new RuntimeException(e);
			}
		}).toList();
	}

	private TransactionLogArchive toArchive(TransactionLog log) {
		TransactionLogArchive archive = new TransactionLogArchive();
		archive.setTransId(log.getTransId());
		archive.setSeqNo(log.getSeqNo());
		archive.setPayload(log.getPayload());
		archive.setProcessedAt(new Date());
		return archive;
	}
}
