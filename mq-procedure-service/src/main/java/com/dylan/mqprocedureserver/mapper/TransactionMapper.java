package com.dylan.mqprocedureserver.mapper;

import java.util.List;
import java.util.Map;

import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;

import com.dylan.transaction.api.model.Transaction;

@Mapper
public interface TransactionMapper {
	public List<Transaction> fetchAll();

	public Transaction findByCondition(Transaction condition);


	default List<Transaction> query(Transaction condition, Integer offset, Integer size) {
		return query(condition, offset, size, null);
	}

	public List<Transaction> query(
			@Param("condition") Transaction condition,
			@Param("offset") Integer offset,
			@Param("size") Integer size,
			@Param("orderByClause") String orderByClause);

	public long countUpTo(
			@Param("condition") Transaction condition,
			@Param("limit") int limit);

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

}
