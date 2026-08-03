package com.dylan.common.security;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.time.Instant;
import java.util.Map;

import com.nimbusds.jose.jwk.source.ImmutableSecret;
import org.junit.jupiter.api.Test;
import org.springframework.security.oauth2.jwt.JwsHeader;
import org.springframework.security.oauth2.jwt.BadJwtException;
import org.springframework.security.oauth2.jwt.JwtClaimsSet;
import org.springframework.security.oauth2.jwt.JwtEncoder;
import org.springframework.security.oauth2.jwt.JwtEncoderParameters;
import org.springframework.security.oauth2.jwt.NimbusJwtEncoder;

class KidAwareJwtDecoderTest {

	@Test
	void decodesTokenSignedWithPreviousKid() {
		KidAwareJwtDecoder decoder = decoder();
		String token = token(SecretTestSupport.PREVIOUS, SecretTestSupport.hmacKey((byte) 2));

		assertThat(decoder.decode(token).getSubject()).isEqualTo("user-1");
	}

	@Test
	void rejectsUnknownOrMissingKid() {
		KidAwareJwtDecoder decoder = decoder();
		String unknownKid = token("UNKNOWN", SecretTestSupport.hmacKey((byte) 1));
		String missingKid = token(null, SecretTestSupport.hmacKey((byte) 1));

		assertThatThrownBy(() -> decoder.decode(unknownKid))
				.isInstanceOf(BadJwtException.class)
				.hasMessageContaining("Unknown JWT kid");
		assertThatThrownBy(() -> decoder.decode(missingKid))
				.isInstanceOf(BadJwtException.class)
				.hasMessageContaining("kid is required");
	}

	@Test
	void classifiesMalformedCompactJwtAsBadJwt() {
		assertThatThrownBy(() -> decoder().decode("not-a-jwt"))
				.isInstanceOf(BadJwtException.class)
				.hasMessageContaining("Invalid JWT format");
	}

	private static KidAwareJwtDecoder decoder() {
		JwtKeySet keySet = new JwtKeySet(
				SecretTestSupport.ACTIVE,
				SecretTestSupport.hmacKey((byte) 1),
				Map.of(
						SecretTestSupport.ACTIVE, SecretTestSupport.hmacKey((byte) 1),
						SecretTestSupport.PREVIOUS, SecretTestSupport.hmacKey((byte) 2)));
		return new KidAwareJwtDecoder(() -> keySet);
	}

	private static String token(String keyId, javax.crypto.SecretKey key) {
		JwtEncoder encoder = keyId == null
				? new NimbusJwtEncoder(new ImmutableSecret<>(key))
				: SecretTestSupport.jwtEncoder(keyId, key);
		JwsHeader.Builder header = JwsHeader.with(() -> "HS256");
		if (keyId != null) {
			header.keyId(keyId);
		}
		Instant now = Instant.now();
		JwtClaimsSet claims = JwtClaimsSet.builder()
				.subject("user-1")
				.issuedAt(now)
				.expiresAt(now.plusSeconds(3600))
				.build();
		return encoder.encode(JwtEncoderParameters.from(header.build(), claims)).getTokenValue();
	}
}
