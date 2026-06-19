import { useEffect, useRef } from 'react'
import type { MonteCarloResult } from '../types'

/**
 * Animated Monte Carlo fan chart.
 *
 * Draws a stratified sample of cumulative-net trajectories (mc.sample_paths) onto a
 * canvas, revealing them left-to-right so the uncertainty cone visibly fans out year
 * by year. Paths are tinted green/red by their final outcome and stacked at low alpha,
 * so overlap builds a density gradient. The median path glows; the p10/p50/p90
 * endpoints are pinned to the right edge. Click to replay.
 */

const ANIM_MS = 1500
const HEIGHT = 220
const PAD = { l: 10, r: 10, t: 14, b: 22 }

const GREEN = '74, 222, 128'   // --green
const RED = '248, 113, 113'    // --red
const MUTED = '136, 146, 164'  // --muted
const ACCENT = '108, 142, 247' // --accent

function fmtShort(n: number) {
  if (Math.abs(n) >= 1_000_000) return `$${(n / 1_000_000).toFixed(1)}M`
  if (Math.abs(n) >= 1_000) return `$${(n / 1_000).toFixed(0)}k`
  return `$${n.toFixed(0)}`
}

export default function MonteCarloChart({ mc }: { mc: MonteCarloResult }) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const wrapRef = useRef<HTMLDivElement>(null)
  const rafRef = useRef<number>(0)

  useEffect(() => {
    const canvas = canvasRef.current
    const wrap = wrapRef.current
    const paths = mc.sample_paths
    if (!canvas || !wrap || !paths.length) return

    const ctx = canvas.getContext('2d')
    if (!ctx) return

    const years = paths[0].length
    const midIdx = Math.floor(paths.length / 2)

    // Value domain across every sampled point, always including the zero baseline.
    let minV = 0
    let maxV = 0
    for (const p of paths) for (const v of p) {
      if (v < minV) minV = v
      if (v > maxV) maxV = v
    }
    const span = maxV - minV || 1
    minV -= span * 0.08
    maxV += span * 0.08

    let width = wrap.clientWidth || 320
    const dpr = window.devicePixelRatio || 1

    function resize() {
      width = wrap!.clientWidth || width
      canvas!.width = Math.round(width * dpr)
      canvas!.height = Math.round(HEIGHT * dpr)
      canvas!.style.width = `${width}px`
      canvas!.style.height = `${HEIGHT}px`
    }

    const plotW = () => width - PAD.l - PAD.r
    const plotH = HEIGHT - PAD.t - PAD.b
    // yearIdx 0 = origin (net 0); 1..years = end of each simulated year.
    const xAt = (yearIdx: number) => PAD.l + (plotW() * yearIdx) / years
    const yAt = (v: number) => PAD.t + plotH * (1 - (v - minV) / (maxV - minV))

    /** Trace a path's polyline up to `reveal` (a fractional year count). */
    function trace(p: number[], reveal: number) {
      ctx!.beginPath()
      ctx!.moveTo(xAt(0), yAt(0))
      for (let yi = 0; yi < years; yi++) {
        const segEnd = yi + 1
        if (reveal >= segEnd) {
          ctx!.lineTo(xAt(segEnd), yAt(p[yi]))
        } else if (reveal > yi) {
          const frac = reveal - yi
          const prevV = yi === 0 ? 0 : p[yi - 1]
          ctx!.lineTo(xAt(yi) + (xAt(segEnd) - xAt(yi)) * frac, yAt(prevV + (p[yi] - prevV) * frac))
          break
        } else {
          break
        }
      }
    }

    function dot(x: number, y: number, rgb: string, label: string, align: 'top' | 'bottom') {
      ctx!.fillStyle = `rgb(${rgb})`
      ctx!.shadowColor = `rgb(${rgb})`
      ctx!.shadowBlur = 8
      ctx!.beginPath()
      ctx!.arc(x, y, 3.5, 0, Math.PI * 2)
      ctx!.fill()
      ctx!.shadowBlur = 0
      ctx!.font = '600 10px system-ui, sans-serif'
      ctx!.textAlign = 'right'
      ctx!.textBaseline = align === 'top' ? 'bottom' : 'top'
      ctx!.fillText(label, x - 6, align === 'top' ? y - 4 : y + 4)
    }

    let start = 0
    function frame(now: number) {
      if (!start) start = now
      const t = Math.min((now - start) / ANIM_MS, 1)
      const ease = 1 - Math.pow(1 - t, 3) // easeOutCubic
      const reveal = ease * years

      ctx!.setTransform(dpr, 0, 0, dpr, 0, 0)
      ctx!.clearRect(0, 0, width, HEIGHT)

      // Zero baseline.
      ctx!.strokeStyle = `rgba(${MUTED}, 0.4)`
      ctx!.lineWidth = 1
      ctx!.setLineDash([4, 4])
      ctx!.beginPath()
      ctx!.moveTo(PAD.l, yAt(0))
      ctx!.lineTo(width - PAD.r, yAt(0))
      ctx!.stroke()
      ctx!.setLineDash([])

      // Faint trajectory fan.
      ctx!.lineWidth = 1.25
      for (let i = 0; i < paths.length; i++) {
        if (i === midIdx) continue
        const final = paths[i][years - 1]
        ctx!.strokeStyle = `rgba(${final >= 0 ? GREEN : RED}, 0.16)`
        trace(paths[i], reveal)
        ctx!.stroke()
      }

      // Glowing median path on top.
      ctx!.strokeStyle = `rgb(${ACCENT})`
      ctx!.lineWidth = 2
      ctx!.shadowColor = `rgba(${ACCENT}, 0.9)`
      ctx!.shadowBlur = 10
      trace(paths[midIdx], reveal)
      ctx!.stroke()
      ctx!.shadowBlur = 0

      // Year ticks.
      ctx!.fillStyle = `rgba(${MUTED}, 0.7)`
      ctx!.font = '10px system-ui, sans-serif'
      ctx!.textAlign = 'center'
      ctx!.textBaseline = 'alphabetic'
      for (let yi = 1; yi <= years; yi++) ctx!.fillText(`Y${yi}`, xAt(yi), HEIGHT - 6)

      if (t < 1) {
        rafRef.current = requestAnimationFrame(frame)
      } else {
        // Pin the headline percentiles to the right edge once the fan settles.
        const xEnd = xAt(years)
        dot(xEnd, yAt(mc.cumulative_net_p90), GREEN, fmtShort(mc.cumulative_net_p90), 'top')
        dot(xEnd, yAt(mc.cumulative_net_p10), RED, fmtShort(mc.cumulative_net_p10), 'bottom')
      }
    }

    function play() {
      start = 0
      cancelAnimationFrame(rafRef.current)
      resize()
      rafRef.current = requestAnimationFrame(frame)
    }

    play()
    window.addEventListener('resize', play)
    wrap.addEventListener('click', play)
    return () => {
      cancelAnimationFrame(rafRef.current)
      window.removeEventListener('resize', play)
      wrap.removeEventListener('click', play)
    }
  }, [mc.scenario_id, mc.sample_paths, mc.cumulative_net_p10, mc.cumulative_net_p90])

  if (!mc.sample_paths.length) return null

  return (
    <div className="mc-chart">
      <div className="mc-chart-wrap" ref={wrapRef} title="Click to replay">
        <canvas ref={canvasRef} className="mc-chart-canvas" />
        <span className="mc-chart-hint">▸ replay</span>
      </div>
      <div className="mc-legend">
        <span><i className="mc-dot" style={{ background: `rgb(${GREEN})` }} /> ends in the green</span>
        <span><i className="mc-dot" style={{ background: `rgb(${RED})` }} /> ends in the red</span>
        <span><i className="mc-dot" style={{ background: `rgb(${ACCENT})` }} /> median path</span>
        <span className="mc-legend-note">{mc.sample_paths.length} of {mc.n_simulations.toLocaleString()} paths</span>
      </div>
    </div>
  )
}
