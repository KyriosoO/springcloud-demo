package com.dylan.documentprovider;

import org.junit.jupiter.api.Test;
import org.springframework.mock.web.MockHttpServletRequest;
import org.springframework.mock.web.MockHttpServletResponse;

import java.util.concurrent.atomic.AtomicBoolean;

import static org.assertj.core.api.Assertions.assertThat;

class DocumentProviderRequestSizeFilterTest {
    @Test
    void rejectsOversizedAndUnknownLengthBodiesBeforeControllerDispatch() throws Exception {
        DocumentProviderOperationProperties properties = new DocumentProviderOperationProperties();
        properties.setMaxRequestBytes(8);
        DocumentProviderRequestSizeFilter filter = new DocumentProviderRequestSizeFilter(properties);

        var oversized = request();
        oversized.setContent(new byte[9]);
        var oversizedResponse = new MockHttpServletResponse();
        AtomicBoolean oversizedInvoked = new AtomicBoolean();
        filter.doFilter(oversized, oversizedResponse,
                (request, response) -> oversizedInvoked.set(true));

        assertThat(oversizedResponse.getStatus()).isEqualTo(413);
        assertThat(oversizedInvoked).isFalse();

        var unknownLength = request();
        var unknownLengthResponse = new MockHttpServletResponse();
        AtomicBoolean unknownInvoked = new AtomicBoolean();
        filter.doFilter(unknownLength, unknownLengthResponse,
                (request, response) -> unknownInvoked.set(true));

        assertThat(unknownLengthResponse.getStatus()).isEqualTo(413);
        assertThat(unknownInvoked).isFalse();
    }

    @Test
    void allowsBoundedProviderRequestAndIgnoresOtherPaths() throws Exception {
        DocumentProviderOperationProperties properties = new DocumentProviderOperationProperties();
        properties.setMaxRequestBytes(8);
        DocumentProviderRequestSizeFilter filter = new DocumentProviderRequestSizeFilter(properties);

        var bounded = request();
        bounded.setContent(new byte[8]);
        AtomicBoolean boundedInvoked = new AtomicBoolean();
        filter.doFilter(bounded, new MockHttpServletResponse(),
                (request, response) -> boundedInvoked.set(true));
        assertThat(boundedInvoked).isTrue();

        var unrelated = new MockHttpServletRequest("GET", "/actuator/health");
        AtomicBoolean unrelatedInvoked = new AtomicBoolean();
        filter.doFilter(unrelated, new MockHttpServletResponse(),
                (request, response) -> unrelatedInvoked.set(true));
        assertThat(unrelatedInvoked).isTrue();
    }

    private static MockHttpServletRequest request() {
        var request = new MockHttpServletRequest("POST", "/internal/document-providers/rewrite");
        request.setContentType("application/json");
        return request;
    }
}
