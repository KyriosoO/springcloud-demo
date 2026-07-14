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
import java.io.ByteArrayInputStream;
import java.io.IOException;
import java.io.InputStreamReader;
import java.nio.charset.Charset;
import java.nio.charset.StandardCharsets;

/** 对指定内部管理路径实施流式请求体上限；无Content-Length/chunked请求同样受限。 */
public final class BoundedRequestBodyFilter extends OncePerRequestFilter {
    private final String pathPrefix; private final long maxBytes;
    public BoundedRequestBodyFilter(String pathPrefix,long maxBytes){
        if(pathPrefix==null||pathPrefix.isBlank()||maxBytes<=0||maxBytes>=Integer.MAX_VALUE)throw new IllegalArgumentException("pathPrefix/maxBytes invalid");
        this.pathPrefix=pathPrefix;this.maxBytes=maxBytes;
    }
    @Override protected boolean shouldNotFilter(HttpServletRequest request){return !request.getRequestURI().startsWith(pathPrefix)||"GET".equalsIgnoreCase(request.getMethod());}
    @Override protected void doFilterInternal(HttpServletRequest request,HttpServletResponse response,FilterChain chain)throws ServletException,IOException{
        if(request.getContentLengthLong()>maxBytes){
            response.setStatus(HttpServletResponse.SC_BAD_REQUEST);response.setContentType("application/json");
            response.getWriter().write("{\"contractVersion\":\"DMERR-1\",\"code\":\"INVALID_REQUEST\",\"diagnosticId\":\"DMERR-BODY-LIMIT\"}");
            return;
        }
        byte[] body=request.getInputStream().readNBytes((int)maxBytes+1);
        if(body.length>maxBytes){
            reject(response);
            return;
        }
        chain.doFilter(new CachedBodyRequest(request,body),response);
    }
    private static void reject(HttpServletResponse response)throws IOException{
        response.setStatus(HttpServletResponse.SC_BAD_REQUEST);response.setContentType("application/json");
        response.getWriter().write("{\"contractVersion\":\"DMERR-1\",\"code\":\"INVALID_REQUEST\",\"diagnosticId\":\"DMERR-BODY-LIMIT\"}");
    }
    private static final class CachedBodyRequest extends HttpServletRequestWrapper {
        private final byte[] body;
        CachedBodyRequest(HttpServletRequest request,byte[] body){super(request);this.body=body.clone();}
        @Override public int getContentLength(){return body.length;}
        @Override public long getContentLengthLong(){return body.length;}
        @Override public ServletInputStream getInputStream(){return new CachedServletInputStream(body);}
        @Override public BufferedReader getReader()throws IOException{
            String encoding=getCharacterEncoding();Charset charset=encoding==null?StandardCharsets.UTF_8:Charset.forName(encoding);
            return new BufferedReader(new InputStreamReader(getInputStream(),charset));
        }
    }
    private static final class CachedServletInputStream extends ServletInputStream {
        private final ByteArrayInputStream delegate;
        CachedServletInputStream(byte[] body){delegate=new ByteArrayInputStream(body);}
        @Override public int read(){return delegate.read();}
        @Override public int read(byte[] bytes,int offset,int length){return delegate.read(bytes,offset,length);}
        @Override public boolean isFinished(){return delegate.available()==0;}
        @Override public boolean isReady(){return true;}
        @Override public void setReadListener(ReadListener listener){
            if(listener==null)throw new IllegalArgumentException("readListener required");
            try{if(isFinished())listener.onAllDataRead();else listener.onDataAvailable();}
            catch(IOException ex){listener.onError(ex);}
        }
    }
}
