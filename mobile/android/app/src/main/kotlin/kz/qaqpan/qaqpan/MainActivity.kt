package kz.qaqpan.qaqpan

import android.Manifest
import android.content.Context
import android.content.pm.PackageManager
import android.media.AudioManager
import android.telephony.TelephonyManager
import io.flutter.embedding.android.FlutterActivity
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.plugin.common.MethodChannel

/**
 * Native half of Qaqpan: the FACT of a phone call, nothing more (no number, no audio).
 *  - AudioManager mode: works without permissions and also covers messenger calls (WhatsApp, Telegram);
 *  - TelephonyManager call state: regular cellular calls, needs READ_PHONE_STATE (asked once).
 */
class MainActivity : FlutterActivity() {
    override fun configureFlutterEngine(flutterEngine: FlutterEngine) {
        super.configureFlutterEngine(flutterEngine)
        MethodChannel(flutterEngine.dartExecutor.binaryMessenger, "kz.qaqpan/call").setMethodCallHandler { call, result ->
            when (call.method) {
                "isOnCall" -> result.success(isOnCall())
                "requestPhonePermission" -> {
                    if (!hasPhonePermission()) requestPermissions(arrayOf(Manifest.permission.READ_PHONE_STATE), 42)
                    result.success(hasPhonePermission())
                }
                else -> result.notImplemented()
            }
        }
    }

    private fun hasPhonePermission(): Boolean =
        checkSelfPermission(Manifest.permission.READ_PHONE_STATE) == PackageManager.PERMISSION_GRANTED

    private fun isOnCall(): Boolean {
        val audio = getSystemService(Context.AUDIO_SERVICE) as AudioManager
        if (audio.mode == AudioManager.MODE_IN_CALL || audio.mode == AudioManager.MODE_IN_COMMUNICATION) return true
        if (!hasPhonePermission()) return false
        return try {
            val tm = getSystemService(Context.TELEPHONY_SERVICE) as TelephonyManager
            @Suppress("DEPRECATION")
            tm.callState != TelephonyManager.CALL_STATE_IDLE
        } catch (e: SecurityException) {
            false
        }
    }
}
