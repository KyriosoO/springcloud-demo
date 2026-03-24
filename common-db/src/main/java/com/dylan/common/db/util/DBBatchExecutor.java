package com.dylan.common.db.util;

import java.util.List;
import java.util.function.BiConsumer;

import org.apache.ibatis.session.ExecutorType;
import org.apache.ibatis.session.SqlSession;
import org.apache.ibatis.session.SqlSessionFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.dao.DuplicateKeyException;
import org.springframework.stereotype.Component;

@Component
public class DBBatchExecutor {
	@Autowired
	SqlSessionFactory sqlSessionFactory;
	private int batchSize;

	public DBBatchExecutor() {
		this.batchSize = 100;
	}

	/**
	 * 批量执行任意 Mapper 方法
	 *
	 * @param list        待处理数据列表
	 * @param mapperClass Mapper 接口 Class
	 * @param consumer    (mapper, item) -> mapper.insertXXX(item) 或
	 *                    mapper.updateXXX(item)
	 * @param <T>         数据类型
	 * @param <M>         Mapper 类型
	 */
	public <T, M> void executeBatch(List<T> list, Class<M> mapperClass, BiConsumer<M, T> consumer) {
		if (list == null || list.isEmpty())
			return;
		try (SqlSession session = sqlSessionFactory.openSession(ExecutorType.BATCH, false)) {
			M mapper = session.getMapper(mapperClass);

			int count = 0;
			for (T item : list) {
				consumer.accept(mapper, item);
				count++;
				// 每 batchSize 条提交一次，避免 SQL 太长或参数过多
				if (count % batchSize == 0) {
					session.flushStatements();
					session.clearCache();
				}
			}
			// 提交剩余的
			session.flushStatements();
			session.commit();
		} catch (Exception e) {
			throw e;
		}
	}

	public void setBatchSize(int batchSize) {
		this.batchSize = batchSize;
	}
}