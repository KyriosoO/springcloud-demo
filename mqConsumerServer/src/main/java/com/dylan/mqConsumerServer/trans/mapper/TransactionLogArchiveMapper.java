package com.dylan.mqConsumerServer.trans.mapper;

import org.apache.ibatis.annotations.Mapper;

import com.dylan.common.model.trans.TransactionLogArchive;

@Mapper
public interface TransactionLogArchiveMapper {
	public void save(TransactionLogArchive archive);
}
