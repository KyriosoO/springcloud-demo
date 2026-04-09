package com.dylan.springGateway.config;

import java.nio.charset.StandardCharsets;
import java.util.List;

import org.springframework.cloud.gateway.filter.GlobalFilter;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.core.annotation.Order;
import org.springframework.core.io.buffer.DataBuffer;
import org.springframework.http.HttpCookie;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.http.server.reactive.ServerHttpRequest;
import org.springframework.security.config.Customizer;
import org.springframework.security.config.annotation.web.reactive.EnableWebFluxSecurity;
import org.springframework.security.config.web.server.ServerHttpSecurity;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.security.oauth2.jwt.JwtDecoder;
import org.springframework.security.oauth2.jwt.JwtDecoders;
import org.springframework.security.web.server.SecurityWebFilterChain;
import org.springframework.security.web.server.ServerAuthenticationEntryPoint;
import org.springframework.security.web.server.authorization.ServerAccessDeniedHandler;
import org.springframework.web.server.ServerWebExchange;
import org.springframework.web.server.WebExceptionHandler;

import reactor.core.publisher.Mono;

@Configuration
@EnableWebFluxSecurity
public class GatewaySecurityConfig {
	private static final List<String> WHITE_LIST = List.of("/login", "/login.html", "/css/", "/js/");

	// ===================== Security FilterChain =====================
	@Bean
	public SecurityWebFilterChain securityWebFilterChain(ServerHttpSecurity http,
			CookieServerBearerTokenConverter cookieServerBearerTokenConverter) {
		http.authorizeExchange(exchanges -> exchanges
				.pathMatchers("/login", "/login.html", "/home.html", "/css/**", "/js/**").permitAll() // 白名单
				.anyExchange().authenticated())
				.oauth2ResourceServer(oauth2 -> oauth2.jwt(Customizer.withDefaults())
						.bearerTokenConverter(cookieServerBearerTokenConverter)// 使用上面定义的
																				// //
																				// jwtDecoder
				).exceptionHandling(exceptions -> exceptions.authenticationEntryPoint(customAuthenticationEntryPoint())
						.accessDeniedHandler(customAccessDeniedHandler()))
				.csrf(csrf -> csrf.disable()); // Gateway 不需要 CSRF

		return http.build();
	}

	@Bean
	@Order(Integer.MIN_VALUE) // 最早执行
	public GlobalFilter authTokenFilter(JwtDecoder jwtDecoder) {
		return (exchange, chain) -> {
			System.out.println("GlobalFilter executed: " + exchange.getRequest().getId() + " path="
					+ exchange.getRequest().getURI().getPath());
			String path = exchange.getRequest().getURI().getPath();
			// 1️ 白名单直接放行
			if (WHITE_LIST.stream().anyMatch(path::startsWith)) {
				return chain.filter(exchange);
			}

			// 2️ 获取 Cookie 中的 AUTH_TOKEN
			HttpCookie cookie = exchange.getRequest().getCookies().getFirst("AUTH_TOKEN");

			// 3️ 如果没有 Token，重定向到登录
			if (cookie == null) {
				return redirectLogin(exchange);
			}
			String token = cookie.getValue();
			Jwt jwt;
			try {
				jwt = jwtDecoder.decode(token);
			} catch (Exception e) {
				return redirectLogin(exchange);
			}
			String userId = jwt.getSubject();
			// 4️ 将 Cookie 中的 Token 转发到下游服务
			ServerHttpRequest mutatedRequest = exchange.getRequest().mutate()
					.header(HttpHeaders.AUTHORIZATION, "Bearer " + cookie.getValue()).header("X-USER-ID", userId)
					.build();

			ServerWebExchange mutatedExchange = exchange.mutate().request(mutatedRequest).build();
			// 5️ 放行请求
			return chain.filter(mutatedExchange);
		};
	}

	// 示例重定向方法
	private Mono<Void> redirectLogin(ServerWebExchange exchange) {
		exchange.getResponse().setStatusCode(HttpStatus.TEMPORARY_REDIRECT);
		exchange.getResponse().getHeaders().set(HttpHeaders.LOCATION, "/login.html");
		return exchange.getResponse().setComplete();
	}

	// ===================== 自定义 401 JSON =====================
	@Bean
	public ServerAuthenticationEntryPoint customAuthenticationEntryPoint() {
		return (exchange, ex) -> writeJson(exchange, 401, "未授权");
	}

	// ===================== 自定义 403 JSON =====================
	@Bean
	public ServerAccessDeniedHandler customAccessDeniedHandler() {
		return (exchange, ex) -> writeJson(exchange, 403, "权限不足");
	}

	// ===================== 公共方法：写 JSON 响应 =====================
	private Mono<Void> writeJson(ServerWebExchange exchange, int code, String message) {
		var response = exchange.getResponse();
		response.setStatusCode(HttpStatus.valueOf(code));
		response.getHeaders().setContentType(MediaType.APPLICATION_JSON);

		String body = String.format("{\"code\":%d,\"message\":\"%s\"}", code, message);
		byte[] bytes = body.getBytes(StandardCharsets.UTF_8);
		DataBuffer buffer = response.bufferFactory().wrap(bytes);
		return response.writeWith(Mono.just(buffer));
	}

	// ===================== 全局异常处理 500 =====================
	@Bean
	@Order(-2) // 确保在 Security 之后执行，但在其他异常处理之前
	public WebExceptionHandler globalExceptionHandler() {
		return (exchange, ex) -> {
			var response = exchange.getResponse();
			if (response.isCommitted()) {
				return Mono.error(ex);
			}

			response.setStatusCode(HttpStatus.INTERNAL_SERVER_ERROR);
			response.getHeaders().setContentType(MediaType.APPLICATION_JSON);

			String body = String.format("{\"code\":500,\"message\":\"%s\"}",
					ex.getMessage() != null ? ex.getMessage() : "系统异常");
			DataBuffer buffer = response.bufferFactory().wrap(body.getBytes(StandardCharsets.UTF_8));
			return response.writeWith(Mono.just(buffer));
		};
	}

	// ===================== Token Relay Filter =====================
//	@Bean
//	@Order(0)
	public GlobalFilter tokenRelayFilter() {
		return new GlobalFilter() {
			@Override
			public Mono<Void> filter(ServerWebExchange exchange,
					org.springframework.cloud.gateway.filter.GatewayFilterChain chain) {
				String authHeader = exchange.getRequest().getHeaders().getFirst(HttpHeaders.AUTHORIZATION);
				if (authHeader != null && authHeader.startsWith("Bearer ")) {
					exchange = exchange.mutate().request(
							exchange.getRequest().mutate().header(HttpHeaders.AUTHORIZATION, authHeader).build())
							.build();
				}
				return chain.filter(exchange);
			}
		};
	}
}
