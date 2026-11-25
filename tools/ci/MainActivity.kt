package com.mathuniverse.math_universe_app

import android.os.Handler
import android.os.Looper
import com.chaquo.python.Python
import com.chaquo.python.android.AndroidPlatform
import io.flutter.embedding.android.FlutterActivity
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.plugin.common.MethodChannel
import java.util.concurrent.Executors

/**
 * Puente Flutter <-> motor Python (Chaquopy, CPython dentro del APK). El motor corre en un hilo propio para no
 * bloquear la interfaz. Canal "math_universe/engine": handle(linea JSON) -> linea JSON (contrato 1.1).
 * Canal "math_universe/app": autotestRequested() indica si la app se abrio con el extra "autotest" (autoprueba de
 * instalacion usada por la integracion continua: adb shell am start ... --ez autotest true).
 */
class MainActivity : FlutterActivity() {
    private val executor = Executors.newSingleThreadExecutor()
    private val main = Handler(Looper.getMainLooper())

    override fun configureFlutterEngine(flutterEngine: FlutterEngine) {
        super.configureFlutterEngine(flutterEngine)
        if (!Python.isStarted()) Python.start(AndroidPlatform(this))
        MethodChannel(flutterEngine.dartExecutor.binaryMessenger, "math_universe/engine").setMethodCallHandler { call, result ->
            if (call.method == "handle") {
                val line = call.arguments as String
                executor.execute {
                    try {
                        val out = Python.getInstance().getModule("mu_bridge").callAttr("handle", line).toString()
                        main.post { result.success(out) }
                    } catch (e: Throwable) {
                        main.post { result.error("ENGINE", e.message, null) }
                    }
                }
            } else {
                result.notImplemented()
            }
        }
        MethodChannel(flutterEngine.dartExecutor.binaryMessenger, "math_universe/app").setMethodCallHandler { call, result ->
            if (call.method == "autotestRequested") {
                result.success(intent?.getBooleanExtra("autotest", false) ?: false)
            } else {
                result.notImplemented()
            }
        }
    }
}
