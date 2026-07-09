package com.dylan.esquery.service;

import com.dylan.esquery.api.model.HybridSearchHit;
import com.dylan.esquery.api.model.HybridSearchRequest;
import org.springframework.stereotype.Component;

import java.io.IOException;
import java.util.List;

/** 基于真实 HybridSearch 执行 gold query 样本。 */
@Component
public class EsDocumentGoldQuerySearchExecutor implements DocumentGoldQuerySearchExecutor {

	private final EsDocumentService esDocumentService;

	public EsDocumentGoldQuerySearchExecutor(EsDocumentService esDocumentService) {
		this.esDocumentService = esDocumentService;
	}

	@Override
	public List<String> searchDocumentIds(String indexAlias, HybridSearchRequest request) throws IOException {
		var response = esDocumentService.hybridSearch(indexAlias, request);
		if (response.getHits() == null) {
			return List.of();
		}
		return response.getHits().stream()
				.map(HybridSearchHit::getDocumentId)
				.filter(value -> value != null && !value.isBlank())
				.distinct()
				.toList();
	}
}
