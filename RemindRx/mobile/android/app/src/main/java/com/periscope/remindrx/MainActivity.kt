package com.periscope.remindrx

import android.app.KeyguardManager
import android.app.NotificationManager
import android.content.Intent
import android.os.Build
import android.os.Bundle
import com.facebook.react.ReactActivity
import com.facebook.react.ReactActivityDelegate
import com.facebook.react.defaults.DefaultNewArchitectureEntryPoint.fabricEnabled
import com.facebook.react.defaults.DefaultReactActivityDelegate

class MainActivity : ReactActivity() {

  /**
   * Returns the name of the main component registered from JavaScript. This is used to schedule
   * rendering of the component.
   */
  override fun getMainComponentName(): String = "RemindRx"

  // react-native-screens: don't restore fragments from a saved state.
  override fun onCreate(savedInstanceState: Bundle?) {
    super.onCreate(null)
    showOverLockScreenIfRinging()
  }

  override fun onNewIntent(intent: Intent) {
    super.onNewIntent(intent)
    showOverLockScreenIfRinging()
  }

  /**
   * A full-screen alarm launches this activity while the phone is locked. It
   * must appear over the keyguard before JS has rendered anything, so decide
   * here: locked + one of our alarm notifications is up → show over the lock
   * screen. The ringer turns it off again when dismissed
   * (RxSystemModule.setShowOverLockScreen), so the rest of the app stays
   * behind the keyguard.
   */
  private fun showOverLockScreenIfRinging() {
    if (Build.VERSION.SDK_INT < 27) return
    val keyguard = getSystemService(KeyguardManager::class.java)
    val notifications = getSystemService(NotificationManager::class.java)
    val ringing = notifications.activeNotifications.any { it.notification.channelId == ALARM_CHANNEL }
    if (keyguard.isKeyguardLocked && ringing) {
      setShowWhenLocked(true)
      setTurnScreenOn(true)
    }
  }

  /**
   * Returns the instance of the [ReactActivityDelegate]. We use [DefaultReactActivityDelegate]
   * which allows you to enable New Architecture with a single boolean flags [fabricEnabled]
   */
  override fun createReactActivityDelegate(): ReactActivityDelegate =
      DefaultReactActivityDelegate(this, mainComponentName, fabricEnabled)

  companion object {
    /** Must match CHANNEL_ALARM in src/reminders/ReminderService.ts. */
    const val ALARM_CHANNEL = "rx-alarm"
  }
}
