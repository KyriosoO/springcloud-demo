package com.dylan.esquery.controller;

import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.Authentication;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import com.dylan.esquery.api.knowledge.KnowledgeSearchRequest;
import com.dylan.esquery.api.knowledge.KnowledgeSearchResponse;
import com.dylan.esquery.service.KnowledgeReadAccessGuard;
import com.dylan.esquery.service.KnowledgeReadDecision;
import com.dylan.esquery.service.KnowledgeSearchService;
import com.dylan.esquery.web.KnowledgeSearchJsonCodec;

@RestController
@RequestMapping("/es/knowledge")
@ConditionalOnProperty(prefix = "es.query.knowledge", name = "enabled", havingValue = "true")
public class KnowledgeSearchController {
	private final KnowledgeSearchJsonCodec codec;
	private final KnowledgeReadAccessGuard accessGuard;
	private final KnowledgeSearchService searchService;

	public KnowledgeSearchController(KnowledgeSearchJsonCodec codec,
			KnowledgeReadAccessGuard accessGuard, KnowledgeSearchService searchService) {
		this.codec = codec;
		this.accessGuard = accessGuard;
		this.searchService = searchService;
	}

	@PostMapping(value = "/search", consumes = MediaType.APPLICATION_JSON_VALUE,
			produces = MediaType.APPLICATION_JSON_VALUE)
	public ResponseEntity<KnowledgeSearchResponse> search(Authentication authentication,
			@RequestBody byte[] body) {
		KnowledgeSearchRequest request = codec.decodeRequest(body);
		KnowledgeReadDecision decision = accessGuard.authorize(authentication,
				request.logicalDomainId(), request.retrievalProfileId());
		return ResponseEntity.ok(searchService.search(request, decision));
	}
}
