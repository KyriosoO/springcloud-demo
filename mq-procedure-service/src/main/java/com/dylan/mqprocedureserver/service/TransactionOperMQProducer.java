package com.dylan.mqprocedureserver.service;

import java.util.ArrayList;
import java.util.List;

import org.apache.rocketmq.spring.core.RocketMQTemplate;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.messaging.support.MessageBuilder;
import org.springframework.stereotype.Service;

import com.dylan.transaction.api.model.Transaction;
import com.dylan.transaction.api.model.TransactionLog;
import com.dylan.common.redis.lock.DistributedLock;
import com.dylan.common.redis.service.RedisService;
import com.dylan.mqprocedureserver.mapper.TransactionMapper;
import com.dylan.mqprocedureserver.support.TransactionDisruptorSupport;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;

@Service
public class TransactionOperMQProducer {

	@Autowired
	TransactionMapper transactionMapper;
	@Autowired
	private TransactionDisruptorSupport disruptorSupport;

	@DistributedLock(prefix = "txn:", key = "#op.transId")
	public void submitOperation(TransactionLog op) {
		disruptorSupport.publishEvent(op);
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
}
