package com.dylan.esquery.service;

import java.util.ArrayList;
import java.util.Collections;
import java.util.List;

final class InMemoryAliasOperationAuditRepository implements AliasOperationAuditRepository {

	private final List<AliasOperationAudit> audits = Collections.synchronizedList(new ArrayList<>());

	@Override
	public void record(AliasOperationAudit audit) {
		audits.add(audit);
	}

	@Override
	public List<AliasOperationAudit> findAll() {
		synchronized (audits) {
			return List.copyOf(audits);
		}
	}

	@Override
	public boolean hasTrustedTarget(String alias, String targetIndex) {
		synchronized (audits) {
			return audits.stream()
					.filter(audit -> alias.equals(audit.alias()))
					.filter(audit -> "SUCCESS".equals(audit.result()) || "IDEMPOTENT".equals(audit.result()))
					.anyMatch(audit -> audit.fromIndexes().contains(targetIndex) || targetIndex.equals(audit.toIndex()));
		}
	}
}
