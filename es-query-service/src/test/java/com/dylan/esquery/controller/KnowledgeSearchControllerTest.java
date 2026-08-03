package com.dylan.esquery.controller;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.inOrder;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

import java.util.List;

import org.junit.jupiter.api.Test;
import org.mockito.InOrder;

import com.dylan.esquery.api.knowledge.KnowledgeSearchRequest;
import com.dylan.esquery.api.knowledge.KnowledgeSearchResponse;
import com.dylan.esquery.service.KnowledgeReadAccessGuard;
import com.dylan.esquery.service.KnowledgeReadDecision;
import com.dylan.esquery.service.KnowledgeSearchService;
import com.dylan.esquery.web.KnowledgeSearchJsonCodec;

class KnowledgeSearchControllerTest {

	@Test
	void decodesThenAuthorizesBeforeSearching() {
		KnowledgeSearchJsonCodec codec = mock(KnowledgeSearchJsonCodec.class);
		KnowledgeReadAccessGuard guard = mock(KnowledgeReadAccessGuard.class);
		KnowledgeSearchService service = mock(KnowledgeSearchService.class);
		KnowledgeSearchRequest request = new KnowledgeSearchRequest(
				1, "tax.policy", "tax-policy-v1", "keyword", "q", null, 20);
		KnowledgeReadDecision decision = new KnowledgeReadDecision(
				"tax.policy", "tax-policy-v1", "v1", "p1", "decision");
		KnowledgeSearchResponse response = new KnowledgeSearchResponse(
				1, "tax.policy", "tax-policy-v1", "keyword", "v1", "0".repeat(64), "p1", false, List.of());
		byte[] body = new byte[] { 1 };
		when(codec.decodeRequest(body)).thenReturn(request);
		when(guard.authorize(null, "tax.policy", "tax-policy-v1")).thenReturn(decision);
		when(service.search(request, decision)).thenReturn(response);

		KnowledgeSearchController controller = new KnowledgeSearchController(codec, guard, service);
		assertThat(controller.search(null, body).getBody()).isSameAs(response);
		InOrder order = inOrder(codec, guard, service);
		order.verify(codec).decodeRequest(body);
		order.verify(guard).authorize(null, "tax.policy", "tax-policy-v1");
		order.verify(service).search(request, decision);
	}
}
