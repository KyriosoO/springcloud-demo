package com.dylan.employee.approval;

import org.springframework.cloud.openfeign.FeignClient;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;

import com.dylan.workflow.model.WorkflowRequest;
import com.dylan.workflow.web.WorkflowSubmitResponse;

@FeignClient(name = "workflow-service", path = "/workflows")
public interface WorkflowClient {
	@PostMapping
	WorkflowSubmitResponse submit(@RequestBody WorkflowRequest request);
}
