package com.dylan.agent.service.e2e;

import static org.assertj.core.api.Assertions.assertThat;

import java.io.IOException;
import java.net.HttpURLConnection;
import java.net.ServerSocket;
import java.net.URI;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.time.Duration;
import java.time.Instant;
import java.util.List;
import java.util.Map;
import java.util.concurrent.TimeUnit;
import java.util.function.BooleanSupplier;

import com.dylan.agent.service.AgentServiceApplication;
import com.dylan.common.security.SecurityTokenUtils;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;

import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.condition.EnabledIfEnvironmentVariable;
import org.springframework.boot.builder.SpringApplicationBuilder;
import org.springframework.boot.test.context.TestConfiguration;
import org.springframework.boot.web.reactive.context.ReactiveWebServerApplicationContext;
import org.springframework.context.annotation.Bean;
import org.springframework.http.MediaType;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.security.oauth2.jwt.JwtException;
import org.springframework.security.oauth2.jwt.ReactiveJwtDecoder;
import org.springframework.test.web.reactive.server.WebTestClient;

import reactor.core.publisher.Mono;

@EnabledIfEnvironmentVariable(named = "RUN_BUSINESS_QUERY_PLAN_NONLIVE_E2E", matches = "1")
class AgentBusinessQueryPlanNonLiveE2ETest {
    private static final String ADMIN_TOKEN = "synthetic-admin-token";
    private static final String DENIED_TOKEN = "synthetic-denied-token";
    private static final Path DEFAULT_PYTHON = Path.of(
            "..", ".tmp", "agent-runtime-venv", "Scripts", "python.exe").toAbsolutePath().normalize();
    private static final Path RUNTIME_ROOT = Path.of("..", "agent-runtime").toAbsolutePath().normalize();

    private final ObjectMapper objectMapper = new ObjectMapper();
    private Process runtimeProcess;
    private Path runtimeStopPath;
    private Path runtimeLogPath;
    private Path evidencePath;
    private Path runRoot;
    private ReactiveWebServerApplicationContext springContext;

    @Test
    void verifiesSpringRuntimeFakeModelAndFakeDomainsUseOnlyQueryPlanPath() throws Exception {
        int runtimePort = freePort();
        runRoot = Files.createTempDirectory("business-query-plan-nonlive-");
        runtimeStopPath = runRoot.resolve("runtime.stop");
        runtimeLogPath = runRoot.resolve("runtime.log");
        evidencePath = runRoot.resolve("evidence.json");
        startRuntime(runtimePort);
        await("Runtime liveness", () -> runtimeHealth(runtimePort, "live"));
        await("Runtime readiness", () -> runtimeHealth(runtimePort, "ready"));
        WebTestClient client = startSpring(runtimePort);
        await("Spring readiness", () -> springReady(client));

        assertOutcome(client, ADMIN_TOKEN, "bq-nonlive-emp-ok", "查询员工详情 员工标识=ABCDE",
                200, "success", "employee.detail", null);
        assertOutcome(client, DENIED_TOKEN, "bq-nonlive-emp-deny", "查询员工详情 员工标识=ABCDE",
                403, "forbidden", "employee.detail", "business.downstream_forbidden");
        assertOutcome(client, ADMIN_TOKEN, "bq-nonlive-txn-ok", "查询交易 金额=1.00",
                200, "success", "transaction.search", null);
        assertOutcome(client, DENIED_TOKEN, "bq-nonlive-txn-deny", "查询交易 金额=1.00",
                403, "forbidden", "transaction.search", "business.downstream_forbidden");
        assertOutcome(client, ADMIN_TOKEN, "bq-nonlive-invalid", "查询交易 金额=1.000",
                400, "invalid_argument", null, "business.plan_invalid");
        assertOutcome(client, ADMIN_TOKEN, "bq-nonlive-unsupported", "查询员工列表 工作地=上海",
                422, "unsupported", null, "business.plan_unsupported");
        assertOutcome(client, ADMIN_TOKEN, "bq-nonlive-second", "查询员工 第二动作",
                400, "invalid_argument", null, "business.plan_invalid");
        assertOutcome(client, ADMIN_TOKEN, "bq-nonlive-cross", "查询员工 跨域计划",
                422, "unsupported", null, "business.plan_unsupported");
        assertOutcome(client, ADMIN_TOKEN, "bq-nonlive-timeout", "查询交易 模型超时",
                504, "timeout", null, "business.plan_model_timeout");
        assertOutcome(client, ADMIN_TOKEN, "bq-nonlive-sensitive", "查询员工 联系电话 13800138000",
                403, "forbidden", null, "business.plan_input_denied");

        stopSpring();
        stopRuntime();
        assertThat(Files.isRegularFile(evidencePath)).isTrue();
        JsonNode evidence = objectMapper.readTree(evidencePath.toFile());
        assertThat(evidence.path("status").asText()).isEqualTo("passed");
        JsonNode counts = evidence.path("requestCounts");
        assertThat(counts.path("queryPlanModel").asInt()).isEqualTo(9);
        assertThat(counts.path("employee").asInt()).isEqualTo(2);
        assertThat(counts.path("transaction").asInt()).isEqualTo(2);
        assertThat(counts.path("otherModelTasks").asInt()).isZero();
        assertThat(counts.path("otherBusinessEndpoints").asInt()).isZero();
        assertThat(counts.path("fallbackSelector").asInt()).isZero();
        assertThat(counts.path("answerGeneration").asInt()).isZero();
        assertThat(counts.path("externalModelOutbound").asInt()).isZero();
        assertThat(evidence.path("cases").size()).isEqualTo(10);
        String finiteEvidence = Files.readString(evidencePath, StandardCharsets.UTF_8);
        String runtimeLog = Files.exists(runtimeLogPath)
                ? Files.readString(runtimeLogPath, StandardCharsets.UTF_8)
                : "";
        assertThat(finiteEvidence).doesNotContain("ABCDE", "13800138000", ADMIN_TOKEN, DENIED_TOKEN);
        assertThat(runtimeLog).doesNotContain("ABCDE", "13800138000", ADMIN_TOKEN, DENIED_TOKEN);
    }

    private WebTestClient startSpring(int runtimePort) {
        springContext = (ReactiveWebServerApplicationContext) new SpringApplicationBuilder(
                AgentServiceApplication.class, TestAuthenticationConfiguration.class)
                .run(
                        "--server.port=0",
                        "--spring.main.web-application-type=reactive",
                        "--spring.cloud.config.enabled=false",
                        "--spring.config.import=",
                        "--agent.runtime.base-url=http://127.0.0.1:" + runtimePort,
                        "--spring.autoconfigure.exclude=com.dylan.common.security.JwtConfig,com.dylan.common.security.ReactiveResourceServerSecurityAutoConfiguration");
        return WebTestClient.bindToServer()
                .baseUrl("http://127.0.0.1:" + springContext.getWebServer().getPort())
                .responseTimeout(Duration.ofSeconds(15))
                .build();
    }

    private void assertOutcome(
            WebTestClient client,
            String token,
            String caseId,
            String question,
            int httpStatus,
            String status,
            String capabilityId,
            String failureCode) {
        WebTestClient.BodyContentSpec body = client.post().uri("/api/v1/agent/queries")
                .header("Authorization", "Bearer " + token)
                .header("X-Correlation-Id", caseId)
                .contentType(MediaType.APPLICATION_JSON)
                .bodyValue(Map.of("question", question))
                .exchange()
                .expectStatus().isEqualTo(httpStatus)
                .expectBody()
                .jsonPath("$.status").isEqualTo(status)
                .jsonPath("$.correlationId").isEqualTo(caseId);
        if (capabilityId != null) {
            body.jsonPath("$.capabilityId").isEqualTo(capabilityId);
        } else {
            body.jsonPath("$.capabilityId").doesNotExist();
        }
        if (failureCode != null) {
            body.jsonPath("$.error.code").isEqualTo(failureCode);
        } else {
            body.jsonPath("$.error").doesNotExist();
        }
    }

    private void startRuntime(int runtimePort) throws IOException {
        Path python = configuredPython();
        assertThat(Files.isExecutable(python)).isTrue();
        ProcessBuilder builder = new ProcessBuilder(
                python.toString(), "-m", "tests.system_e2e.business_query_plan_runtime_server")
                .directory(RUNTIME_ROOT.toFile())
                .redirectErrorStream(true)
                .redirectOutput(runtimeLogPath.toFile());
        builder.environment().put("AGENT_RUNTIME_HOST", "127.0.0.1");
        builder.environment().put("AGENT_RUNTIME_PORT", Integer.toString(runtimePort));
        builder.environment().put("AGENT_MODEL_PROVIDER", "stub");
        builder.environment().put("PYTHONPATH", "src" + java.io.File.pathSeparator + ".");
        builder.environment().put("BUSINESS_QUERY_PLAN_E2E_EVIDENCE_PATH", evidencePath.toString());
        builder.environment().put("BUSINESS_QUERY_PLAN_E2E_STOP_PATH", runtimeStopPath.toString());
        builder.environment().put("BUSINESS_QUERY_PLAN_E2E_ADMIN_TOKEN", ADMIN_TOKEN);
        builder.environment().remove("LLM_API_KEY");
        runtimeProcess = builder.start();
    }

    private Path configuredPython() {
        String configured = System.getProperty("agent.runtime.python");
        return configured == null || configured.isBlank()
                ? DEFAULT_PYTHON
                : Path.of(configured).toAbsolutePath().normalize();
    }

    private boolean runtimeHealth(int runtimePort, String endpoint) {
        if (runtimeProcess == null || !runtimeProcess.isAlive()) {
            return false;
        }
        HttpURLConnection connection = null;
        try {
            URL health = URI.create("http://127.0.0.1:" + runtimePort + "/internal/health/" + endpoint).toURL();
            connection = (HttpURLConnection) health.openConnection();
            connection.setConnectTimeout(300);
            connection.setReadTimeout(300);
            return connection.getResponseCode() == 200;
        } catch (IOException unavailable) {
            return false;
        } finally {
            if (connection != null) {
                connection.disconnect();
            }
        }
    }

    private boolean springReady(WebTestClient client) {
        return client.get().uri("/actuator/health/readiness")
                .exchange()
                .returnResult(Void.class)
                .getStatus()
                .value() == 200;
    }

    private void await(String condition, BooleanSupplier assertion) throws InterruptedException {
        long deadline = System.nanoTime() + Duration.ofSeconds(20).toNanos();
        while (System.nanoTime() < deadline) {
            if (assertion.getAsBoolean()) {
                return;
            }
            Thread.sleep(100);
        }
        throw new AssertionError(condition + " was not reached");
    }

    private void stopSpring() {
        ReactiveWebServerApplicationContext context = springContext;
        springContext = null;
        if (context != null) {
            context.close();
        }
    }

    private void stopRuntime() throws InterruptedException {
        Process process = runtimeProcess;
        runtimeProcess = null;
        if (process == null || !process.isAlive()) {
            return;
        }
        try {
            Files.writeString(runtimeStopPath, "stop", StandardCharsets.US_ASCII);
        } catch (IOException failure) {
            process.destroyForcibly();
            process.waitFor(3, TimeUnit.SECONDS);
            return;
        }
        if (!process.waitFor(12, TimeUnit.SECONDS)) {
            process.destroyForcibly();
            process.waitFor(3, TimeUnit.SECONDS);
        }
    }

    @AfterEach
    void cleanup() throws Exception {
        stopSpring();
        stopRuntime();
        if (runRoot != null && Files.exists(runRoot)) {
            try (var paths = Files.walk(runRoot)) {
                for (Path path : paths.sorted(java.util.Comparator.reverseOrder()).toList()) {
                    Files.deleteIfExists(path);
                }
            }
        }
    }

    private static int freePort() {
        try (ServerSocket socket = new ServerSocket(0)) {
            socket.setReuseAddress(false);
            return socket.getLocalPort();
        } catch (IOException failure) {
            throw new IllegalStateException("agent.business-query-plan-nonlive-port-unavailable", failure);
        }
    }

    @TestConfiguration(proxyBeanMethods = false)
    static class TestAuthenticationConfiguration {
        @Bean
        ReactiveJwtDecoder reactiveJwtDecoder() {
            return token -> {
                if (!ADMIN_TOKEN.equals(token) && !DENIED_TOKEN.equals(token)) {
                    return Mono.error(new JwtException("invalid"));
                }
                Instant now = Instant.now();
                return Mono.just(Jwt.withTokenValue(token)
                        .header("alg", "none")
                        .subject(ADMIN_TOKEN.equals(token) ? "admin" : "denied")
                        .claim(SecurityTokenUtils.TOKEN_TYPE_CLAIM, SecurityTokenUtils.USER_TOKEN_TYPE)
                        .claim("role", List.of(ADMIN_TOKEN.equals(token) ? "ADMIN" : "UNKNOWN"))
                        .issuedAt(now)
                        .expiresAt(now.plusSeconds(60))
                        .build());
            };
        }
    }
}
