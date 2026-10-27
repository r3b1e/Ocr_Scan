package com.periscope.remindrx

import android.app.NotificationManager
import android.content.Context
import android.content.Intent
import android.net.Uri
import android.os.Build
import android.provider.Settings
import android.view.WindowManager
import com.facebook.react.bridge.Promise
import com.facebook.react.bridge.ReactApplicationContext
import com.facebook.react.bridge.ReactContextBaseJavaModule
import com.facebook.react.bridge.ReactMethod

/**
 * Android 14+ lets the user revoke full-screen intents, which turns an alarm
 * into a plain heads-up. notifee can't report that, so this does.
 *
 * Also toggles show-over-lock-screen at runtime: only the alarm ringer may
 * appear without unlocking; the rest of the app (medicines, erase data) must
 * stay behind the keyguard.
 */
class RxSystemModule(private val ctx: ReactApplicationContext) : ReactContextBaseJavaModule(ctx) {
  override fun getName() = "RxSystem"

  @ReactMethod
  fun canUseFullScreenIntent(promise: Promise) {
    if (Build.VERSION.SDK_INT < 34) { promise.resolve(true); return }
    val nm = ctx.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
    promise.resolve(nm.canUseFullScreenIntent())
  }

  @ReactMethod
  fun openFullScreenIntentSettings(promise: Promise) {
    try {
      val intent = if (Build.VERSION.SDK_INT >= 34)
        Intent(Settings.ACTION_MANAGE_APP_USE_FULL_SCREEN_INTENT, Uri.parse("package:${ctx.packageName}"))
      else
        Intent(Settings.ACTION_APP_NOTIFICATION_SETTINGS).putExtra(Settings.EXTRA_APP_PACKAGE, ctx.packageName)
      intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
      ctx.startActivity(intent)
      promise.resolve(true)
    } catch (e: Exception) {
      promise.resolve(false)
    }
  }

  @ReactMethod
  fun setShowOverLockScreen(on: Boolean) {
    val activity = reactApplicationContext.currentActivity ?: return
    activity.runOnUiThread {
      if (Build.VERSION.SDK_INT >= 27) {
        activity.setShowWhenLocked(on)
        activity.setTurnScreenOn(on)
      } else {
        @Suppress("DEPRECATION")
        val flags = WindowManager.LayoutParams.FLAG_SHOW_WHEN_LOCKED or WindowManager.LayoutParams.FLAG_TURN_SCREEN_ON
        if (on) activity.window.addFlags(flags) else activity.window.clearFlags(flags)
      }
    }
  }
}
