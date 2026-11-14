/** One burst of paper from both lower corners, in the given colours. Nothing under reduced-motion settings. */
export function confetti(colors: string[]) {
  if (matchMedia('(prefers-reduced-motion: reduce)').matches || !colors.length) return
  const canvas = Object.assign(document.createElement('canvas'), { width: innerWidth, height: innerHeight })
  Object.assign(canvas.style, { position: 'fixed', inset: '0', pointerEvents: 'none', zIndex: '60' })
  document.body.append(canvas)
  const context = canvas.getContext('2d')
  if (!context) return
  const ctx: CanvasRenderingContext2D = context
  const pieces = Array.from({ length: 180 }, (_, i) => {
    const left = i % 2 === 0
    return {
      x: left ? 0 : innerWidth,
      y: innerHeight * (0.75 + Math.random() * 0.25),
      vx: (left ? 1 : -1) * (innerWidth / 150) * (0.4 + Math.random() * 1.6),
      vy: -(innerHeight / 60) * (0.7 + Math.random() * 0.9),
      w: 6 + Math.random() * 8,
      h: 4 + Math.random() * 6,
      turn: Math.random() * Math.PI,
      spin: (Math.random() - 0.5) * 0.4,
      color: colors[i % colors.length] ?? '#ffffff',
    }
  })
  const started = performance.now()
  const LASTS = 3400
  function frame(now: number) {
    const age = now - started
    ctx.clearRect(0, 0, canvas.width, canvas.height)
    ctx.globalAlpha = Math.min(1, (LASTS - age) / 600)
    for (const p of pieces) {
      p.vy += 0.32
      p.vx *= 0.992
      p.x += p.vx
      p.y += p.vy
      p.turn += p.spin
      ctx.save()
      ctx.translate(p.x, p.y)
      ctx.rotate(p.turn)
      ctx.fillStyle = p.color
      // a piece seen edge-on narrows, which is what makes it read as paper
      ctx.fillRect(-p.w / 2, -p.h / 2, p.w, p.h * Math.abs(Math.cos(p.turn * 1.7)))
      ctx.restore()
    }
    if (age < LASTS) requestAnimationFrame(frame)
    else canvas.remove()
  }
  requestAnimationFrame(frame)
}
