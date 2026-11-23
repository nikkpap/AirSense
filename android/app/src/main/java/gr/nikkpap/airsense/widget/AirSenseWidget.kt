package gr.nikkpap.airsense.widget

import android.app.PendingIntent
import android.appwidget.AppWidgetManager
import android.appwidget.AppWidgetProvider
import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.view.View
import android.widget.RemoteViews
import androidx.work.OneTimeWorkRequestBuilder
import androidx.work.WorkManager
import gr.nikkpap.airsense.MainActivity
import gr.nikkpap.airsense.R
import gr.nikkpap.airsense.data.Prefs
import gr.nikkpap.airsense.data.Status
import gr.nikkpap.airsense.data.f
import gr.nikkpap.airsense.work.CheckWorker
import org.json.JSONObject
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

/**
 * Home-screen widget: temperature + humidity of the chosen sensor, status dot, last update.
 * Tap = open AirSense · ↻ = refresh now. Updated by the app, the background check and every 30 min.
 * Nikolaos K. Paridis (aka nikkpap) · ALU DEV TEAM
 */
class AirSenseWidget : AppWidgetProvider() {

    override fun onUpdate(ctx: Context, mgr: AppWidgetManager, ids: IntArray) {
        render(ctx, mgr, ids)
        refresh(ctx)
    }

    override fun onReceive(ctx: Context, intent: Intent) {
        super.onReceive(ctx, intent)
        if (intent.action == ACTION_REFRESH) {
            render(ctx, AppWidgetManager.getInstance(ctx), null, refreshing = true)
            refresh(ctx)
        }
    }

    companion object {
        const val ACTION_REFRESH = "gr.nikkpap.airsense.widget.REFRESH"
        private const val KEY = "widgetCache"

        private fun refresh(ctx: Context) {
            runCatching {
                WorkManager.getInstance(ctx).enqueue(OneTimeWorkRequestBuilder<CheckWorker>().build())
            }
        }

        /** Called by the app and by the background check after every successful read. */
        fun save(ctx: Context, st: Status) {
            val p = Prefs(ctx)
            val devs = st.devices.filter { it.enabled }
            val d = devs.firstOrNull { it.id == p.selected } ?: devs.firstOrNull { it.online == true } ?: devs.firstOrNull()
            val j = JSONObject()
                .put("name", d?.name ?: "—").put("online", d?.online == true)
                .put("t", d?.t ?: JSONObject.NULL).put("h", d?.h ?: JSONObject.NULL)
                .put("dp", d?.dp ?: JSONObject.NULL).put("count", devs.size)
                .put("ts", System.currentTimeMillis()).put("server", true)
            ctxPrefs(ctx).edit().putString(KEY, j.toString()).apply()
            updateAll(ctx)
        }

        /** Server did not answer: keep the last values, mark them as old. */
        fun markOffline(ctx: Context) {
            val sp = ctxPrefs(ctx)
            val j = runCatching { JSONObject(sp.getString(KEY, "{}") ?: "{}") }.getOrDefault(JSONObject())
            sp.edit().putString(KEY, j.put("server", false).toString()).apply()
            updateAll(ctx)
        }

        fun updateAll(ctx: Context) {
            val mgr = AppWidgetManager.getInstance(ctx)
            val ids = mgr.getAppWidgetIds(ComponentName(ctx, AirSenseWidget::class.java))
            if (ids.isNotEmpty()) render(ctx, mgr, ids)
        }

        private fun ctxPrefs(ctx: Context) = ctx.applicationContext.getSharedPreferences("airsense_widget", Context.MODE_PRIVATE)

        private fun render(ctx: Context, mgr: AppWidgetManager, idsIn: IntArray?, refreshing: Boolean = false) {
            val ids = idsIn ?: mgr.getAppWidgetIds(ComponentName(ctx, AirSenseWidget::class.java))
            if (ids.isEmpty()) return
            val p = Prefs(ctx)
            val en = p.lang == "en"
            val j = runCatching { JSONObject(ctxPrefs(ctx).getString(KEY, "{}") ?: "{}") }.getOrDefault(JSONObject())
            val has = j.has("ts")
            val t = if (j.isNull("t")) null else j.optDouble("t")
            val h = if (j.isNull("h")) null else j.optDouble("h")
            val ok = j.optBoolean("online") && j.optBoolean("server", true)
            val time = if (has) SimpleDateFormat("HH:mm", Locale.getDefault()).format(Date(j.optLong("ts"))) else "—"

            for (id in ids) {
                val v = RemoteViews(ctx.packageName, R.layout.widget_airsense)
                v.setTextViewText(R.id.w_name, if (has) j.optString("name") else "AirSense")
                v.setTextViewText(R.id.w_temp, if (t != null) "${f(t)}°" else "—")
                v.setTextViewText(R.id.w_hum, if (h != null) "${f(h)}%" else "—")
                v.setTextViewText(
                    R.id.w_time,
                    when {
                        refreshing -> if (en) "updating…" else "ενημέρωση…"
                        !p.configured -> if (en) "open the app to connect" else "άνοιξε την εφαρμογή"
                        !has -> if (en) "waiting for data" else "αναμονή δεδομένων"
                        !j.optBoolean("server", true) -> (if (en) "server offline · " else "server εκτός · ") + time
                        else -> time
                    }
                )
                v.setTextColor(R.id.w_dot, if (ok) 0xFF2ECC71.toInt() else 0xFFFF5C5C.toInt())
                v.setViewVisibility(R.id.w_dot, if (has) View.VISIBLE else View.GONE)
                val open = PendingIntent.getActivity(
                    ctx, 0, Intent(ctx, MainActivity::class.java).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK),
                    PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
                )
                v.setOnClickPendingIntent(R.id.w_root, open)
                val rf = PendingIntent.getBroadcast(
                    ctx, 1, Intent(ctx, AirSenseWidget::class.java).setAction(ACTION_REFRESH),
                    PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
                )
                v.setOnClickPendingIntent(R.id.w_refresh, rf)
                mgr.updateAppWidget(id, v)
            }
        }
    }
}
