package com.dylan.mqConsumerServer.support;

import java.util.Comparator;
import java.util.Date;
import java.util.List;
import java.util.Set;
import java.util.concurrent.CopyOnWriteArrayList;
import java.util.stream.Collectors;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.dao.DuplicateKeyException;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Propagation;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.transaction.interceptor.TransactionAspectSupport;

import com.dylan.common.db.util.DBBatchExecutor;
import com.dylan.common.model.trans.Transaction;
import com.dylan.common.model.trans.TransactionLog;
import com.dylan.common.model.trans.TransactionLogArchive;
import com.dylan.common.redis.service.RedisService;
import com.dylan.common.redis.service.SeqNoGenerator;
import com.dylan.mqConsumerServer.trans.mapper.TransactionLogArchiveMapper;
import com.dylan.mqConsumerServer.trans.mapper.TransactionLogMapper;
import com.dylan.mqConsumerServer.trans.mapper.TransactionMapper;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;

@Service
public class TransBatchService {

	private final List<TransactionLog> batch = new CopyOnWriteArrayList<>();

	@Autowired
	private SeqNoGenerator seqNoGenerator;
	@Autowired
	DBBatchExecutor dbBatchExecutor;
	@Autowired
	private TransactionLogMapper transactionLogMapper;
	@Autowired
	RedisService redisService;
	@Autowired
	TransExceptionLogService mqExceptionLogService;

	/**
	 * flushBatch 全过程加入事务，异常回滚
	 */
	@Transactional(rollbackFor = Exception.class)
	public synchronized void mqFlushBatch(boolean scheduled, int BATCH_SIZE, TransactionLog log) {
		if (!scheduled && null != log) {
			batch.add(log);
		}
		if (!scheduled && batch.size() < BATCH_SIZE) {
			return;
		}
		if (scheduled && batch.isEmpty()) {
			return;
		}
		try {
			// 1. 批量生成 seq_no
			seqNoGenerator.assignBatchSeqNo("txn:", batch, TransactionLog::getTransId, TransactionLog::setSeqNo);

			// 2. 按交易 + seq_no 排序
			batch.sort(Comparator.comparing(TransactionLog::getTransId).thenComparing(TransactionLog::getSeqNo));

			// 3. 批量插入日志表（幂等）
			List<TransactionLog> logsToInsert = batch.stream().map(this::toTransactionLog).collect(Collectors.toList());
			dbBatchExecutor.executeBatch(logsToInsert, TransactionLogMapper.class, (m, i) -> {
				try {
					m.save(i);
				} catch (DuplicateKeyException e) {
					// TODO: handle exception
				}
			});
			// 4. 获取新增交易集合（Set便于O(1)判断）
			Set<String> addTransIdSet = transactionLogMapper.fetchNewTransByIdentityAsSet();

			// 5. 分离新增和编辑交易
			List<TransactionLog> addTransactions = logsToInsert.stream()
					.filter(l -> addTransIdSet.contains(l.getTransId())).collect(Collectors.toList());

			List<TransactionLog> editTransactions = logsToInsert.stream()
					.filter(l -> !addTransIdSet.contains(l.getTransId())).collect(Collectors.toList());

			// 6. 落库交易表
			dbBatchExecutor.executeBatch(toTransactionObjects(addTransactions), TransactionMapper.class,
					TransactionMapper::insertTransaction);
			dbBatchExecutor.executeBatch(toTransactionObjects(editTransactions), TransactionMapper.class,
					TransactionMapper::updateTransaction);

			// 7. 日志归档
			List<TransactionLogArchive> archiveList = batch.stream().map(this::toArchive).toList();
			dbBatchExecutor.executeBatch(archiveList, TransactionLogArchiveMapper.class,
					TransactionLogArchiveMapper::save);

			// 8. 清理日志
			dbBatchExecutor.executeBatch(batch, TransactionLogMapper.class, TransactionLogMapper::clear);
			// 9.清理缓存
			redisService.delete(batch.stream().map(l -> "dirty:txn:" + l.getTransId()).collect(Collectors.toList()));
		} catch (Exception e) {
			System.out.println("异常：" + e.getMessage());
			TransactionAspectSupport.currentTransactionStatus().setRollbackOnly();
			mqExceptionLogService.saveExceptionLog(batch);
			// TODO: handle exception
		} finally {
			// 10. 清空 batch 内存
			batch.clear();
		}
	}

	@Transactional(rollbackFor = Exception.class)
	public synchronized void kafkaFlushBatch(List<TransactionLog> logs) {
		if (logs.isEmpty()) {
			return;
		}
		try {
			// 1. 批量生成 seq_no
			seqNoGenerator.assignBatchSeqNo("txn:", logs, TransactionLog::getTransId, TransactionLog::setSeqNo);
			// 2. 按交易 + seq_no 排序
			logs.sort(Comparator.comparing(TransactionLog::getTransId).thenComparing(TransactionLog::getSeqNo));

			// 3. 批量插入日志表（幂等）
			List<TransactionLog> logsToInsert = logs.stream().map(this::toTransactionLog).collect(Collectors.toList());
			dbBatchExecutor.executeBatch(logsToInsert, TransactionLogMapper.class, (m, i) -> {
				try {
					m.save(i);
				} catch (DuplicateKeyException e) {
					
				}
			});
			// 4. 获取新增交易集合（Set便于O(1)判断）
			Set<String> addTransIdSet = transactionLogMapper.fetchNewTransByIdentityAsSet();

			// 5. 分离新增和编辑交易
			List<TransactionLog> addTransactions = logsToInsert.stream()
					.filter(l -> addTransIdSet.contains(l.getTransId())).collect(Collectors.toList());

			List<TransactionLog> editTransactions = logsToInsert.stream()
					.filter(l -> !addTransIdSet.contains(l.getTransId())).collect(Collectors.toList());

			// 6. 落库交易表
			dbBatchExecutor.executeBatch(toTransactionObjects(addTransactions), TransactionMapper.class,
					TransactionMapper::insertTransaction);
			dbBatchExecutor.executeBatch(toTransactionObjects(editTransactions), TransactionMapper.class,
					TransactionMapper::updateTransaction);

			// 7. 日志归档
			List<TransactionLogArchive> archiveList = logs.stream().map(this::toArchive).toList();
			dbBatchExecutor.executeBatch(archiveList, TransactionLogArchiveMapper.class,
					TransactionLogArchiveMapper::save);
			// 8. 清理日志
			dbBatchExecutor.executeBatch(logs, TransactionLogMapper.class, TransactionLogMapper::clear);
			// 9.清理缓存
			redisService.delete(logs.stream().map(l -> "dirty:txn:" + l.getTransId()).collect(Collectors.toList()));
		} catch (Exception e) {
			System.out.println("异常：" + e.getMessage());
			TransactionAspectSupport.currentTransactionStatus().setRollbackOnly();
//			mqExceptionLogService.saveExceptionLog(logs);
			throw new RuntimeException(e);
			// TODO: handle exception
		} finally {
			// 10. 清空 batch 内存
			batch.clear();
		}
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

	private TransactionLog toTransactionLog(TransactionLog op) {
		TransactionLog log = new TransactionLog();
		log.setTransId(op.getTransId());
		log.setSeqNo(op.getSeqNo());
		log.setPayload(op.getPayload());
		log.setCreatedAt(new Date());
		return log;
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
