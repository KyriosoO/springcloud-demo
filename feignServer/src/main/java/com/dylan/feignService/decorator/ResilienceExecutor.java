package com.dylan.feignService.decorator;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

public interface ResilienceExecutor {
	Logger log = LoggerFactory.getLogger(ResilienceExecutor.class);

	<T> T execute(ResilienceCommand<T> command);
}
