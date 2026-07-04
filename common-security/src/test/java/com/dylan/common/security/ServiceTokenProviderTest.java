package com.dylan.common.security;

import static org.assertj.core.api.Assertions.assertThat;

import java.text.ParseException;
import java.util.Map;

import com.nimbusds.jwt.SignedJWT;
import org.junit.jupiter.api.Test;
import org.springframework.mock.env.MockEnvironment;
import org.springframework.security.oauth2.jwt.JwtEncoder;

class ServiceTokenProviderTest {

	@Test
	void serviceTokenCarriesKid() throws ParseException {
		JwtKeySet keySet = new JwtKeySet(
				SecretTestSupport.ACTIVE,
				SecretTestSupport.hmacKey((byte) 1),
				Map.of(SecretTestSupport.ACTIVE, SecretTestSupport.hmacKey((byte) 1)));
		JwtEncoder encoder = SecretTestSupport.jwtEncoder(keySet.activeKeyId(), keySet.activeKey());
		ServiceTokenProperties properties = new ServiceTokenProperties();
		ServiceTokenProvider provider = new ServiceTokenProvider(
				encoder,
				properties,
				new MockEnvironment().withProperty("spring.application.name", "agent-service"),
				() -> keySet);

		String token = provider.token();

		assertThat(SignedJWT.parse(token).getHeader().getKeyID()).isEqualTo(SecretTestSupport.ACTIVE);
	}
}
