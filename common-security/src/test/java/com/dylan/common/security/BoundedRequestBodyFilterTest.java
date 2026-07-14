package com.dylan.common.security;

import org.junit.jupiter.api.Test;
import org.springframework.mock.web.MockHttpServletRequest;
import org.springframework.mock.web.MockHttpServletResponse;
import java.nio.charset.StandardCharsets;
import static org.assertj.core.api.Assertions.assertThat;

class BoundedRequestBodyFilterTest {
    @Test void rejectsDeclaredAndChunkedBodiesAboveLimit() throws Exception {
        var filter=new BoundedRequestBodyFilter("/internal/document-governance",16);
        var declared=new MockHttpServletRequest("POST","/internal/document-governance/indexes/activate");
        declared.setContent("x".repeat(17).getBytes(StandardCharsets.UTF_8));
        var response=new MockHttpServletResponse();
        filter.doFilter(declared,response,(request,result)->{});
        assertThat(response.getStatus()).isEqualTo(400);
        assertThat(response.getContentAsString()).contains("\"code\":\"INVALID_REQUEST\"");

        var chunked=new MockHttpServletRequest("POST","/internal/document-governance/indexes/activate"){
            @Override public long getContentLengthLong(){return -1;}
        };
        chunked.setContent("x".repeat(17).getBytes(StandardCharsets.UTF_8));
        var chunkedResponse=new MockHttpServletResponse();
        filter.doFilter(chunked,chunkedResponse,(request,result)->request.getInputStream().readAllBytes());
        assertThat(chunkedResponse.getStatus()).isEqualTo(400);
        assertThat(chunkedResponse.getContentAsString()).contains("\"code\":\"INVALID_REQUEST\"");
    }
}
