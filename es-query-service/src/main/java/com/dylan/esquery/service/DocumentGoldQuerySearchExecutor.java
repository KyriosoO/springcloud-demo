package com.dylan.esquery.service;

import com.dylan.esquery.api.model.HybridSearchRequest;

import java.io.IOException;
import java.util.List;

/** gold query 批跑检索执行端口。 */
public interface DocumentGoldQuerySearchExecutor {

	List<String> searchDocumentIds(String indexAlias, HybridSearchRequest request) throws IOException;
}
