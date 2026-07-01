package com.dylan.mqconsumerserver.trans.mapper;


import org.apache.ibatis.annotations.Mapper;

import com.dylan.transaction.api.model.Transaction;

@Mapper
public interface TransactionMapper {

	public void insertTransaction(Transaction transaction);

	public void updateTransaction(Transaction transaction);
	
}
