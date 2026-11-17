import { useEffect } from "react";

/**
 * Cursor interaction for mouse users: a faint light follows the pointer, panels and stats
 * highlight under it, and primary buttons lean toward it. It does nothing on touch screens
 * or when the user asks for reduced motion.
 */
export function useCursorFx() {
  useEffect(() => {
    const fine = matchMedia("(hover: hover) and (pointer: fine)").matches;
    const reduced = matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (!fine || reduced) return;

    const root = document.documentElement;
    let frame = 0;
    let last: PointerEvent | null = null;

    const run = () => {
      frame = 0;
      const ev = last;
      if (!ev) return;
      root.style.setProperty("--cx", ev.clientX + "px");
      root.style.setProperty("--cy", ev.clientY + "px");

      const target = ev.target instanceof Element ? ev.target : null;
      const lit = target?.closest<HTMLElement>(".panel, .stat");
      if (lit) {
        const r = lit.getBoundingClientRect();
        lit.style.setProperty("--mx", ev.clientX - r.left + "px");
        lit.style.setProperty("--my", ev.clientY - r.top + "px");
      }

      const btn = target?.closest<HTMLButtonElement>(".btn.primary") ?? null;
      document.querySelectorAll<HTMLElement>(".btn.primary.pulled").forEach((b) => {
        if (b !== btn) {
          b.classList.remove("pulled");
          b.style.transform = "";
        }
      });
      if (btn && !btn.disabled) {
        const r = btn.getBoundingClientRect();
        btn.classList.add("pulled");
        btn.style.transform = `translate(${((ev.clientX - r.left - r.width / 2) * 0.12).toFixed(1)}px, ${((ev.clientY - r.top - r.height / 2) * 0.22).toFixed(1)}px)`;
      }
    };

    const onMove = (ev: PointerEvent) => {
      last = ev;
      if (!frame) frame = requestAnimationFrame(run);
    };

    root.classList.add("fx");
    document.addEventListener("pointermove", onMove, { passive: true });
    return () => {
      document.removeEventListener("pointermove", onMove);
      if (frame) cancelAnimationFrame(frame);
      root.classList.remove("fx");
    };
  }, []);
}
