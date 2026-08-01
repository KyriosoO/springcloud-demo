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
import java.util.concurrent.TimeUnit;
import java.util.function.BooleanSupplier;

import com.dylan.agent.service.AgentServiceApplication;
import com.dylan.common.security.SecurityTokenUtils;

import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.Test;
import org.springframework.boot.builder.SpringApplicationBuilder;
import org.springframework.boot.web.reactive.context.ReactiveWebServerApplicationContext;
import org.springframework.boot.test.context.TestConfiguration;
import org.springframework.context.annotation.Bean;
import org.springframework.http.MediaType;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.security.oauth2.jwt.JwtException;
import org.springframework.security.oauth2.jwt.ReactiveJwtDecoder;
import org.springframework.test.web.reactive.server.WebTestClient;

import reactor.core.publisher.Mono;

class AgentAccessE2ETest {
    private static final Path DEFAULT_PYTHON = Path.of(
            "..", ".tmp", "agent-runtime-venv", "Scripts", "python.exe").toAbsolutePath().normalize();
    private static final Path RUNTIME_ROOT = Path.of("..", "agent-runtime").toAbsolutePath().normalize();
    private static final Path RUNTIME_LOG = Path.of("target", "agent-access-e2e-runtime.log")
            .toAbsolutePath().normalize();

    private Process runtimeProcess;
    private ReactiveWebServerApplicationContext springContext;

    @Test
    void verifiesTwoProcessStartupAuthenticationMappingAndReverseShutdown() throws Exception {
        int runtimePort = freePort();
        WebTestClient springWithoutRuntime = startSpring(runtimePort);
        springWithoutRuntime.get().uri("/actuator/health/liveness").exchange().expectStatus().isOk();
        springWithoutRuntime.get().uri("/actuator/health/readiness").exchange().expectStatus().isEqualTo(503);
        assertInvalidToken(springWithoutRuntime);
        assertRuntimeUnavailable(springWithoutRuntime);
        stopSpring();

        startRuntime(runtimePort);
        await("Runtime liveness", () -> runtimeHealth(runtimePort, "live"));
        await("Runtime readiness", () -> runtimeHealth(runtimePort, "ready"));
        WebTestClient springWithRuntime = startSpring(runtimePort);
        await("Spring readiness", () -> springReady(springWithRuntime));

        springWithRuntime.post().uri("/api/v1/agent/queries")
                .header("Authorization", "Bearer e2e-user-token")
                .header("X-Correlation-Id", "corr-e2e-safe")
                .contentType(MediaType.APPLICATION_JSON)
                .bodyValue("{\"question\":\"税务政策\"}")
                .exchange()
                .expectStatus().isEqualTo(422)
                .expectHeader().contentTypeCompatibleWith(MediaType.APPLICATION_JSON)
                .expectBody()
                .jsonPath("$.status").isEqualTo("unsupported")
                .jsonPath("$.correlationId").isEqualTo("corr-e2e-safe")
                .jsonPath("$.error.code").isEqualTo("core.no_enabled_capability");

        stopSpring();
        assertThat(runtimeProcess).isNotNull();
        assertThat(runtimeProcess.isAlive()).as("Runtime remains alive until Spring stops").isTrue();
        stopRuntime();

        String runtimeLog = Files.exists(RUNTIME_LOG)
                ? Files.readString(RUNTIME_LOG, StandardCharsets.UTF_8)
                : "";
        assertThat(runtimeLog).doesNotContain("e2e-user-token", "税务政策");
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
        int springPort = springContext.getWebServer().getPort();
        return WebTestClient.bindToServer()
                .baseUrl("http://127.0.0.1:" + springPort)
                .responseTimeout(Duration.ofSeconds(5))
                .build();
    }

    private void assertInvalidToken(WebTestClient client) {
        client.post().uri("/api/v1/agent/queries")
                .header("Authorization", "Bearer invalid-e2e-token")
                .contentType(MediaType.APPLICATION_JSON)
                .bodyValue("{\"question\":\"税务政策\"}")
                .exchange()
                .expectStatus().isUnauthorized()
                .expectBody()
                .jsonPath("$.status").isEqualTo("unauthenticated")
                .jsonPath("$.error.code").isEqualTo("core.user_identity_required");
    }

    private void assertRuntimeUnavailable(WebTestClient client) {
        client.post().uri("/api/v1/agent/queries")
                .header("Authorization", "Bearer e2e-user-token")
                .contentType(MediaType.APPLICATION_JSON)
                .bodyValue("{\"question\":\"税务政策\"}")
                .exchange()
                .expectStatus().isEqualTo(502)
                .expectBody()
                .jsonPath("$.status").isEqualTo("downstream_failure")
                .jsonPath("$.error.code").isEqualTo("downstream.runtime_unavailable");
    }

    private void startRuntime(int runtimePort) throws IOException {
        Path python = configuredPython();
        assertThat(Files.isExecutable(python)).as("isolated runtime Python must exist").isTrue();
        Files.createDirectories(RUNTIME_LOG.getParent());
        Files.deleteIfExists(RUNTIME_LOG);
        ProcessBuilder builder = new ProcessBuilder(python.toString(), "-m", "agent_runtime.main")
                .directory(RUNTIME_ROOT.toFile())
                .redirectErrorStream(true)
                .redirectOutput(RUNTIME_LOG.toFile());
        builder.environment().put("AGENT_RUNTIME_HOST", "127.0.0.1");
        builder.environment().put("AGENT_RUNTIME_PORT", Integer.toString(runtimePort));
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
            connection.setConnectTimeout(200);
            connection.setReadTimeout(200);
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
        long deadline = System.nanoTime() + Duration.ofSeconds(10).toNanos();
        while (System.nanoTime() < deadline) {
            if (assertion.getAsBoolean()) {
                return;
            }
            Thread.sleep(50);
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
        process.destroy();
        if (!process.waitFor(3, TimeUnit.SECONDS)) {
            process.destroyForcibly();
            process.waitFor(3, TimeUnit.SECONDS);
        }
    }

    @AfterEach
    void cleanup() throws InterruptedException {
        stopSpring();
        stopRuntime();
    }

    private static int freePort() {
        try (ServerSocket socket = new ServerSocket(0)) {
            socket.setReuseAddress(false);
            return socket.getLocalPort();
        } catch (IOException failure) {
            throw new IllegalStateException("agent.e2e-port-unavailable", failure);
        }
    }

    @TestConfiguration(proxyBeanMethods = false)
    static class TestAuthenticationConfiguration {
        @Bean
        ReactiveJwtDecoder reactiveJwtDecoder() {
            return token -> {
                if (!"e2e-user-token".equals(token)) {
                    return Mono.error(new JwtException("invalid"));
                }
                Instant now = Instant.now();
                return Mono.just(Jwt.withTokenValue(token)
                        .header("alg", "none")
                        .subject("dylan")
                        .claim(SecurityTokenUtils.TOKEN_TYPE_CLAIM, SecurityTokenUtils.USER_TOKEN_TYPE)
                        .issuedAt(now)
                        .expiresAt(now.plusSeconds(60))
                        .build());
            };
        }
    }
}
