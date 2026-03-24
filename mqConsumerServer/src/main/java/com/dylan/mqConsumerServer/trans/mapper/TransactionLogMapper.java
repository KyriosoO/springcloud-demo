package com.dylan.mqConsumerServer.trans.mapper;

import java.util.Set;

import org.apache.ibatis.annotations.Mapper;

import com.dylan.common.model.trans.TransactionLog;

@Mapper
public interface TransactionLogMapper {
	public void save(TransactionLog transactionLog);

	public Set<String> fetchNewTransByIdentityAsSet();

	public void clear(TransactionLog transactionLog);

	public void saveException(TransactionLog transactionLog);

}