package com.dylan.mqConsumerServer.trans.mapper;


import org.apache.ibatis.annotations.Mapper;

import com.dylan.common.model.trans.Transaction;

@Mapper
public interface TransactionMapper {

	public void insertTransaction(Transaction transaction);

	public void updateTransaction(Transaction transaction);
	
}
