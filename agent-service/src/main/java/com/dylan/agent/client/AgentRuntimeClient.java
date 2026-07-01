package com.dylan.agent.client;

import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.InputStream;

import org.springframework.http.HttpStatus;
import org.springframework.http.HttpStatusCode;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestClient;

import com.dylan.agent.api.request.PlanGenerateRequest;
import com.dylan.agent.api.response.PlanGenerateResponse;
import com.dylan.agent.api.response.RuntimeErrorResponse;
import com.dylan.agent.config.AgentProperties;
import com.dylan.agent.exception.AgentPlanValidationException;
import com.dylan.agent.exception.AgentRuntimeException;
import com.fasterxml.jackson.core.JsonParseException;
import com.fasterxml.jackson.databind.JsonMappingException;
import com.fasterxml.jackson.databind.ObjectMapper;

/**
 * Runtime HTTP Client，使用独立 RestClient。
 * 不转发用户 JWT，使用 X-Agent-Runtime-Key 内部共享密钥。
 */
@Component
public class AgentRuntimeClient {

    private final RestClient restClient;
    private final ObjectMapper objectMapper;
    private final AgentProperties properties;

    public AgentRuntimeClient(RestClient agentRuntimeRestClient, ObjectMapper objectMapper, AgentProperties properties) {
        this.restClient = agentRuntimeRestClient;
        this.objectMapper = objectMapper;
        this.properties = properties;
    }

    /** 调用 Runtime /plans/generate 端点，发送 PlanGenerateRequest，返回 PlanGenerateResponse。使用独立 RestClient 和共享密钥认证。 */
    public PlanGenerateResponse generate(PlanGenerateRequest request) {
        try {
            return restClient.post()
                    .uri("/runtime/v1/plans/generate")
                    .header("X-Agent-Runtime-Key", properties.getRuntime().getSharedKey())
                    .body(request)
                    .exchange((httpRequest, response) -> {
                        byte[] responseBytes = readLimited(
                                response.getBody(),
                                properties.getRuntime().getMaxResponseBytes());
                        HttpStatusCode status = response.getStatusCode();
                        if (status.is2xxSuccessful()) {
                            return parseSuccess(responseBytes);
                        }
                        throw mapError(status, responseBytes, request.getRequestId());
                    });
        } catch (AgentRuntimeException | AgentPlanValidationException e) {
            throw e;
        } catch (Exception e) {
            throw new AgentRuntimeException("调用 Runtime 失败。", e);
        }
    }

    private PlanGenerateResponse parseSuccess(byte[] responseBytes) {
        if (responseBytes == null || responseBytes.length == 0) {
            throw new AgentRuntimeException("Runtime 返回空响应。");
        }

        try {
            return objectMapper.readValue(responseBytes, PlanGenerateResponse.class);
        } catch (JsonParseException e) {
            throw new AgentRuntimeException("Runtime 返回非法 JSON。", e);
        } catch (JsonMappingException e) {
            throw new AgentPlanValidationException("Runtime 响应不符合契约。");
        } catch (IOException e) {
            throw new AgentRuntimeException("读取 Runtime 响应失败。", e);
        }
    }

    private RuntimeException mapError(HttpStatusCode status, byte[] responseBytes, String expectedRequestId) {
        RuntimeErrorResponse error = parseError(responseBytes);
        if (error.getRequestId() != null && !error.getRequestId().isBlank()
                && !error.getRequestId().equals(expectedRequestId)) {
            return new AgentRuntimeException("Runtime 错误响应 requestId 不匹配。");
        }

        String code = error.getCode();
        if (status == HttpStatus.UNPROCESSABLE_ENTITY && "RUNTIME_PLAN_INVALID".equals(code)) {
            return new AgentPlanValidationException("Runtime Plan 校验失败。");
        }
        if (status == HttpStatus.BAD_REQUEST && "RUNTIME_INVALID_REQUEST".equals(code)) {
            return new AgentRuntimeException("Runtime 请求契约错误。");
        }
        if ((status == HttpStatus.UNAUTHORIZED || status == HttpStatus.FORBIDDEN)
                && "RUNTIME_AUTH_ERROR".equals(code)) {
            return new AgentRuntimeException("Runtime 鉴权失败，请检查 shared key 配置。");
        }
        if (status == HttpStatus.BAD_GATEWAY && "RUNTIME_PROVIDER_ERROR".equals(code)) {
            return new AgentRuntimeException("Runtime Provider 不可用。");
        }
        if (status == HttpStatus.GATEWAY_TIMEOUT && "RUNTIME_TIMEOUT".equals(code)) {
            return new AgentRuntimeException("Runtime 调用 LLM 超时。");
        }
        return new AgentRuntimeException("Runtime 返回未知错误。");
    }

    private RuntimeErrorResponse parseError(byte[] responseBytes) {
        if (responseBytes == null || responseBytes.length == 0) {
            throw new AgentRuntimeException("Runtime 返回空错误响应。");
        }
        try {
            RuntimeErrorResponse error = objectMapper.readValue(responseBytes, RuntimeErrorResponse.class);
            if (error.getCode() == null || error.getCode().isBlank()
                    || error.getMessage() == null || error.getMessage().isBlank()) {
                throw new AgentRuntimeException("Runtime 错误响应不符合契约。");
            }
            return error;
        } catch (JsonParseException | JsonMappingException e) {
            throw new AgentRuntimeException("Runtime 错误响应不符合契约。", e);
        } catch (IOException e) {
            throw new AgentRuntimeException("读取 Runtime 错误响应失败。", e);
        }
    }

    private byte[] readLimited(InputStream input, int maxBytes) throws IOException {
        if (input == null) {
            return new byte[0];
        }
        try (input; ByteArrayOutputStream output = new ByteArrayOutputStream(Math.min(maxBytes, 8192))) {
            byte[] buffer = new byte[4096];
            int total = 0;
            int read;
            while ((read = input.read(buffer)) != -1) {
                total += read;
                if (total > maxBytes) {
                    throw new AgentRuntimeException("Runtime 响应超过大小上限。");
                }
                output.write(buffer, 0, read);
            }
            return output.toByteArray();
        }
    }
}
