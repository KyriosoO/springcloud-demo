package com.dylan.agent.controller;

import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import com.dylan.agent.api.request.AgentChatRequest;
import com.dylan.agent.api.response.AgentChatResponse;
import com.dylan.agent.application.AgentOrchestrator;
import com.dylan.agent.model.AgentUserContext;
import com.dylan.agent.security.AgentUserContextResolver;

import jakarta.validation.Valid;

/**
 * Agent 聊天 Controller。
 * 只负责 Bean Validation、JWT 解析和调用 Orchestrator。
 */
@RestController
@RequestMapping("/agent")
public class AgentChatController {

    private final AgentOrchestrator orchestrator;
    private final AgentUserContextResolver userContextResolver;

    public AgentChatController(AgentOrchestrator orchestrator, AgentUserContextResolver userContextResolver) {
        this.orchestrator = orchestrator;
        this.userContextResolver = userContextResolver;
    }

    /** 接收 Agent 聊天请求，解析 JWT 用户上下文，委托 AgentOrchestrator 处理。 */
    @PostMapping("/chat")
    public AgentChatResponse chat(@AuthenticationPrincipal Jwt jwt,
                                  @Valid @RequestBody AgentChatRequest request) {
        AgentUserContext userContext = userContextResolver.resolve(jwt);
        return orchestrator.chat(userContext, request);
    }
}
