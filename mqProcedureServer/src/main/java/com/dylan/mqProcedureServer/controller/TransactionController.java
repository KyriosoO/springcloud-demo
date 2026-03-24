package com.dylan.mqProcedureServer.controller;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import com.dylan.mqProcedureServer.service.TransactionOperKafkaProducer;
import com.dylan.mqProcedureServer.service.TransactionOperMQProducer;

@RestController
@RequestMapping("/txn")
public class TransactionController {
	@Autowired
	TransactionOperKafkaProducer transactionOperKafkaProducer;
	@Autowired
	TransactionOperMQProducer transactionOperMQProducer;

	@PostMapping("/txnmq")
	public String txnmq() {
		transactionOperMQProducer.startTest();
		return "提交成功";
	}

	@PostMapping("/txnkafka")
	public String txnkafka() {
		transactionOperKafkaProducer.startTest();
		return "提交成功";
	}
}
