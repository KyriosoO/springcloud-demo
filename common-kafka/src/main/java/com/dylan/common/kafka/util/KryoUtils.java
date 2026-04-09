package com.dylan.common.kafka.util;

import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.util.List;
import java.util.stream.Collectors;

import com.esotericsoftware.kryo.Kryo;
import com.esotericsoftware.kryo.io.Input;
import com.esotericsoftware.kryo.io.Output;

public class KryoUtils {
	// Kryo 对象建议每线程使用独立实例（非线程安全）
	private static final ThreadLocal<Kryo> KRYO_THREAD_LOCAL = ThreadLocal.withInitial(() -> {
		Kryo kryo = new Kryo();
		kryo.setReferences(true); // 支持循环引用
		kryo.setRegistrationRequired(false); // 是否要求注册 class
		return kryo;
	});

	// 对象 -> byte[]
	public static <T> byte[] serialize(T obj) {
		Kryo kryo = KRYO_THREAD_LOCAL.get();
		try (ByteArrayOutputStream baos = new ByteArrayOutputStream(); Output output = new Output(baos)) {
			kryo.writeClassAndObject(output, obj);
			output.flush();
			return baos.toByteArray();
		} catch (Exception e) {
			throw new RuntimeException("Kryo 序列化失败", e);
		}
	}

	// byte[] -> 对象
	public static <T> T deserialize(byte[] data, Class<T> clazz) {
		Kryo kryo = KRYO_THREAD_LOCAL.get();
		try {
			ByteArrayInputStream bais = new ByteArrayInputStream(data);
			Input input = new Input(bais);
			Object obj = kryo.readClassAndObject(input);
			return clazz.cast(obj);
		} catch (Exception e) {
			throw new RuntimeException("Kryo 反序列化失败", e);
		}
	}

	public static <T> T deserializeGeneric(byte[] data) {
		Kryo kryo = KRYO_THREAD_LOCAL.get();
		try (Input input = new Input(data)) {
			return (T) kryo.readClassAndObject(input); // 泛型由调用者负责
		}
	}
}
