package com.dylan.mqConsumerServer.trans.mapper;

import java.util.List;

import com.dylan.common.model.trans.Transaction;
import com.dylan.common.model.trans.TransactionLog;
import com.dylan.common.model.trans.TransactionLogArchive;

//@Mapper
public interface TransactionMapper {
	public void save(List<TransactionLogArchive> list);

	public void deleteProcessed();

	public void saveBatch();

	public List<TransactionLog> findAll();

	public void insertAll(List<Transaction> list);

	public void updateAll(List<Transaction> list);
}
