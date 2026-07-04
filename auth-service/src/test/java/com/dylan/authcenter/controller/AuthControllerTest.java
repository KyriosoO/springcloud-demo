package com.dylan.authcenter.controller;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.nio.charset.StandardCharsets;
import java.text.ParseException;
import java.util.Map;

import javax.crypto.SecretKey;
import javax.crypto.spec.SecretKeySpec;

import com.dylan.common.security.JwtKeyProvider;
import com.dylan.common.security.JwtKeySet;
import com.nimbusds.jose.JWSAlgorithm;
import com.nimbusds.jose.jwk.JWKSet;
import com.nimbusds.jose.jwk.OctetSequenceKey;
import com.nimbusds.jose.jwk.source.ImmutableJWKSet;
import com.nimbusds.jwt.SignedJWT;
import com.nimbusds.jose.proc.SecurityContext;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.mock.web.MockHttpServletResponse;
import org.springframework.security.authentication.AuthenticationManager;
import org.springframework.security.authentication.BadCredentialsException;
import org.springframework.security.authentication.ProviderManager;
import org.springframework.security.authentication.dao.DaoAuthenticationProvider;
import org.springframework.security.crypto.factory.PasswordEncoderFactories;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.security.oauth2.jwt.JwtDecoder;
import org.springframework.security.oauth2.jwt.JwtEncoder;
import org.springframework.security.oauth2.jwt.NimbusJwtDecoder;
import org.springframework.security.oauth2.jwt.NimbusJwtEncoder;

import com.dylan.authcenter.model.LoginRequest;
import com.dylan.authcenter.service.JwtService;
import com.dylan.authcenter.service.UserService;

@DisplayName("AuthController")
class AuthControllerTest {

    private AuthController controller;
    private JwtDecoder decoder;

    @BeforeEach
    void setUp() {
        SecretKey key = new SecretKeySpec(
                "test-secret-key-test-secret-key-1234".getBytes(StandardCharsets.UTF_8),
                "HmacSHA256");
        JwtEncoder encoder = new NimbusJwtEncoder(new ImmutableJWKSet<SecurityContext>(new JWKSet(
                new OctetSequenceKey.Builder(key.getEncoded())
                        .keyID("ACTIVE")
                        .algorithm(JWSAlgorithm.HS256)
                        .build())));
        decoder = NimbusJwtDecoder.withSecretKey(key).build();
        JwtKeyProvider jwtKeyProvider = () -> new JwtKeySet("ACTIVE", key, Map.of("ACTIVE", key));
        JwtService jwtService = new JwtService(encoder, decoder, jwtKeyProvider);
        UserService userService = new UserService();
        DaoAuthenticationProvider provider = new DaoAuthenticationProvider(userService);
        provider.setPasswordEncoder(PasswordEncoderFactories.createDelegatingPasswordEncoder());
        AuthenticationManager manager = new ProviderManager(provider);
        controller = new AuthController(jwtService, userService, manager);
    }

    @Test
    void loginRejectsInvalidPassword() {
        assertThatThrownBy(() -> login("admin", "wrong-password"))
                .isInstanceOf(BadCredentialsException.class);
    }

    @Test
    void loginRejectsUnknownUser() {
        assertThatThrownBy(() -> login("unknown-user", "123456"))
                .isInstanceOf(BadCredentialsException.class);
    }

    @Test
    void loginIssuesAdminRoles() {
        Jwt jwt = decoder.decode(login("admin", "123456"));
        assertThat(jwt.getClaimAsStringList("role"))
                .containsExactlyInAnyOrder("agent:admin", "agent:viewer");
    }

    @Test
    void loginIssuesViewerRole() {
        Jwt jwt = decoder.decode(login("viewer_t", "123456"));
        assertThat(jwt.getClaimAsStringList("role"))
                .containsExactly("agent:viewer");
    }

    @Test
    void loginTokenCarriesKid() throws ParseException {
        assertThat(SignedJWT.parse(login("admin", "123456")).getHeader().getKeyID()).isEqualTo("ACTIVE");
    }

    private String login(String userId, String password) {
        LoginRequest request = new LoginRequest();
        request.setUserId(userId);
        request.setPassword(password);
        MockHttpServletResponse response = new MockHttpServletResponse();
        controller.login(request, response);
        String setCookie = response.getHeader("Set-Cookie");
        assertThat(setCookie).isNotBlank();
        String tokenPair = setCookie.split(";", 2)[0];
        return tokenPair.substring(tokenPair.indexOf('=') + 1);
    }
}
