package com.dylan.mqProcedureServer.mapper;

import java.util.List;

import org.apache.ibatis.annotations.Mapper;

import com.dylan.common.model.trans.Transaction;

@Mapper
public interface TransactionMapper {
	public List<Transaction> fetchAll();
}
