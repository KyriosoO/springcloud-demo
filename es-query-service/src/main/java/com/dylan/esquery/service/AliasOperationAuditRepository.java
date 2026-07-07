package com.dylan.esquery.service;

import java.util.List;

/** 文档 alias 操作审计与回滚历史仓储端口。 */
public interface AliasOperationAuditRepository {

	void record(AliasOperationAudit audit);

	List<AliasOperationAudit> findAll();

	boolean hasTrustedTarget(String alias, String targetIndex);
}
