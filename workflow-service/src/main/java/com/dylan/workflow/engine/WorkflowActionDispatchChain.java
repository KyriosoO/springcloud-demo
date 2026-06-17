package com.dylan.workflow.engine;

import java.util.List;
import java.util.Map;
import java.util.ArrayList;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.Executor;
import java.util.function.Function;
import java.util.stream.Collectors;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.stereotype.Component;

import com.dylan.workflow.config.WorkflowActionProperties;
import com.dylan.workflow.model.WorkflowOutboxEvent;

/**
 * 按配置并发执行多个动作分发器。
 */
@Component
public class WorkflowActionDispatchChain {
	private static final Logger log = LoggerFactory.getLogger(WorkflowActionDispatchChain.class);

	private final WorkflowActionProperties properties;
	private final Map<String, WorkflowActionDispatcher> dispatchers;
	private final Executor executor;

	public WorkflowActionDispatchChain(WorkflowActionProperties properties, List<WorkflowActionDispatcher> dispatchers,
			@Qualifier("workflowAsyncExecutor") Executor executor) {
		this.properties = properties;
		this.dispatchers = dispatchers.stream()
				.collect(Collectors.toMap(WorkflowActionDispatcher::name, Function.identity()));
		this.executor = executor;
	}

	public void dispatch(WorkflowOutboxEvent event) {
		List<String> missingDispatchers = new ArrayList<>();
		List<CompletableFuture<DispatchResult>> futures = new ArrayList<>();
		for (String dispatcherName : properties.getDispatchers()) {
			WorkflowActionDispatcher dispatcher = dispatchers.get(dispatcherName);
			if (dispatcher == null) {
				missingDispatchers.add(dispatcherName);
				continue;
			}
			futures.add(CompletableFuture.supplyAsync(() -> dispatch(dispatcher, event), executor));
		}

		List<String> failedDispatchers = new ArrayList<>(missingDispatchers);
		for (CompletableFuture<DispatchResult> future : futures) {
			DispatchResult result = future.join();
			if (!result.success()) {
				failedDispatchers.add(result.dispatcherName());
				log.error("Workflow action dispatcher failed, dispatcherName={}, eventId={}", result.dispatcherName(),
						event.getEventId(), result.error());
			}
		}
		if (!failedDispatchers.isEmpty()) {
			throw new WorkflowActionDispatchException(failedDispatchers);
		}
	}

	private DispatchResult dispatch(WorkflowActionDispatcher dispatcher, WorkflowOutboxEvent event) {
		try {
			dispatcher.dispatch(event);
			return new DispatchResult(dispatcher.name(), true, null);
		} catch (RuntimeException e) {
			return new DispatchResult(dispatcher.name(), false, e);
		}
	}

	private record DispatchResult(String dispatcherName, boolean success, RuntimeException error) {
	}
}
