package com.dylan.mqprocedureserver.controller;

import java.util.List;
import java.util.Map;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import com.dylan.mqprocedureserver.service.TransactionOperKafkaProducer;
import com.dylan.mqprocedureserver.service.TransactionOperMQProducer;
import com.dylan.mqprocedureserver.service.TransactionService;
import com.dylan.transaction.api.model.AggregateRequest;
import com.dylan.transaction.api.model.Transaction;

@RestController
@RequestMapping("/txn")
public class TransactionController {
	@Autowired
	TransactionOperKafkaProducer transactionOperKafkaProducer;
	@Autowired
	TransactionOperMQProducer transactionOperMQProducer;
	@Autowired
	TransactionService transactionService;

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

	@PutMapping("/{transId}")
	public String update(@PathVariable String transId, @RequestBody Transaction transaction,
			@RequestParam(defaultValue = "system") String operator) {
		transactionOperKafkaProducer.update(transId, transaction, operator);
		return "提交成功";
	}

	@GetMapping("/{transId}")
	public Transaction detail(@PathVariable String transId) {
		return transactionService.getByTransId(transId);
	}

	@PostMapping("/query")
	public List<Transaction> query(@RequestBody Transaction condition) {
		return transactionService.query(condition);
	}

	/**
	 * 聚合统计 —— 支持按字段分组 + COUNT。
	 * body: {"condition": {...}, "groupBy": ["transType"], "metrics": ["COUNT"]}
	 * 无 groupBy 时返回全局聚合（totalCount, totalAmount, avgAmount, minAmount, maxAmount）。
	 */
	@PostMapping("/aggregate")
	public Map<String, Object> aggregate(@RequestBody AggregateRequest request) {
		return transactionService.aggregate(request);
	}

	@PostMapping
	public Transaction create(@RequestBody Transaction transaction) {
		return transactionService.create(transaction);
	}

	@DeleteMapping("/{transId}")
	public int delete(@PathVariable String transId) {
		return transactionService.delete(transId);
	}
}
