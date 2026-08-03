package com.dylan.esquery.web;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.nio.charset.StandardCharsets;

import org.junit.jupiter.api.Test;

import com.dylan.esquery.api.knowledge.KnowledgeSearchRequest;
import com.dylan.esquery.web.KnowledgeSearchExceptions.KnowledgeInvalidRequestException;
import com.fasterxml.jackson.databind.ObjectMapper;

class KnowledgeSearchJsonCodecTest {
	private final KnowledgeSearchJsonCodec codec = new KnowledgeSearchJsonCodec(new ObjectMapper());

	@Test
	void decodesTheFiniteKeywordContract() {
		byte[] body = """
				{"schemaVersion":1,"logicalDomainId":"tax.policy","retrievalProfileId":"tax-policy-v1","path":"keyword","queryText":"税务政策","queryVector":null,"limit":20}
				""".getBytes(StandardCharsets.UTF_8);
		KnowledgeSearchRequest request = codec.decodeRequest(body);
		assertThat(request.path()).isEqualTo("keyword");
		assertThat(request.limit()).isEqualTo(20);
	}

	@Test
	void rejectsDuplicateUnknownTrailingAndPathMismatch() {
		assertInvalid("{\"schemaVersion\":1,\"schemaVersion\":1}");
		assertInvalid("{\"schemaVersion\":1,\"unknown\":1}");
		assertInvalid("{} {}");
		assertInvalid("""
				{"schemaVersion":1,"logicalDomainId":"tax.policy","retrievalProfileId":"tax-policy-v1","path":"keyword","queryText":"q","queryVector":[1.0],"limit":20}
				""");
		assertInvalid("""
				{"schemaVersion":1,"logicalDomainId":"tax.policy","retrievalProfileId":"tax-law-v1","path":"keyword","queryText":"q","queryVector":null,"limit":20}
				""");
	}

	@Test
	void rejectsBomAndOversizedBody() {
		assertThatThrownBy(() -> codec.decodeRequest(new byte[] {(byte) 0xef, (byte) 0xbb, (byte) 0xbf, '{', '}'}))
				.isInstanceOf(KnowledgeInvalidRequestException.class);
		assertThatThrownBy(() -> codec.decodeRequest(new byte[KnowledgeSearchJsonCodec.MAX_BODY_BYTES + 1]))
				.isInstanceOf(KnowledgeInvalidRequestException.class);
	}

	@Test
	void rejectsScalarCoercionAndMalformedUtf8() {
		assertInvalid("""
				{"schemaVersion":"1","logicalDomainId":"tax.policy","retrievalProfileId":"tax-policy-v1","path":"keyword","queryText":"q","queryVector":null,"limit":20}
				""");
		assertInvalid("""
				{"schemaVersion":1,"logicalDomainId":"tax.policy","retrievalProfileId":"tax-policy-v1","path":"keyword","queryText":123,"queryVector":null,"limit":20}
				""");
		assertInvalid("""
				{"schemaVersion":1,"logicalDomainId":"tax.policy","retrievalProfileId":"tax-policy-v1","path":"keyword","queryText":"q","queryVector":null,"limit":"20"}
				""");
		byte[] malformed = "{\"schemaVersion\":1,\"logicalDomainId\":\"tax.policy\",\"retrievalProfileId\":\"tax-policy-v1\",\"path\":\"keyword\",\"queryText\":\""
				.getBytes(StandardCharsets.UTF_8);
		byte[] suffix = "\",\"queryVector\":null,\"limit\":20}".getBytes(StandardCharsets.UTF_8);
		byte[] body = new byte[malformed.length + 2 + suffix.length];
		System.arraycopy(malformed, 0, body, 0, malformed.length);
		body[malformed.length] = (byte) 0xc3;
		body[malformed.length + 1] = 0x28;
		System.arraycopy(suffix, 0, body, malformed.length + 2, suffix.length);
		assertThatThrownBy(() -> codec.decodeRequest(body))
				.isInstanceOf(KnowledgeInvalidRequestException.class);
	}

	private void assertInvalid(String json) {
		assertThatThrownBy(() -> codec.decodeRequest(json.getBytes(StandardCharsets.UTF_8)))
				.isInstanceOf(KnowledgeInvalidRequestException.class);
	}
}
