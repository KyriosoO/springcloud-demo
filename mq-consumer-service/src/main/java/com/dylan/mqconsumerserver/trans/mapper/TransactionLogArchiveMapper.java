package com.dylan.mqconsumerserver.trans.mapper;

import org.apache.ibatis.annotations.Mapper;

import com.dylan.transaction.api.model.TransactionLogArchive;

@Mapper
public interface TransactionLogArchiveMapper {
	public void save(TransactionLogArchive archive);
}
