package com.dylan.esquery.service;

import java.util.List;

/** 文档读取 alias 回滚 dry-run 结果，不执行 alias 写操作。 */
public record AliasRollbackDryRunResult(
		String alias,
		List<String> currentIndexes,
		String targetIndex,
		String expectedPreviousIndex,
		boolean ready) {
}
