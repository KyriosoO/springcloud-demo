package com.dylan.mqConsumerServer.trans.mapper;

import java.util.List;

import com.dylan.common.model.trans.TransactionLogArchive;

//@Mapper
public interface TransactionLogArchiveMapper {
	public void save(List<TransactionLogArchive> list);

	public void deleteProcessed();
}
