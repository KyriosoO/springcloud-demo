package com.dylan.mqprocedureserver.controller;

import java.util.List;
import java.util.Map;

import org.springframework.security.core.Authentication;
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
import com.dylan.mqprocedureserver.security.CapabilityAccessGuard;
import com.dylan.transaction.api.model.AggregateRequest;
import com.dylan.transaction.api.model.Transaction;
import com.dylan.transaction.api.query.TransactionSearchRequest;
import com.dylan.transaction.api.query.TransactionSearchResponse;

@RestController
@RequestMapping("/txn")
public class TransactionController {
	private final TransactionOperKafkaProducer transactionOperKafkaProducer;
	private final TransactionOperMQProducer transactionOperMQProducer;
	private final TransactionService transactionService;
	private final CapabilityAccessGuard accessGuard;

	public TransactionController(TransactionOperKafkaProducer transactionOperKafkaProducer,
								 TransactionOperMQProducer transactionOperMQProducer,
								 TransactionService transactionService,
								 CapabilityAccessGuard accessGuard) {
		this.transactionOperKafkaProducer = transactionOperKafkaProducer;
		this.transactionOperMQProducer = transactionOperMQProducer;
		this.transactionService = transactionService;
		this.accessGuard = accessGuard;
	}

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

	@PostMapping("/condition")
	public Transaction findByCondition(@RequestBody Transaction condition) {
		return transactionService.findByCondition(condition);
	}

	@PostMapping("/query")
	public List<Transaction> query(@RequestBody Transaction condition) {
		return transactionService.query(condition);
	}

	@PostMapping("/search")
	public TransactionSearchResponse search(Authentication authentication,
			@RequestBody TransactionSearchRequest request) {
		accessGuard.requireTransactionRead(authentication);
		return transactionService.search(request);
	}

	/**
	 * 聚合统计 —— 支持按字段分组 + COUNT。
	 * body: {"condition": {...}, "groupBy": ["transType"], "metrics": ["COUNT"]}
	 * 无 groupBy 时返回全局聚合（totalCount, totalAmount, avgAmount, minAmount, maxAmount）。
	 */
	@PostMapping("/aggregate")
	public Map<String, Object> aggregate(Authentication authentication, @RequestBody AggregateRequest request) {
		accessGuard.requireUser(authentication);
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
