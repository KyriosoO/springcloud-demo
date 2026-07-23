package com.dylan.esquery.controller;

import com.dylan.esquery.api.model.RebuildRequest;
import com.dylan.esquery.api.model.RebuildTask;
import com.dylan.esquery.config.EsQueryProperties;
import com.dylan.esquery.service.EsDocumentService;
import com.dylan.esquery.service.EsManagementAccessGuard;
import com.dylan.esquery.service.IndexRebuildService;
import com.dylan.esquery.service.RebuildTaskRepository;
import org.junit.jupiter.api.Test;
import org.springframework.http.HttpStatus;
import org.springframework.web.server.ResponseStatusException;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyNoInteractions;
import static org.mockito.Mockito.when;

class EsQueryControllerAccessTest {

	@Test
	void rejectsRebuildWithoutManagementServiceToken() {
		IndexRebuildService rebuildService = mock(IndexRebuildService.class);
		EsQueryController controller = controller(rebuildService, "local-token");

		assertThatThrownBy(() -> controller.fullRebuild("orders", new RebuildRequest(), null))
				.isInstanceOfSatisfying(ResponseStatusException.class, ex ->
						assertThat(ex.getStatusCode()).isEqualTo(HttpStatus.FORBIDDEN));
		verifyNoInteractions(rebuildService);
	}

	@Test
	void acceptsRebuildWithManagementServiceToken() {
		IndexRebuildService rebuildService = mock(IndexRebuildService.class);
		RebuildRequest request = new RebuildRequest();
		RebuildTask task = new RebuildTask();
		task.setTaskId("task-1");
		when(rebuildService.submitFullRebuild("orders", request)).thenReturn(task);
		EsQueryController controller = controller(rebuildService, "local-token");

		assertThat(controller.fullRebuild("orders", request, "local-token").getTaskId()).isEqualTo("task-1");
		verify(rebuildService).submitFullRebuild("orders", request);
	}

	private static EsQueryController controller(IndexRebuildService rebuildService, String managementToken) {
		EsQueryProperties properties = new EsQueryProperties();
		properties.setManagementServiceToken(managementToken);
		return new EsQueryController(
				mock(EsDocumentService.class),
				rebuildService,
				mock(RebuildTaskRepository.class),
				new EsManagementAccessGuard(properties));
	}
}
