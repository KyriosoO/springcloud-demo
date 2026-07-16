package com.dylan.authcenter.testsupport;

import com.dylan.authcenter.config.AuthRbacProperties;

import java.io.IOException;

import org.springframework.boot.context.properties.bind.Bindable;
import org.springframework.boot.context.properties.bind.Binder;
import org.springframework.boot.env.YamlPropertySourceLoader;
import org.springframework.core.io.ClassPathResource;
import org.springframework.core.env.MutablePropertySources;
import org.springframework.core.env.StandardEnvironment;

public final class AuthRbacTestFixtures {

    private AuthRbacTestFixtures() {
    }

    public static AuthRbacProperties load() {
        try {
            StandardEnvironment environment = new StandardEnvironment();
            MutablePropertySources sources = environment.getPropertySources();
            new YamlPropertySourceLoader()
                    .load("agent-rbac-test", new ClassPathResource("agent-rbac.yml"))
                    .forEach(sources::addFirst);
            AuthRbacProperties properties = Binder.get(environment)
                    .bind("auth.rbac", Bindable.of(AuthRbacProperties.class))
                    .orElseThrow(() -> new IllegalStateException("auth.rbac test configuration was not bound"));
            properties.afterPropertiesSet();
            return properties;
        } catch (IOException ex) {
            throw new IllegalStateException("failed to load agent-rbac.yml", ex);
        }
    }
}
