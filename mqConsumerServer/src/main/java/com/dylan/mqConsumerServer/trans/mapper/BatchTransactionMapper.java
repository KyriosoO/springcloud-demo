package com.dylan.mqConsumerServer.trans.mapper;

import java.util.List;

//@Mapper
public interface BatchTransactionMapper {

	public void save(List<Long> seqNo);

	public void deleteAll();
}
