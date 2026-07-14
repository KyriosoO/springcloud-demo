package com.dylan.common.security;

import jakarta.servlet.FilterChain;
import jakarta.servlet.ReadListener;
import jakarta.servlet.ServletException;
import jakarta.servlet.ServletInputStream;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletRequestWrapper;
import jakarta.servlet.http.HttpServletResponse;
import org.springframework.web.filter.OncePerRequestFilter;

import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStreamReader;
import java.nio.charset.Charset;
import java.nio.charset.StandardCharsets;

/** 对指定内部管理路径实施流式请求体上限；无Content-Length/chunked请求同样受限。 */
public final class BoundedRequestBodyFilter extends OncePerRequestFilter {
    private final String pathPrefix; private final long maxBytes;
    public BoundedRequestBodyFilter(String pathPrefix,long maxBytes){
        if(pathPrefix==null||pathPrefix.isBlank()||maxBytes<=0)throw new IllegalArgumentException("pathPrefix/maxBytes invalid");
        this.pathPrefix=pathPrefix;this.maxBytes=maxBytes;
    }
    @Override protected boolean shouldNotFilter(HttpServletRequest request){return !request.getRequestURI().startsWith(pathPrefix)||"GET".equalsIgnoreCase(request.getMethod());}
    @Override protected void doFilterInternal(HttpServletRequest request,HttpServletResponse response,FilterChain chain)throws ServletException,IOException{
        if(request.getContentLengthLong()>maxBytes){
            response.setStatus(HttpServletResponse.SC_BAD_REQUEST);response.setContentType("application/json");
            response.getWriter().write("{\"contractVersion\":\"DMERR-1\",\"code\":\"INVALID_REQUEST\",\"diagnosticId\":\"DMERR-BODY-LIMIT\"}");
            return;
        }
        chain.doFilter(new BoundedRequest(request,maxBytes),response);
    }
    private static final class BoundedRequest extends HttpServletRequestWrapper {
        private final long maxBytes;
        BoundedRequest(HttpServletRequest request,long maxBytes){super(request);this.maxBytes=maxBytes;}
        @Override public ServletInputStream getInputStream()throws IOException{return new BoundedServletInputStream(super.getInputStream(),maxBytes);}
        @Override public BufferedReader getReader()throws IOException{
            String encoding=getCharacterEncoding();Charset charset=encoding==null?StandardCharsets.UTF_8:Charset.forName(encoding);
            return new BufferedReader(new InputStreamReader(getInputStream(),charset));
        }
    }
    private static final class BoundedServletInputStream extends ServletInputStream {
        private final ServletInputStream delegate;private final long maxBytes;private long read;
        BoundedServletInputStream(ServletInputStream delegate,long maxBytes){this.delegate=delegate;this.maxBytes=maxBytes;}
        @Override public int read()throws IOException{int value=delegate.read();if(value>=0)count(1);return value;}
        @Override public int read(byte[] bytes,int offset,int length)throws IOException{int count=delegate.read(bytes,offset,length);if(count>0)count(count);return count;}
        private void count(int count)throws IOException{read+=count;if(read>maxBytes)throw new IOException("request body exceeds configured limit");}
        @Override public boolean isFinished(){return delegate.isFinished();}
        @Override public boolean isReady(){return delegate.isReady();}
        @Override public void setReadListener(ReadListener listener){delegate.setReadListener(listener);}
    }
}
