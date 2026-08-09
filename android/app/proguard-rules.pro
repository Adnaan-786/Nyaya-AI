# R8 keep rules for the release build.
#
# This file was referenced by build.gradle.kts long before it existed. A missing
# `proguardFiles` entry is only a *warning* ("Supplied proguard configuration does not
# exist"), so every release build so far succeeded and shrank the app with nothing but
# the Android defaults — producing an APK that installs and then fails at runtime rather
# than one that fails to build. Keep that in mind before deleting a rule here because
# "the build still passes": for R8 problems the build passing proves nothing.
#
# Most modern libraries ship their own consumer rules inside the AAR (OkHttp, Hilt,
# Room, Coil, Compose, kotlinx-serialization's plugin). What follows is deliberately
# limited to the things those do not cover.

# ---------------------------------------------------------------------------
# Crash reports
# ---------------------------------------------------------------------------
# Without this a stack trace from the field is a list of a(), b(), c(). The mapping file
# in build/outputs/mapping/ is what turns it back into something readable, so keep the
# attributes that make the trace worth de-obfuscating in the first place.
-keepattributes SourceFile,LineNumberTable
-renamesourcefileattribute SourceFile

# Runtime annotations and generic signatures. Retrofit reads both reflectively: the
# annotations to build a call, the signatures to know that Response<ApiEnvelope<UserDto>>
# is not just Response<Object>. Losing them turns every API call into a runtime failure.
-keepattributes RuntimeVisibleAnnotations,RuntimeVisibleParameterAnnotations
-keepattributes Signature,InnerClasses,EnclosingMethod,AnnotationDefault

# ---------------------------------------------------------------------------
# Retrofit
# ---------------------------------------------------------------------------
# Service declarations are interfaces that are never *implemented* in our code — the
# implementation is generated at runtime by a Proxy. R8 sees an interface with no
# implementors and no direct instantiation, which is exactly the shape it likes to
# remove.
-keep,allowobfuscation,allowshrinking interface retrofit2.Call
-keep,allowobfuscation,allowshrinking class retrofit2.Response
-if interface * { @retrofit2.http.* <methods>; }
-keep,allowobfuscation interface <1>
-keep,allowobfuscation interface * {
    @retrofit2.http.* <methods>;
}
# Suspend functions are compiled to return Continuation-typed generics; the type
# resolution Retrofit does at proxy-creation time needs these intact.
-keep,allowobfuscation,allowshrinking class kotlin.coroutines.Continuation

# ---------------------------------------------------------------------------
# kotlinx.serialization
# ---------------------------------------------------------------------------
# The compiler plugin generates a `Companion.serializer()` per @Serializable class and
# ships consumer rules, so DTOs themselves are handled. These cover the lookup paths
# those rules historically miss — named companions and the generated $$serializer.
-if @kotlinx.serialization.Serializable class **
-keepclassmembers class <1> {
    static <1>$Companion Companion;
    static **$* *;
}
-keepclassmembers class **$$serializer {
    *** descriptor;
}
-keep,includedescriptorclasses class ai.nyayaai.**$$serializer { *; }

# ---------------------------------------------------------------------------
# Razorpay checkout
# ---------------------------------------------------------------------------
# The SDK reflects over its own model classes and calls back into the Activity through
# an interface it looks up by name, so neither side survives obfuscation. These are the
# rules Razorpay documents for their Android SDK.
-keepclassmembers class * {
    @android.webkit.JavascriptInterface <methods>;
}
-keepattributes JavascriptInterface
-keep class com.razorpay.** { *; }
-dontwarn com.razorpay.**
-optimizations !method/inlining/*
# The payment result arrives on MainActivity via PaymentResultWithDataListener, invoked
# reflectively — renaming the callbacks silently loses every payment confirmation, with
# the money already taken.
-keep class ai.nyayaai.app.MainActivity { *; }
-keep interface com.razorpay.PaymentResultWithDataListener { *; }
-keep class * implements com.razorpay.PaymentResultWithDataListener { *; }

# ---------------------------------------------------------------------------
# Domain and DTO layers
# ---------------------------------------------------------------------------
# Enum valueOf() is reflective, and the wire strings map onto enum constants in the
# mappers. R8 cannot see the connection between "firm_admin" in JSON and the constant.
-keepclassmembers enum * {
    public static **[] values();
    public static ** valueOf(java.lang.String);
}
-keep class ai.nyayaai.core.network.dto.** { *; }
-keep class ai.nyayaai.core.model.** { *; }

# ---------------------------------------------------------------------------
# Firebase Cloud Messaging
# ---------------------------------------------------------------------------
# The service is instantiated by name from the manifest, never from our code.
-keep class ai.nyayaai.app.push.** { *; }

# ---------------------------------------------------------------------------
# ML Kit document scanner
# ---------------------------------------------------------------------------
# Delivered as a Play Services module and resolved dynamically; R8 has no visibility
# into what the module will ask for.
-dontwarn com.google.mlkit.**
-keep class com.google.mlkit.** { *; }
