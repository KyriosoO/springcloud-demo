package com.dylan.mqprocedureserver.mapper;

import java.util.List;
import java.util.Map;

import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;

import com.dylan.transaction.api.model.Transaction;

@Mapper
public interface TransactionMapper {
	public List<Transaction> fetchAll();

	public List<Transaction> query(Transaction condition);

	public Map<String, Object> aggregate(Transaction condition);

	/**
	 * 动态聚合 —— Service 层已验证 selectClause 和 groupByClause，确保安全。
	 * @param condition 过滤条件
	 * @param selectClause 已校验的 SELECT 子句（列名 + 聚合函数）
	 * @param groupByClause 已校验的 GROUP BY 子句，null 表示无分组
	 */
	public List<Map<String, Object>> aggregateDynamic(
			@Param("condition") Transaction condition,
			@Param("selectClause") String selectClause,
			@Param("groupByClause") String groupByClause);

	public int insert(Transaction transaction);

	public int update(Transaction transaction);

	public int deleteByTransId(String transId);

	public Transaction findByTransId(String transId);
}
