package gr.nikkpap.airsense.ui

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.gestures.detectHorizontalDragGestures
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.material3.MaterialTheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableFloatStateOf
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.CornerRadius
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.PathEffect
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.StrokeJoin
import androidx.compose.ui.graphics.drawscope.DrawScope
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.layout.onSizeChanged
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.drawText
import androidx.compose.ui.text.rememberTextMeasurer
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import gr.nikkpap.airsense.data.HistPoint
import gr.nikkpap.airsense.data.WxPoint
import gr.nikkpap.airsense.data.f
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import kotlin.math.abs
import kotlin.math.max

private fun range(v: List<Double>): Pair<Double, Double> {
    if (v.isEmpty()) return 0.0 to 1.0
    var lo = v.min()
    var hi = v.max()
    if (hi - lo < 1.0) {
        lo -= 0.5
        hi += 0.5
    }
    val p = (hi - lo) * 0.1
    return (lo - p) to (hi + p)
}

/**
 * Γράφημα δύο αξόνων: θερμοκρασία (αριστερά), υγρασία (δεξιά), σημείο δρόσου,
 * εξωτερικές τιμές Open-Meteo (διακεκομμένες) και μπάρες βροχής/χιονιού. Άγγιγμα/σύρσιμο = τιμές.
 */
@Composable
fun HygroChart(points: List<HistPoint>, wx: List<WxPoint>, modifier: Modifier = Modifier, outLabel: String? = null) {
    val tm = rememberTextMeasurer()
    var hover by remember(points) { mutableIntStateOf(-1) }
    var widthPx by remember { mutableFloatStateOf(1f) }
    val density = LocalDensity.current
    val padL = with(density) { 40.dp.toPx() }
    val padR = with(density) { 36.dp.toPx() }
    val grid = MaterialTheme.colorScheme.outlineVariant
    val labelC = MaterialTheme.colorScheme.onSurfaceVariant
    val tipBg = MaterialTheme.colorScheme.surfaceVariant
    val tipFg = MaterialTheme.colorScheme.onSurface
    val lOut = outLabel ?: tr("Έξω", "Out")
    val lDew = tr("Δρόσος", "Dew")
    val lEmpty = tr("Δεν υπάρχουν δεδομένα για το διάστημα", "No data for this period")
    val valid = remember(points) { points.filter { it.t != null || it.h != null } }

    fun pick(x: Float) {
        if (valid.isEmpty()) return
        val x0 = valid.first().ts
        val x1 = if (valid.last().ts > x0) valid.last().ts else x0 + 60.0
        val frac = ((x - padL) / (widthPx - padL - padR)).toDouble()
        val target = x0 + frac * (x1 - x0)
        hover = points.indices
            .filter { points[it].t != null || points[it].h != null }
            .minByOrNull { abs(points[it].ts - target) } ?: -1
    }

    Canvas(
        modifier
            .fillMaxWidth()
            .height(290.dp)
            .onSizeChanged { widthPx = it.width.toFloat() }
            .pointerInput(points) { detectTapGestures { o -> pick(o.x) } }
            .pointerInput(points) { detectHorizontalDragGestures { change, _ -> pick(change.position.x) } }
    ) {
        val top = 8.dp.toPx()
        val bottom = 22.dp.toPx()
        val pw = size.width - padL - padR
        val ph = size.height - top - bottom
        val small = TextStyle(fontSize = 10.sp, color = labelC)
        if (valid.isEmpty()) {
            val lay = tm.measure(lEmpty, small)
            drawText(lay, topLeft = Offset((size.width - lay.size.width) / 2f, (size.height - lay.size.height) / 2f))
            return@Canvas
        }
        val x0 = valid.first().ts
        val x1 = if (valid.last().ts > x0) valid.last().ts else x0 + 60.0
        val w = wx.filter { it.ts in x0..x1 }
        val (t0, t1) = range(valid.mapNotNull { it.t } + valid.mapNotNull { it.dp } + w.mapNotNull { it.t })
        val (h0, h1) = range(valid.mapNotNull { it.h } + w.mapNotNull { it.h })

        fun xOf(ts: Double): Float = padL + ((ts - x0) / (x1 - x0)).toFloat() * pw
        fun yT(v: Double): Float = top + ph - ((v - t0) / (t1 - t0)).toFloat() * ph
        fun yH(v: Double): Float = top + ph - ((v - h0) / (h1 - h0)).toFloat() * ph

        // πλέγμα + ετικέτες αξόνων
        for (i in 0..5) {
            val y = top + ph * i / 5f
            drawLine(grid, Offset(padL, y), Offset(padL + pw, y), 1f)
            val tl = tm.measure(String.format(Locale.US, "%.1f", t1 - (t1 - t0) * i / 5.0), small.copy(color = TempC))
            drawText(tl, topLeft = Offset(padL - tl.size.width - 4f, y - tl.size.height / 2f))
            val hl = tm.measure(String.format(Locale.US, "%.0f", h1 - (h1 - h0) * i / 5.0), small.copy(color = HumC))
            drawText(hl, topLeft = Offset(padL + pw + 4f, y - hl.size.height / 2f))
        }
        val span = x1 - x0
        val tf = SimpleDateFormat(if (span <= 2 * 86400) "HH:mm" else "dd/MM", Locale.getDefault())
        for (i in 0..4) {
            val ts = x0 + span * i / 4.0
            val lay = tm.measure(tf.format(Date((ts * 1000).toLong())), small)
            val lx = (xOf(ts) - lay.size.width / 2f).coerceIn(0f, size.width - lay.size.width)
            drawText(lay, topLeft = Offset(lx, size.height - lay.size.height))
        }

        // μπάρες βροχής / χιονιού (Open-Meteo)
        val pmax = max(1.0, w.maxOfOrNull { max(it.precip ?: 0.0, it.snow ?: 0.0) } ?: 0.0)
        for (p in w) {
            val v = max(p.precip ?: 0.0, p.snow ?: 0.0)
            if (v <= 0.0) continue
            val bh = (v / pmax).toFloat() * ph * 0.35f
            val col = if ((p.snow ?: 0.0) > 0.0) Color(0x99E6F0FF) else Color(0x775AA9FF)
            drawRect(col, topLeft = Offset(xOf(p.ts) - 2.dp.toPx(), top + ph - bh), size = Size(4.dp.toPx(), bh))
        }

        fun DrawScope.series(vals: List<Pair<Double, Double?>>, y: (Double) -> Float, color: Color, width: Float, dashed: Boolean) {
            val path = Path()
            var pen = false
            for ((ts, v) in vals) {
                if (v == null) {
                    pen = false
                    continue
                }
                val px = xOf(ts)
                val py = y(v)
                if (!pen) {
                    path.moveTo(px, py)
                    pen = true
                } else path.lineTo(px, py)
            }
            drawPath(
                path, color,
                style = Stroke(
                    width = width, cap = StrokeCap.Round, join = StrokeJoin.Round,
                    pathEffect = if (dashed) PathEffect.dashPathEffect(floatArrayOf(14f, 10f)) else null
                )
            )
        }
        val sw = 2.2.dp.toPx()
        series(w.map { it.ts to it.t }, ::yT, OutTC, 1.6.dp.toPx(), true)
        series(w.map { it.ts to it.h }, ::yH, OutHC, 1.6.dp.toPx(), true)
        series(points.map { it.ts to it.dp }, ::yT, DewC, 1.3.dp.toPx(), true)
        series(points.map { it.ts to it.h }, ::yH, HumC, sw, false)
        series(points.map { it.ts to it.t }, ::yT, TempC, sw, false)
        if (valid.size < 40) {
            for (p in valid) {
                p.t?.let { drawCircle(TempC, 3.dp.toPx(), Offset(xOf(p.ts), yT(it))) }
                p.h?.let { drawCircle(HumC, 3.dp.toPx(), Offset(xOf(p.ts), yH(it))) }
            }
        }

        // tooltip
        if (hover in points.indices) {
            val p = points[hover]
            val x = xOf(p.ts)
            drawLine(labelC.copy(alpha = 0.7f), Offset(x, top), Offset(x, top + ph), 1.5f)
            val near = w.minByOrNull { abs(it.ts - p.ts) }?.takeIf { abs(it.ts - p.ts) < 7200 }
            val lines = buildList {
                add(SimpleDateFormat("dd/MM HH:mm", Locale.getDefault()).format(Date((p.ts * 1000).toLong())))
                add("🌡 ${f(p.t)} °C   💧 ${f(p.h)} %")
                add("$lDew ${f(p.dp)} °C")
                if (near != null) add("$lOut ${f(near.t)} °C · ${f(near.h, 0)} %")
            }
            val lays = lines.map { tm.measure(it, TextStyle(fontSize = 11.sp, color = tipFg)) }
            val bw = lays.maxOf { it.size.width } + 16.dp.toPx()
            val bh = lays.sumOf { it.size.height } + 12.dp.toPx()
            var bx = x + 10.dp.toPx()
            if (bx + bw > size.width) bx = x - bw - 10.dp.toPx()
            drawRoundRect(tipBg, Offset(bx, top + 4f), Size(bw, bh), CornerRadius(8.dp.toPx()))
            var yy = top + 4f + 6.dp.toPx()
            for (l in lays) {
                drawText(l, topLeft = Offset(bx + 8.dp.toPx(), yy))
                yy += l.size.height
            }
        }
    }
}
