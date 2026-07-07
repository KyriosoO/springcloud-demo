package com.dylan.esquery.controller;

import com.dylan.esquery.api.model.AliasSwitchRequest;
import com.dylan.esquery.api.model.RebuildRequest;
import com.dylan.esquery.api.model.RebuildTask;
import com.dylan.esquery.config.EsQueryProperties;
import com.dylan.esquery.service.EsDocumentService;
import com.dylan.esquery.service.EsIndexAliasService;
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

class EsQueryControllerManagementAccessTest {

	@Test
	void rejectsFullRebuildWithoutManagementServiceToken() {
		IndexRebuildService rebuildService = mock(IndexRebuildService.class);
		EsQueryController controller = controller(rebuildService, mock(EsIndexAliasService.class),
				mock(RebuildTaskRepository.class), "local-token");

		assertThatThrownBy(() -> controller.fullRebuild("agent-doc-policy", new RebuildRequest(), null))
				.isInstanceOfSatisfying(ResponseStatusException.class, ex ->
						assertThat(ex.getStatusCode()).isEqualTo(HttpStatus.FORBIDDEN));
		verifyNoInteractions(rebuildService);
	}

	@Test
	void acceptsFullRebuildWithManagementServiceToken() {
		IndexRebuildService rebuildService = mock(IndexRebuildService.class);
		RebuildRequest request = new RebuildRequest();
		RebuildTask task = new RebuildTask();
		task.setTaskId("task-1");
		when(rebuildService.submitFullRebuild("agent-doc-policy", request)).thenReturn(task);
		EsQueryController controller = controller(rebuildService, mock(EsIndexAliasService.class),
				mock(RebuildTaskRepository.class), "local-token");

		RebuildTask response = controller.fullRebuild("agent-doc-policy", request, "local-token");

		assertThat(response.getTaskId()).isEqualTo("task-1");
		verify(rebuildService).submitFullRebuild("agent-doc-policy", request);
	}

	@Test
	void rejectsAliasSwitchWithoutConfiguredManagementServiceToken() {
		EsIndexAliasService aliasService = mock(EsIndexAliasService.class);
		EsQueryController controller = controller(mock(IndexRebuildService.class), aliasService,
				mock(RebuildTaskRepository.class), null);

		assertThatThrownBy(() -> controller.switchReadAlias("agent-doc-policy", new AliasSwitchRequest(), "any-token"))
				.isInstanceOfSatisfying(ResponseStatusException.class, ex ->
						assertThat(ex.getStatusCode()).isEqualTo(HttpStatus.FORBIDDEN));
		verifyNoInteractions(aliasService);
	}

	private EsQueryController controller(
			IndexRebuildService rebuildService,
			EsIndexAliasService aliasService,
			RebuildTaskRepository taskRepository,
			String managementServiceToken) {
		EsQueryProperties properties = new EsQueryProperties();
		properties.setTotalHitsThreshold(10000);
		properties.setManagementServiceToken(managementServiceToken);
		return new EsQueryController(
				mock(EsDocumentService.class),
				rebuildService,
				taskRepository,
				aliasService,
				new EsManagementAccessGuard(properties));
	}
}
