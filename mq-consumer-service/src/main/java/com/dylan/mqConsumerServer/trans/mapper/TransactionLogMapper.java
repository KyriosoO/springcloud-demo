package com.dylan.mqconsumerserver.trans.mapper;

import java.util.Set;

import org.apache.ibatis.annotations.Mapper;

import com.dylan.transaction.api.model.TransactionLog;

@Mapper
public interface TransactionLogMapper {
	public void save(TransactionLog transactionLog);

	public Set<String> fetchNewTransByIdentityAsSet();

	public void clear(TransactionLog transactionLog);

	public void saveException(TransactionLog transactionLog);

}