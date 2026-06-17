package com.dylan.mqprocedureserver.service;

import java.util.ArrayList;
import java.util.List;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.kafka.core.KafkaTemplate;
import org.springframework.stereotype.Service;

import com.dylan.common.kafka.util.KryoUtils;
import com.dylan.transaction.api.model.Transaction;
import com.dylan.transaction.api.model.TransactionLog;
import com.dylan.common.redis.lock.DistributedLock;
import com.dylan.common.redis.service.RedisService;
import com.dylan.mqprocedureserver.mapper.TransactionMapper;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;

@Service
public class TransactionOperKafkaProducer {
	@Autowired
	private RedisService redisService;

	@Autowired
	private KafkaTemplate<String, byte[]> bytesKafkaTemplate;

	@Autowired
	TransactionMapper transactionMapper;

	@DistributedLock(prefix = "txn:", key = "#op.transId")
	public void submitOperation(TransactionLog op) {
		// 1. 写缓存
//		String cacheKey = "txn:" + op.getTransId();
//		redisService.rPush(cacheKey, op.getPayload());
		String dirtyKey = "dirty:txn:" + op.getTransId();
		redisService.set(dirtyKey, op.getPayload());
		byte[] payloads = KryoUtils.serialize(op);
		// 2. 顺序发送消息到 MQ（同一 transactionId hashKey 保证顺序消费
		bytesKafkaTemplate.send("transaction-topic", op.getTransId(), payloads);
	}

	public void startTest() {
		List<Transaction> list = transactionMapper.fetchAll();
		List<TransactionLog> logs = new ArrayList<TransactionLog>();
		list.forEach(t -> {
			try {
				String transType = t.getTransType();
				transType = transType.split("_")[0];
				TransactionLog log1 = new TransactionLog();
				log1.setTransId(t.getTransId());
				t.setTransType(transType + "_1");
				log1.setPayload(new ObjectMapper().writeValueAsString(t));
				logs.add(log1);
				TransactionLog log2 = new TransactionLog();
				log2.setTransId(t.getTransId());
				t.setTransType(transType + "_2");
				log2.setPayload(new ObjectMapper().writeValueAsString(t));
				logs.add(log2);
			} catch (JsonProcessingException e) {
				// TODO Auto-generated catch block
				e.printStackTrace();
			}
		});
		logs.forEach(l -> {
			submitOperation(l);
		});
	}

	public void update(String transId, Transaction transaction, String operator) {
		TransactionLog log = new TransactionLog();
		log.setTransId(transaction.getTransId());
		try {
			log.setPayload(new ObjectMapper().writeValueAsString(transaction));
		} catch (JsonProcessingException e) {
			// TODO Auto-generated catch block
			e.printStackTrace();
		}
		submitOperation(log);
	}
}
