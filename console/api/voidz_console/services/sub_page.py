"""Browser-facing pages for subscription links.

``render_subscription_page`` is what a person sees when they open their
subscription URL in a browser; ``render_notice`` covers every other state
(not found, expired, out of data, unavailable). Proxy clients never see
either — gateway.py serves them raw payloads.

CSS and JS live in plain strings so they don't need brace escaping; only
the markup is assembled with f-strings, and every dynamic value goes
through ``esc``.
"""
from __future__ import annotations

import html
import io
from datetime import datetime, timezone
from urllib.parse import parse_qs, urlparse

import qrcode
import qrcode.image.svg


def esc(value) -> str:
    return html.escape(str(value), quote=True)


# ---------------------------------------------------------------------------
# Icons (24px grid, 1.75 stroke, drawn with currentColor)
# ---------------------------------------------------------------------------
_PATHS = {
    "copy": '<rect x="8.5" y="8.5" width="12" height="12" rx="2.75"/>'
            '<path d="M15.5 8.5V6.25A2.75 2.75 0 0 0 12.75 3.5h-6.5A2.75 2.75 0 0 0 3.5 6.25v6.5A2.75 2.75 0 0 0 6.25 15.5H8.5"/>',
    "check": '<path d="M5 12.5l4.25 4.25L19 7"/>',
    "qr": '<rect x="3.5" y="3.5" width="6.5" height="6.5" rx="1.5"/><rect x="14" y="3.5" width="6.5" height="6.5" rx="1.5"/>'
          '<rect x="3.5" y="14" width="6.5" height="6.5" rx="1.5"/><path d="M14 14h2.75v2.75H14zM17.75 17.75h2.75v2.75h-2.75zM14 20.5v0M20.5 14v0"/>',
    "globe": '<circle cx="12" cy="12" r="8.5"/><path d="M3.5 12h17M12 3.5c2.25 2.4 3.4 5.25 3.4 8.5s-1.15 6.1-3.4 8.5c-2.25-2.4-3.4-5.25-3.4-8.5s1.15-6.1 3.4-8.5z"/>',
    "chevron": '<path d="M7.5 10l4.5 4.5 4.5-4.5"/>',
    "close": '<path d="M6.75 6.75l10.5 10.5M17.25 6.75L6.75 17.25"/>',
    "data": '<ellipse cx="12" cy="6.25" rx="7.5" ry="2.75"/><path d="M4.5 6.25V12c0 1.52 3.36 2.75 7.5 2.75s7.5-1.23 7.5-2.75V6.25"/>'
            '<path d="M4.5 12v5.75c0 1.52 3.36 2.75 7.5 2.75s7.5-1.23 7.5-2.75V12"/>',
    "clock": '<circle cx="12" cy="12" r="8.5"/><path d="M12 7.5V12l3 1.75"/>',
    "devices": '<rect x="2.75" y="4.75" width="13.5" height="9.75" rx="2"/><path d="M6.5 18.5h6"/><rect x="17.25" y="9" width="4" height="10.5" rx="1.25"/>',
    "link": '<path d="M10 14a4 4 0 0 0 5.66 0l3-3a4 4 0 1 0-5.66-5.66l-1 1"/><path d="M14 10a4 4 0 0 0-5.66 0l-3 3a4 4 0 1 0 5.66 5.66l1-1"/>',
    "shield": '<path d="M12 3.5l7 2.75v5.25c0 4.3-2.9 7.9-7 9-4.1-1.1-7-4.7-7-9V6.25z"/><path d="M9.25 12.25l1.9 1.9 3.6-3.9"/>',
    "info": '<circle cx="12" cy="12" r="8.5"/><path d="M12 11v5M12 8v.01"/>',
    "check-circle": '<circle cx="12" cy="12" r="8.5"/><path d="M8.5 12.25l2.4 2.4 4.6-4.9"/>',
    "alert": '<path d="M10.3 4.9a2 2 0 0 1 3.4 0l7 12.1A2 2 0 0 1 19 20H5a2 2 0 0 1-1.7-3z"/><path d="M12 10v3.5M12 16.5v.01"/>',
    "lock": '<rect x="5" y="10.5" width="14" height="10" rx="2.5"/><path d="M8.5 10.5V8a3.5 3.5 0 0 1 7 0v2.5"/>',
    "unlink": '<path d="M13.5 6.5l.75-.75a4 4 0 1 1 5.66 5.66l-.75.75M10.5 17.5l-.75.75a4 4 0 1 1-5.66-5.66l.75-.75"/><path d="M4 4l2.25 2.25M17.75 17.75L20 20"/>',
    "cloud-off": '<path d="M8 18.5h8.5a4 4 0 0 0 1.4-7.75A6 6 0 0 0 7.6 8.2 5 5 0 0 0 8 18.5z"/><path d="M3.5 3.5l17 17"/>',
}


def icon(name: str, cls: str = "ic") -> str:
    return f'<svg class="{cls}" viewBox="0 0 24 24" aria-hidden="true" focusable="false">{_PATHS[name]}</svg>'


# ---------------------------------------------------------------------------
# Shared styles
# ---------------------------------------------------------------------------
_BASE_CSS = r"""
:root{
  color-scheme:dark;
  --bg:#06080c;
  --surface:rgba(15,19,27,.74);
  --surface-2:rgba(255,255,255,.028);
  --surface-3:rgba(255,255,255,.055);
  --line:rgba(255,255,255,.07);
  --line-2:rgba(255,255,255,.11);
  --fg:#f2f5f8;
  --fg-2:#a8b2c0;
  --fg-3:#737d8c;
  --fg-4:#4c5462;
  --teal:#3ee0d8;
  --blue:#7fb4ff;
  --violet:#9d8cff;
  --accent:linear-gradient(115deg,#3ee0d8 0%,#7fb4ff 52%,#9d8cff 100%);
  --ok:#43d39e;
  --warn:#f5b547;
  --crit:#ff6b7d;
  --r-sm:10px;
  --r-md:14px;
  --r-lg:20px;
  --r-xl:26px;
  --ease:cubic-bezier(.2,.8,.2,1);
  --ease-out:cubic-bezier(.16,1,.3,1);
  --spring:cubic-bezier(.34,1.36,.64,1);
  --font:ui-sans-serif,-apple-system,BlinkMacSystemFont,"SF Pro Text","Segoe UI Variable Text","Segoe UI",Roboto,"Helvetica Neue",Arial,sans-serif;
  --mono:ui-monospace,"SF Mono","Cascadia Mono","JetBrains Mono",Menlo,Consolas,monospace;
}
[data-tone="ok"]{--tone:#43d39e;--tone-bg:rgba(67,211,158,.1);--tone-line:rgba(67,211,158,.26)}
[data-tone="warn"]{--tone:#f5b547;--tone-bg:rgba(245,181,71,.1);--tone-line:rgba(245,181,71,.28)}
[data-tone="crit"]{--tone:#ff6b7d;--tone-bg:rgba(255,107,125,.1);--tone-line:rgba(255,107,125,.28)}
[data-tone="muted"]{--tone:#a8b2c0;--tone-bg:rgba(255,255,255,.05);--tone-line:rgba(255,255,255,.1)}
*,*::before,*::after{box-sizing:border-box}
html{-webkit-text-size-adjust:100%;text-size-adjust:100%;background:var(--bg)}
body{margin:0;min-height:100vh;min-height:100dvh;background:var(--bg);color:var(--fg);
  font:400 14px/1.5 var(--font);letter-spacing:-.006em;
  -webkit-font-smoothing:antialiased;-moz-osx-font-smoothing:grayscale;
  -webkit-tap-highlight-color:transparent;overflow-x:hidden}
button{font:inherit;color:inherit;background:none;border:0;margin:0;padding:0;cursor:pointer;-webkit-appearance:none;appearance:none}
:focus{outline:none}
:focus-visible{outline:2px solid var(--teal);outline-offset:2px}
::selection{background:rgba(62,224,216,.28);color:#fff}
.ic{width:18px;height:18px;flex:none;fill:none;stroke:currentColor;stroke-width:1.75;stroke-linecap:round;stroke-linejoin:round}
.sr{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0);clip-path:inset(50%);white-space:nowrap}

.backdrop{position:fixed;inset:0;z-index:0;pointer-events:none;overflow:hidden}
.backdrop::before{content:"";position:absolute;inset:0;
  background-image:radial-gradient(rgba(255,255,255,.075) 1px,transparent 1.3px);background-size:24px 24px;
  -webkit-mask-image:radial-gradient(ellipse 75% 50% at 50% 0%,#000 25%,transparent 72%);
  mask-image:radial-gradient(ellipse 75% 50% at 50% 0%,#000 25%,transparent 72%)}
.glow{position:absolute;border-radius:50%;will-change:transform}
.glow--a{width:620px;height:460px;left:50%;top:-280px;margin-left:-360px;
  background:radial-gradient(closest-side,rgba(62,224,216,.32),rgba(62,224,216,0));animation:drift-a 19s var(--ease) infinite alternate}
.glow--b{width:560px;height:440px;left:50%;top:-220px;margin-left:-40px;
  background:radial-gradient(closest-side,rgba(157,140,255,.28),rgba(157,140,255,0));animation:drift-b 23s var(--ease) infinite alternate}
.glow--c{width:680px;height:560px;right:-300px;bottom:-360px;
  background:radial-gradient(closest-side,rgba(127,180,255,.14),rgba(127,180,255,0));animation:drift-a 29s var(--ease) infinite alternate-reverse}
@keyframes drift-a{to{transform:translate3d(-56px,36px,0) scale(1.1)}}
@keyframes drift-b{to{transform:translate3d(64px,24px,0) scale(.92)}}

.reveal{animation:reveal .75s var(--ease-out) both;animation-delay:calc(var(--i,0) * 70ms + 40ms)}
@keyframes reveal{from{opacity:0;translate:0 14px}to{opacity:1;translate:0 0}}

.eyebrow{font-size:11px;font-weight:600;letter-spacing:.14em;text-transform:uppercase;color:var(--fg-3)}

@media (prefers-reduced-motion:reduce){
  *,*::before,*::after{animation-duration:1ms!important;animation-delay:0ms!important;animation-iteration-count:1!important;
    transition-duration:1ms!important;transition-delay:0ms!important;scroll-behavior:auto!important}
}
"""

_SUB_CSS = r"""
.shell{position:relative;z-index:1;width:100%;max-width:640px;margin:0 auto;
  padding:max(16px,env(safe-area-inset-top)) 16px calc(36px + env(safe-area-inset-bottom))}
@media (min-width:600px){.shell{padding:28px 24px 48px}}

/* top bar */
.topbar{display:flex;align-items:center;justify-content:space-between;gap:12px;height:40px;margin-bottom:16px}
.brand{display:flex;align-items:center;gap:10px;font-size:15px;font-weight:650;letter-spacing:-.015em}
.brand img{width:28px;height:28px;object-fit:contain;filter:drop-shadow(0 0 12px rgba(62,224,216,.35))}
.sync{display:inline-flex;align-items:center;gap:8px;height:28px;padding:0 11px 0 10px;border-radius:999px;
  color:var(--fg-3);font-size:12px;font-variant-numeric:tabular-nums;white-space:nowrap;
  background:rgba(255,255,255,.025);box-shadow:inset 0 0 0 1px var(--line)}
.sync time{color:var(--fg-2);font-weight:500}
.dot{position:relative;width:6px;height:6px;flex:none;border-radius:50%;background:var(--tone,var(--ok))}
.dot::after{content:"";position:absolute;inset:-4px;border-radius:50%;box-shadow:0 0 0 1px var(--tone,var(--ok));opacity:0;animation:ping 2.6s var(--ease-out) infinite}
@keyframes ping{0%{transform:scale(.4);opacity:.75}80%,100%{transform:scale(1.5);opacity:0}}

/* pass card */
.pass{position:relative;isolation:isolate;overflow:hidden;border-radius:var(--r-xl);padding:22px;
  background:
    radial-gradient(120% 95% at 0% 0%,rgba(62,224,216,.15),rgba(62,224,216,0) 55%),
    radial-gradient(110% 90% at 100% 100%,rgba(157,140,255,.15),rgba(157,140,255,0) 55%),
    linear-gradient(160deg,#121823 0%,#0a0e15 100%);
  box-shadow:inset 0 1px 0 rgba(255,255,255,.05),0 32px 64px -32px rgba(0,0,0,.85);
  transform:perspective(1100px) rotateX(var(--rx,0deg)) rotateY(var(--ry,0deg));
  transition:transform .7s var(--ease-out)}
@media (min-width:600px){.pass{padding:26px}}
.pass.is-tracking{transition:transform .14s linear}
.pass::before{content:"";position:absolute;inset:0;z-index:2;border-radius:inherit;padding:1px;pointer-events:none;
  background:linear-gradient(135deg,rgba(62,224,216,.5),rgba(255,255,255,.07) 32%,rgba(255,255,255,.04) 68%,rgba(157,140,255,.45));
  -webkit-mask:linear-gradient(#000 0 0) content-box,linear-gradient(#000 0 0);-webkit-mask-composite:xor;
  mask:linear-gradient(#000 0 0) content-box exclude,linear-gradient(#000 0 0)}
.pass::after{content:"";position:absolute;inset:0;z-index:1;border-radius:inherit;pointer-events:none;
  background:radial-gradient(460px circle at var(--mx,50%) var(--my,0%),rgba(255,255,255,.075),rgba(255,255,255,0) 60%);
  opacity:var(--sheen,0);transition:opacity .5s var(--ease)}
.pass>*{position:relative;z-index:3}
.pass-head{display:flex;align-items:flex-start;justify-content:space-between;gap:16px}
.pass-id{min-width:0}
.pass-name{margin:8px 0 0;font-size:30px;line-height:1.08;font-weight:680;letter-spacing:-.032em;overflow-wrap:anywhere;
  background:linear-gradient(180deg,#fff 35%,#c3cbd7);-webkit-background-clip:text;background-clip:text;color:transparent}
.pass-sub{display:flex;flex-wrap:wrap;align-items:center;gap:4px 10px;margin-top:9px;color:var(--fg-2);font-size:13px}
.pass-sub .sep{width:3px;height:3px;border-radius:50%;background:var(--fg-4)}
.pass-sub b{font-weight:600;color:var(--fg);font-variant-numeric:tabular-nums}
.status{flex:none;display:inline-flex;align-items:center;gap:8px;height:28px;padding:0 12px 0 11px;border-radius:999px;
  font-size:12px;font-weight:600;letter-spacing:-.005em;white-space:nowrap;color:var(--tone);
  background:var(--tone-bg);box-shadow:inset 0 0 0 1px var(--tone-line)}

/* metrics */
.metrics{display:grid;grid-template-columns:1fr 1fr;margin-top:22px;border-radius:var(--r-lg);overflow:hidden;
  background:rgba(4,6,10,.5);box-shadow:inset 0 0 0 1px var(--line)}
.metric{min-width:0;padding:16px;box-shadow:-1px 0 0 var(--line),0 -1px 0 var(--line)}
.metric--wide{grid-column:1 / -1}
@media (min-width:600px){.metrics{grid-template-columns:repeat(3,minmax(0,1fr))}.metric--wide{grid-column:auto}.metric{padding:18px}}
.metric-label{display:flex;align-items:center;gap:7px;color:var(--fg-3);font-size:12px;font-weight:500}
.metric-label .ic{width:15px;height:15px}
.metric-value{display:flex;align-items:baseline;gap:5px;margin-top:10px;white-space:nowrap;font-variant-numeric:tabular-nums}
.metric-value .num{font-size:26px;line-height:1;font-weight:650;letter-spacing:-.035em}
.metric-value .num--inf{font-weight:500;letter-spacing:0}
.metric-value .unit{font-size:13px;font-weight:550;color:var(--fg-2)}
.metric-value .of{font-size:13px;color:var(--fg-3)}
.metric[data-tone="warn"] .num{color:var(--warn)}
.metric[data-tone="crit"] .num{color:var(--crit)}
.meter{position:relative;height:4px;margin-top:14px;border-radius:99px;background:rgba(255,255,255,.07);overflow:hidden}
.meter i{position:absolute;top:0;bottom:0;left:0;width:0;border-radius:inherit;background:var(--accent);
  transition:width 1.25s var(--ease-out) .35s}
.is-ready .meter i{width:calc(var(--p) * 100%)}
.metric[data-tone="warn"] .meter i{background:linear-gradient(90deg,#f5b547,#ff9d5c)}
.metric[data-tone="crit"] .meter i{background:linear-gradient(90deg,#ff9460,#ff6b7d)}
.meter--inf i{width:38%!important;background:linear-gradient(90deg,rgba(62,224,216,0),rgba(62,224,216,.75),rgba(157,140,255,0));
  transition:none;animation:sweep 2.8s var(--ease) infinite}
@keyframes sweep{from{translate:-100% 0}to{translate:265% 0}}
.slots{display:flex;gap:4px;height:4px;margin-top:14px}
.slots i{flex:1;border-radius:99px;background:rgba(255,255,255,.07);transition:background-color .6s var(--ease) .45s,box-shadow .6s var(--ease) .45s}
.is-ready .slots i.on{background:var(--ok);box-shadow:0 0 10px rgba(67,211,158,.45)}
.metric-foot{margin-top:10px;color:var(--fg-3);font-size:12px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;font-variant-numeric:tabular-nums}
.metric-foot b{font-weight:550;color:var(--fg-2)}

/* panels */
.panel{margin-top:14px;padding:18px;border-radius:var(--r-xl);background:var(--surface);
  box-shadow:inset 0 0 0 1px var(--line),0 24px 48px -32px rgba(0,0,0,.85);
  -webkit-backdrop-filter:blur(22px) saturate(1.25);backdrop-filter:blur(22px) saturate(1.25)}
@media (min-width:600px){.panel{padding:22px}}
.panel-head{display:flex;align-items:center;justify-content:space-between;gap:12px;min-height:34px}
.panel-title{display:flex;align-items:center;gap:8px;margin:0;font-size:16px;font-weight:650;letter-spacing:-.018em}
.panel-desc{margin:4px 0 0;color:var(--fg-3);font-size:13px}
.count{display:inline-grid;place-items:center;min-width:22px;height:20px;padding:0 7px;border-radius:999px;
  background:var(--surface-3);color:var(--fg-2);font-size:11.5px;font-weight:600;letter-spacing:0;font-variant-numeric:tabular-nums}

/* format switch */
.seg{position:relative;display:grid;grid-auto-flow:column;grid-auto-columns:minmax(0,1fr);margin-top:16px;padding:3px;
  border-radius:12px;background:rgba(0,0,0,.34);box-shadow:inset 0 0 0 1px var(--line)}
.seg-ind{position:absolute;top:3px;bottom:3px;left:0;width:0;border-radius:9px;
  background:linear-gradient(180deg,rgba(255,255,255,.115),rgba(255,255,255,.06));
  box-shadow:inset 0 0 0 1px rgba(255,255,255,.09),0 6px 14px -6px rgba(0,0,0,.7)}
.seg.is-ready .seg-ind{transition:transform .45s var(--ease-out),width .45s var(--ease-out)}
.seg-btn{position:relative;z-index:1;height:34px;padding:0 8px;border-radius:9px;font-size:13px;font-weight:550;
  color:var(--fg-3);white-space:nowrap;transition:color .25s var(--ease)}
.seg-btn:hover{color:var(--fg-2)}
.seg-btn[aria-selected="true"]{color:var(--fg)}
.seg-btn:focus-visible{outline-offset:-2px}

.linkbox{display:flex;align-items:center;gap:10px;height:48px;margin-top:10px;padding:0 14px;border-radius:var(--r-md);
  background:rgba(0,0,0,.3);box-shadow:inset 0 0 0 1px var(--line)}
.linkbox .ic{width:16px;height:16px;color:var(--fg-4)}
.link-text{flex:1;min-width:0;overflow:hidden;white-space:nowrap;text-overflow:ellipsis;
  font:500 12.5px/1.2 var(--mono);letter-spacing:0;color:var(--fg-2)}
.link-text .dim{color:var(--fg-4)}
.lk-ell{display:none}
@media (max-width:479px){.lk-host{display:none}.lk-ell{display:inline}}
.link-text .acc{color:var(--teal)}

.actions{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:8px;margin-top:10px}
.btn{position:relative;overflow:hidden;display:inline-flex;align-items:center;justify-content:center;gap:8px;height:44px;padding:0 18px;
  border-radius:12px;font-size:14px;font-weight:600;letter-spacing:-.012em;white-space:nowrap;user-select:none;-webkit-user-select:none;
  transition:transform .2s var(--ease),box-shadow .3s var(--ease),background-color .25s var(--ease),color .25s var(--ease)}
.btn:active{transform:scale(.98)}
.btn .ic{width:17px;height:17px}
.btn--primary{color:#03110f;background:var(--accent);
  box-shadow:inset 0 1px 0 rgba(255,255,255,.35),inset 0 -1px 0 rgba(0,0,0,.12),0 10px 24px -12px rgba(62,224,216,.65)}
.btn--primary:hover{box-shadow:inset 0 1px 0 rgba(255,255,255,.4),inset 0 -1px 0 rgba(0,0,0,.12),0 14px 30px -12px rgba(62,224,216,.85)}
.btn--primary::after{content:"";position:absolute;inset:0;pointer-events:none;
  background:linear-gradient(105deg,rgba(255,255,255,0) 35%,rgba(255,255,255,.45) 50%,rgba(255,255,255,0) 65%);
  translate:-120% 0;transition:translate .9s var(--ease-out)}
.btn--primary:hover::after{translate:120% 0}
.btn--ghost{color:var(--fg);background:var(--surface-3);box-shadow:inset 0 0 0 1px var(--line-2)}
.btn--ghost:hover{background:rgba(255,255,255,.085)}
.btn--sm{height:34px;padding:0 12px;border-radius:10px;font-size:13px;gap:7px}
.btn--sm .ic{width:15px;height:15px}

.swap{display:inline-grid;place-items:center}
.swap>*{grid-area:1 / 1;display:inline-flex;align-items:center;justify-content:center;gap:inherit;
  transition:opacity .22s var(--ease),translate .4s var(--ease-out)}
.btn .swap{gap:8px}
.btn--sm .swap{gap:7px}
.swap>:last-child{opacity:0;translate:0 7px}
.is-done .swap>:first-child{opacity:0;translate:0 -7px}
.is-done .swap>:last-child{opacity:1;translate:0 0}

.hint{display:flex;align-items:flex-start;gap:8px;margin:12px 2px 0;color:var(--fg-3);font-size:12.5px;line-height:1.45}
.hint .ic{width:15px;height:15px;margin-top:1px;color:var(--fg-4)}

/* filters */
.filters{display:flex;gap:6px;margin:14px -18px 0;padding:2px 18px;overflow-x:auto;scrollbar-width:none;
  -webkit-mask-image:linear-gradient(90deg,transparent 0,#000 18px,#000 calc(100% - 18px),transparent 100%);
  mask-image:linear-gradient(90deg,transparent 0,#000 18px,#000 calc(100% - 18px),transparent 100%)}
.filters::-webkit-scrollbar{display:none}
@media (min-width:600px){.filters{margin:16px -22px 0;padding:2px 22px}}
.chip{flex:none;display:inline-flex;align-items:center;gap:7px;height:32px;padding:0 12px;border-radius:999px;
  font-size:12.5px;font-weight:550;color:var(--fg-2);white-space:nowrap;background:var(--surface-2);box-shadow:inset 0 0 0 1px var(--line);
  transition:background-color .2s var(--ease),color .2s var(--ease),box-shadow .2s var(--ease)}
.chip:hover{color:var(--fg);background:var(--surface-3)}
.chip .n{font-size:11.5px;font-variant-numeric:tabular-nums;opacity:.55}
.chip[aria-pressed="true"]{color:#06080c;background:#e8edf3;box-shadow:none}
.chip[aria-pressed="true"] .n{opacity:.5}

/* config list */
.group{margin-top:16px}
.group[hidden]{display:none}
.group-head{display:flex;align-items:center;gap:8px;padding:0 4px 8px;color:var(--fg-3);
  font-size:11px;font-weight:600;letter-spacing:.1em;text-transform:uppercase}
.group-head .ic{width:14px;height:14px}
.group-head .n{margin-left:auto;letter-spacing:0;color:var(--fg-4);font-variant-numeric:tabular-nums}
.cfg-list{list-style:none;margin:0;padding:0;overflow:hidden;border-radius:var(--r-lg);
  background:rgba(0,0,0,.2);box-shadow:inset 0 0 0 1px var(--line)}
.cfg{position:relative}
.cfg+.cfg::before{content:"";position:absolute;top:0;left:60px;right:0;height:1px;background:var(--line)}
.cfg.rise{animation:row-in .55s var(--ease-out) both;animation-delay:calc(var(--base,280ms) + var(--d,0) * 32ms)}
@keyframes row-in{from{opacity:0;translate:0 6px}to{opacity:1;translate:0 0}}
.cfg-row{display:flex;align-items:center;gap:2px;padding:6px 6px 6px 4px;transition:background-color .2s var(--ease)}
.cfg:hover .cfg-row,.cfg.is-open .cfg-row{background:rgba(255,255,255,.022)}
.cfg-main{flex:1;min-width:0;display:flex;align-items:center;gap:12px;padding:6px;border-radius:12px;text-align:left}
.cfg-main:focus-visible{outline-offset:-2px}
.badge{flex:none;display:grid;place-items:center;width:38px;height:38px;border-radius:11px;
  font:700 15px/1 var(--font);letter-spacing:-.02em;color:var(--c);background:var(--c-bg);box-shadow:inset 0 0 0 1px var(--c-line)}
.tone-vless{--c:#93b6ff;--c-bg:rgba(147,182,255,.09);--c-line:rgba(147,182,255,.22)}
.tone-xhttp{--c:#f6c56f;--c-bg:rgba(246,197,111,.09);--c-line:rgba(246,197,111,.22)}
.tone-trojan{--c:#ff94a6;--c-bg:rgba(255,148,166,.09);--c-line:rgba(255,148,166,.22)}
.tone-ss{--c:#62e0b3;--c-bg:rgba(98,224,179,.09);--c-line:rgba(98,224,179,.22)}
.cfg-text{display:flex;flex-direction:column;gap:4px;min-width:0}
.cfg-title{overflow:hidden;white-space:nowrap;text-overflow:ellipsis;font-size:14px;line-height:1.2;font-weight:600;letter-spacing:-.012em}
.cfg-title .v{margin-left:6px;font-weight:450;color:var(--fg-3)}
.cfg-meta{display:flex;align-items:center;overflow:hidden;white-space:nowrap;font:500 11px/1.2 var(--mono);letter-spacing:.02em;color:var(--fg-3)}
.cfg-meta span+span::before{content:"";display:inline-block;width:3px;height:3px;margin:0 7px 2px;border-radius:50%;background:var(--fg-4);vertical-align:middle}
.cfg-chev{margin-left:auto;width:16px;height:16px;color:var(--fg-4);transition:transform .4s var(--ease-out),color .2s var(--ease)}
.cfg-main[aria-expanded="true"] .cfg-chev{transform:rotate(180deg);color:var(--fg-2)}
@media (max-width:419px){.cfg-chev{display:none}}
.cfg-actions{display:flex;gap:2px}
.icon-btn{display:grid;place-items:center;width:38px;height:38px;border-radius:11px;color:var(--fg-3);
  transition:background-color .2s var(--ease),color .2s var(--ease),transform .2s var(--ease)}
.icon-btn:hover{color:var(--fg);background:var(--surface-3)}
.icon-btn:active{transform:scale(.92)}
.icon-btn.is-done{color:var(--ok)}
.icon-btn .ic{width:18px;height:18px}
.cfg-detail{display:grid;grid-template-rows:0fr;transition:grid-template-rows .45s var(--ease-out)}
.cfg.is-open .cfg-detail{grid-template-rows:1fr}
.cfg-detail-in{min-height:0;overflow:hidden;opacity:0;transition:opacity .3s var(--ease)}
.cfg.is-open .cfg-detail-in{opacity:1;transition-delay:.08s}
.code{display:block;margin:0 12px 12px 60px;padding:10px 12px;max-height:128px;overflow:auto;border-radius:10px;
  background:rgba(0,0,0,.34);box-shadow:inset 0 0 0 1px var(--line);
  font:12px/1.6 var(--mono);letter-spacing:0;color:var(--fg-2);word-break:break-all;-webkit-user-select:all;user-select:all}
@media (max-width:419px){.code{margin-left:12px}}

/* footer */
.foot{display:flex;flex-direction:column;align-items:center;gap:8px;margin-top:28px;text-align:center;color:var(--fg-4);font-size:12px}
.foot-note{display:inline-flex;align-items:center;gap:7px;color:var(--fg-3)}
.foot-note .ic{width:15px;height:15px}

/* QR sheet */
.sheet{position:fixed;inset:0;z-index:50;display:grid;place-items:end center;padding:12px 12px calc(12px + env(safe-area-inset-bottom));
  visibility:hidden;pointer-events:none;transition:visibility 0s linear .5s}
@media (min-width:600px){.sheet{place-items:center}}
.sheet.is-open{visibility:visible;pointer-events:auto;transition:visibility 0s}
.sheet-scrim{position:absolute;inset:0;background:rgba(3,5,8,.64);-webkit-backdrop-filter:blur(8px);backdrop-filter:blur(8px);
  opacity:0;transition:opacity .35s var(--ease)}
.sheet.is-open .sheet-scrim{opacity:1}
.sheet-card{position:relative;width:100%;max-width:372px;padding:18px;border-radius:26px;
  background:linear-gradient(180deg,#141a24 0%,#0c1018 100%);
  box-shadow:inset 0 0 0 1px var(--line-2),0 40px 80px -24px rgba(0,0,0,.9);
  opacity:0;translate:0 28px;scale:.97;transition:opacity .28s var(--ease),translate .55s var(--ease-out),scale .55s var(--ease-out)}
.sheet.is-open .sheet-card{opacity:1;translate:0 0;scale:1}
.sheet-head{display:flex;align-items:flex-start;justify-content:space-between;gap:12px;padding:2px 2px 0 4px}
.sheet-title{margin:0;font-size:16px;font-weight:650;letter-spacing:-.018em}
.sheet-sub{margin:3px 0 0;color:var(--fg-3);font-size:13px}
.sheet-close{margin:-4px -4px 0 0}
.qr-frame{position:relative;display:grid;place-items:center;overflow:hidden;width:100%;max-width:264px;aspect-ratio:1 / 1;
  margin:18px auto 0;padding:14px;border-radius:20px;background:#fff;color:#5b6472;font-size:13px;line-height:1.45;text-align:center;
  box-shadow:0 0 0 1px rgba(255,255,255,.12),0 24px 56px -24px rgba(62,224,216,.45)}
.qr-frame svg{display:block;width:100%;height:100%;animation:qr-in .45s var(--ease-out) both}
@keyframes qr-in{from{opacity:0;scale:.96}to{opacity:1;scale:1}}
.qr-frame.is-loading::before{content:"";position:absolute;inset:14px;border-radius:8px;
  background:linear-gradient(100deg,#eef1f4 30%,#fafbfc 50%,#eef1f4 70%) 0 0 / 250% 100%;animation:shimmer 1.2s linear infinite}
@keyframes shimmer{from{background-position:120% 0}to{background-position:-120% 0}}
.qr-frame.is-error{padding:28px}
.sheet-actions{margin-top:18px}
.sheet-actions .btn{width:100%}

/* toast */
.toast{position:fixed;left:50%;bottom:calc(20px + env(safe-area-inset-bottom));z-index:40;display:flex;align-items:center;gap:9px;
  height:40px;padding:0 16px 0 13px;border-radius:999px;white-space:nowrap;font-size:13px;font-weight:550;color:var(--fg);
  background:rgba(19,24,33,.94);-webkit-backdrop-filter:blur(14px);backdrop-filter:blur(14px);
  box-shadow:inset 0 0 0 1px var(--line-2),0 18px 40px -14px rgba(0,0,0,.85);
  opacity:0;translate:-50% 14px;scale:.96;pointer-events:none;
  transition:opacity .22s var(--ease),translate .5s var(--spring),scale .5s var(--spring)}
.toast.is-on{opacity:1;translate:-50% 0;scale:1}
.toast .ic{width:16px;height:16px}
.toast .t-ok{color:var(--ok)}
.toast .t-err{color:var(--crit);display:none}
.toast[data-state="err"] .t-ok{display:none}
.toast[data-state="err"] .t-err{display:block}

.is-locked,.is-locked body{overflow:hidden}
"""

_NOTICE_CSS = r"""
.notice{position:relative;z-index:1;min-height:100vh;min-height:100dvh;display:grid;place-items:center;
  padding:max(24px,env(safe-area-inset-top)) 16px max(24px,env(safe-area-inset-bottom))}
.notice-card{position:relative;width:100%;max-width:412px;padding:32px 26px 26px;border-radius:var(--r-xl);text-align:center;
  background:var(--surface);box-shadow:inset 0 0 0 1px var(--line),0 32px 64px -32px rgba(0,0,0,.85);
  -webkit-backdrop-filter:blur(22px) saturate(1.25);backdrop-filter:blur(22px) saturate(1.25)}
.notice-icon{display:grid;place-items:center;width:56px;height:56px;margin:0 auto 18px;border-radius:18px;
  color:var(--tone);background:var(--tone-bg);box-shadow:inset 0 0 0 1px var(--tone-line)}
.notice-icon .ic{width:26px;height:26px}
.notice-card h1{margin:8px 0 0;font-size:21px;line-height:1.25;font-weight:650;letter-spacing:-.022em}
.notice-card p{margin:10px 0 0;color:var(--fg-2);font-size:14px;line-height:1.6}
.notice-card b{font-weight:600;color:var(--fg)}
.notice-card code{padding:2px 6px;border-radius:6px;background:var(--surface-3);font:12px var(--mono);color:var(--fg)}
.notice-brand{display:flex;align-items:center;justify-content:center;gap:8px;margin-top:26px;padding-top:18px;
  box-shadow:0 -1px 0 var(--line);color:var(--fg-4);font-size:12px;font-weight:500}
.notice-brand img{width:18px;height:18px;object-fit:contain;opacity:.85}
"""

_SUB_JS = r"""
(() => {
  'use strict';
  const doc = document, root = doc.documentElement;
  const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const $ = (s, r = doc) => r.querySelector(s);
  const $$ = (s, r = doc) => Array.from(r.querySelectorAll(s));

  requestAnimationFrame(() => requestAnimationFrame(() => doc.body.classList.add('is-ready')));

  $$('time[data-ts]').forEach(el => {
    const d = new Date(el.dateTime);
    if (!isNaN(d)) el.textContent = d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  });

  if (!reduce) {
    $$('[data-count]').forEach(el => {
      const to = parseFloat(el.dataset.count);
      const dec = parseInt(el.dataset.dec || '0', 10);
      if (!isFinite(to) || to <= 0) return;
      const final = el.textContent;
      el.textContent = (0).toFixed(dec);
      const start = performance.now() + 340, dur = 1150;
      const tick = now => {
        const p = Math.min(1, Math.max(0, (now - start) / dur));
        el.textContent = p >= 1 ? final : (to * (1 - Math.pow(1 - p, 4))).toFixed(dec);
        if (p < 1) requestAnimationFrame(tick);
      };
      requestAnimationFrame(tick);
    });
  }

  /* clipboard + feedback */
  const copyText = async text => {
    if (navigator.clipboard && window.isSecureContext) {
      try { await navigator.clipboard.writeText(text); return true; } catch (_) { /* fall through */ }
    }
    const ta = doc.createElement('textarea');
    ta.value = text;
    ta.setAttribute('readonly', '');
    ta.style.cssText = 'position:fixed;top:0;left:0;width:1px;height:1px;opacity:0;pointer-events:none';
    doc.body.appendChild(ta);
    ta.select();
    ta.setSelectionRange(0, text.length);
    let ok = false;
    try { ok = doc.execCommand('copy'); } catch (_) { ok = false; }
    ta.remove();
    return ok;
  };
  const toastEl = $('#toast'), toastMsg = $('#toast-msg');
  let toastTimer = 0;
  const toast = (msg, ok) => {
    toastMsg.textContent = msg;
    toastEl.dataset.state = ok ? 'ok' : 'err';
    toastEl.classList.add('is-on');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => toastEl.classList.remove('is-on'), 2000);
  };
  const markDone = btn => {
    btn.classList.add('is-done');
    clearTimeout(btn._doneTimer);
    btn._doneTimer = setTimeout(() => btn.classList.remove('is-done'), 1600);
  };
  const copyWith = async (btn, text, msg) => {
    if (await copyText(text)) { markDone(btn); if (msg) toast(msg, true); }
    else toast('Couldn’t copy — press and hold to copy manually', false);
  };

  /* format switch */
  const seg = $('.seg'), ind = $('.seg-ind'), linkAcc = $('#link-acc'), hint = $('#format-hint');
  let fmt = $('.seg-btn[aria-selected="true"]');
  const placeIndicator = () => {
    if (!fmt || !ind) return;
    ind.style.width = fmt.offsetWidth + 'px';
    ind.style.transform = 'translateX(' + fmt.offsetLeft + 'px)';
  };
  const selectFormat = btn => {
    $$('.seg-btn').forEach(b => {
      const on = b === btn;
      b.setAttribute('aria-selected', on ? 'true' : 'false');
      b.tabIndex = on ? 0 : -1;
    });
    fmt = btn;
    placeIndicator();
    linkAcc.textContent = btn.dataset.suffix;
    hint.textContent = btn.dataset.hint;
  };
  if (seg) {
    placeIndicator();
    requestAnimationFrame(() => seg.classList.add('is-ready'));
    if ('ResizeObserver' in window) new ResizeObserver(placeIndicator).observe(seg);
    else window.addEventListener('resize', placeIndicator);
    if (doc.fonts && doc.fonts.ready) doc.fonts.ready.then(placeIndicator);
  }

  /* region filter */
  const visibleRows = () => $$('.group:not([hidden]) .cfg');
  const setFilter = chip => {
    $$('.chip').forEach(c => c.setAttribute('aria-pressed', c === chip ? 'true' : 'false'));
    const key = chip.dataset.region;
    $$('.group').forEach(g => {
      const show = key === 'all' || g.dataset.region === key;
      if (show && g.hidden) {
        g.hidden = false;
        $$('.cfg', g).forEach((row, i) => {
          row.style.setProperty('--base', '0ms');
          row.style.setProperty('--d', i);
          row.classList.remove('rise');
          void row.offsetWidth;
          row.classList.add('rise');
        });
      } else if (!show) {
        g.hidden = true;
      }
    });
  };

  /* rows */
  const toggleRow = btn => {
    const row = btn.closest('.cfg');
    const open = btn.getAttribute('aria-expanded') !== 'true';
    btn.setAttribute('aria-expanded', open ? 'true' : 'false');
    row.classList.toggle('is-open', open);
  };

  /* QR sheet */
  const sheet = $('#sheet'), slot = $('#qr-slot'), sTitle = $('#sheet-title'), sSub = $('#sheet-sub');
  let sheetText = '', lastFocus = null;
  const focusables = () => $$('button:not([disabled])', sheet).filter(b => b.offsetParent !== null);
  const qrCache = new Map();
  const qrEndpoint = doc.body.dataset.qr;
  const loadQr = text => {
    if (!qrCache.has(text)) {
      const req = fetch(qrEndpoint, {
        method: 'POST', credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text })
      }).then(r => { if (!r.ok) throw new Error(r.status); return r.text(); });
      req.catch(() => qrCache.delete(text));
      qrCache.set(text, req);
    }
    return qrCache.get(text);
  };
  let qrToken = 0;
  const renderQr = text => {
    const mine = ++qrToken;
    slot.classList.remove('is-loaded', 'is-error');
    slot.classList.add('is-loading');
    slot.textContent = '';
    loadQr(text).then(svg => {
      if (mine !== qrToken) return;
      const tmp = doc.createElement('div');
      tmp.innerHTML = svg;
      const el = tmp.querySelector('svg');
      if (!el) throw new Error('bad svg');
      el.removeAttribute('width');
      el.removeAttribute('height');
      el.setAttribute('aria-hidden', 'true');
      slot.appendChild(el);
      slot.classList.remove('is-loading');
      slot.classList.add('is-loaded');
    }).catch(() => {
      if (mine !== qrToken) return;
      slot.classList.remove('is-loading');
      slot.classList.add('is-error');
      slot.textContent = 'QR code unavailable — copy the link instead.';
    });
  };
  const openSheet = (title, sub, text) => {
    renderQr(text);
    sTitle.textContent = title;
    sSub.textContent = sub;
    sheetText = text;
    $('.sheet-actions .btn', sheet).classList.remove('is-done');
    lastFocus = doc.activeElement;
    sheet.classList.add('is-open');
    sheet.setAttribute('aria-hidden', 'false');
    root.classList.add('is-locked');
    setTimeout(() => { const c = $('.sheet-close', sheet); if (c) c.focus({ preventScroll: true }); }, 50);
  };
  const closeSheet = () => {
    if (!sheet.classList.contains('is-open')) return;
    sheet.classList.remove('is-open');
    sheet.setAttribute('aria-hidden', 'true');
    root.classList.remove('is-locked');
    if (lastFocus && lastFocus.focus) lastFocus.focus({ preventScroll: true });
  };

  doc.addEventListener('click', e => {
    const el = e.target.closest('[data-action]');
    if (!el) return;
    const row = el.closest('.cfg');
    switch (el.dataset.action) {
      case 'format': selectFormat(el); break;
      case 'copy-sub': copyWith(el, fmt.dataset.href, 'Subscription link copied'); break;
      case 'qr-sub': openSheet('Subscription · ' + fmt.dataset.label, 'Scan with your client to import every config', fmt.dataset.href); break;
      case 'filter': setFilter(el); break;
      case 'copy-all': {
        const rows = visibleRows();
        copyWith(el, rows.map(r => r.dataset.url).join('\n'), rows.length + (rows.length === 1 ? ' config copied' : ' configs copied'));
        break;
      }
      case 'toggle': toggleRow(el); break;
      case 'copy': copyWith(el, row.dataset.url, 'Config copied'); break;
      case 'qr': openSheet(row.dataset.title, row.dataset.sub, row.dataset.url); break;
      case 'sheet-copy': copyWith(el, sheetText, ''); break;
      case 'close': closeSheet(); break;
    }
  });

  doc.addEventListener('keydown', e => {
    if (e.key === 'Escape') { closeSheet(); return; }
    if (e.key === 'Tab' && sheet.classList.contains('is-open')) {
      const f = focusables();
      if (!f.length) return;
      const first = f[0], last = f[f.length - 1];
      if (e.shiftKey && doc.activeElement === first) { last.focus(); e.preventDefault(); }
      else if (!e.shiftKey && doc.activeElement === last) { first.focus(); e.preventDefault(); }
      return;
    }
    const t = e.target;
    if (t.classList && t.classList.contains('seg-btn') && (e.key === 'ArrowRight' || e.key === 'ArrowLeft' || e.key === 'Home' || e.key === 'End')) {
      const btns = $$('.seg-btn');
      let i = btns.indexOf(t);
      if (e.key === 'ArrowRight') i = (i + 1) % btns.length;
      else if (e.key === 'ArrowLeft') i = (i - 1 + btns.length) % btns.length;
      else if (e.key === 'Home') i = 0;
      else i = btns.length - 1;
      selectFormat(btns[i]);
      btns[i].focus();
      e.preventDefault();
    }
  });

  /* pass card tilt (fine pointers only) */
  const pass = $('.pass');
  if (pass && !reduce && window.matchMedia('(hover: hover) and (pointer: fine)').matches) {
    let frame = 0;
    pass.addEventListener('pointermove', e => {
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(() => {
        const r = pass.getBoundingClientRect();
        const x = (e.clientX - r.left) / r.width, y = (e.clientY - r.top) / r.height;
        pass.classList.add('is-tracking');
        pass.style.setProperty('--mx', (x * 100).toFixed(2) + '%');
        pass.style.setProperty('--my', (y * 100).toFixed(2) + '%');
        pass.style.setProperty('--rx', ((0.5 - y) * 4).toFixed(2) + 'deg');
        pass.style.setProperty('--ry', ((x - 0.5) * 6).toFixed(2) + 'deg');
        pass.style.setProperty('--sheen', '1');
      });
    });
    pass.addEventListener('pointerleave', () => {
      cancelAnimationFrame(frame);
      pass.classList.remove('is-tracking');
      pass.style.setProperty('--rx', '0deg');
      pass.style.setProperty('--ry', '0deg');
      pass.style.setProperty('--sheen', '0');
    });
  }
})();
"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
_PROTOCOLS = {
    "vless-ws": ("VLESS", "", "V", "vless"),
    "xhttp-packet-up": ("xHTTP", "packet-up", "X", "xhttp"),
    "xhttp-stream-up": ("xHTTP", "stream-up", "X", "xhttp"),
    "trojan-ws": ("Trojan", "", "T", "trojan"),
    "shadowsocks": ("Shadowsocks", "", "S", "ss"),
}


def qr_svg(text: str) -> str:
    img = qrcode.make(text, image_factory=qrcode.image.svg.SvgPathImage, box_size=10, border=0)
    buf = io.BytesIO()
    img.save(buf)
    svg = buf.getvalue().decode()
    return svg[svg.find("<svg"):]


def _transport(url: str) -> list[str]:
    """Human summary of a share link: security, transport, port."""
    try:
        u = urlparse(url)
        port = str(u.port or 443)
    except ValueError:
        return []
    q = {k: v[0] for k, v in parse_qs(u.query).items()}
    if u.scheme == "ss":
        plugin = q.get("plugin", "").split(";")
        return ["TLS" if "tls" in plugin else "Plain", "WS", port]
    security = q.get("security", "")
    net = q.get("type", "")
    return [
        security.upper() if security and security != "none" else "Plain",
        {"ws": "WS", "xhttp": "xHTTP", "grpc": "gRPC", "tcp": "TCP"}.get(net, net.upper() or "TCP"),
        port,
    ]


def _middle(text: str, head: int, tail: int) -> str:
    return text if len(text) <= head + tail + 1 else f"{text[:head]}…{text[-tail:]}"


def _num(value: float) -> tuple[str, int]:
    """Display string and decimals for a GB amount."""
    dec = 2 if value < 10 else (1 if value < 100 else 0)
    return f"{value:.{dec}f}", dec


def _trim(value: float) -> str:
    return f"{value:.2f}".rstrip("0").rstrip(".")


def _favicon(logo_b64: str) -> str:
    return f'<link rel="icon" type="image/png" href="data:image/png;base64,{logo_b64}">'


def _head(title: str, logo_b64: str, css: str) -> str:
    return (
        '<!doctype html><html lang="en" dir="ltr"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">'
        '<meta name="color-scheme" content="dark"><meta name="theme-color" content="#06080c">'
        '<meta name="format-detection" content="telephone=no"><meta name="robots" content="noindex,nofollow">'
        f'<meta name="referrer" content="no-referrer"><title>{esc(title)}</title>{_favicon(logo_b64)}'
        f"<style>{_BASE_CSS}{css}</style></head>"
    )


_BACKDROP = ('<div class="backdrop" aria-hidden="true"><div class="glow glow--a"></div>'
             '<div class="glow glow--b"></div><div class="glow glow--c"></div></div>')


# ---------------------------------------------------------------------------
# Subscription page
# ---------------------------------------------------------------------------
def _metrics(info: dict) -> tuple[str, tuple[str, str]]:
    used = float(info.get("used_gb") or 0)
    total = info.get("total_gb")
    pct = max(0.0, min(100.0, float(info.get("pct") or 0)))
    no_expiry = info.get("no_expiry", True)
    days_left = int(info.get("days_left") or 0)
    days_total = max(1, int(info.get("days_total") or 1))
    online = int(info.get("online_count") or 0)
    max_dev = int(info.get("max_devices") or 0)
    expires_at = info.get("expires_at")

    # data
    used_s, used_dec = _num(used)
    if total:
        data_tone = "crit" if pct >= 95 else ("warn" if pct >= 80 else "")
        left_s, _ = _num(max(0.0, total - used))
        p = pct / 100
        p = max(p, 0.012) if p > 0 else 0
        data = (
            f'<div class="metric metric--wide" data-tone="{data_tone}">'
            f'<div class="metric-label">{icon("data")}<span>Data</span></div>'
            f'<div class="metric-value"><span class="num" data-count="{used:.{used_dec}f}" data-dec="{used_dec}">{used_s}</span>'
            f'<span class="unit">GB</span><span class="of">of {_trim(total)} GB</span></div>'
            f'<div class="meter" style="--p:{p:.4f}" role="progressbar" aria-label="Data used" '
            f'aria-valuemin="0" aria-valuemax="100" aria-valuenow="{pct:.0f}"><i></i></div>'
            f'<div class="metric-foot"><b>{left_s} GB</b> left &middot; {pct:.0f}% used</div></div>'
        )
    else:
        data = (
            '<div class="metric metric--wide">'
            f'<div class="metric-label">{icon("data")}<span>Data</span></div>'
            f'<div class="metric-value"><span class="num" data-count="{used:.{used_dec}f}" data-dec="{used_dec}">{used_s}</span>'
            '<span class="unit">GB</span><span class="of">used</span></div>'
            '<div class="meter meter--inf" aria-hidden="true"><i></i></div>'
            '<div class="metric-foot"><b>Unlimited</b> &middot; no data cap</div></div>'
        )

    # time
    if no_expiry:
        time_tone = ""
        time = (
            '<div class="metric">'
            f'<div class="metric-label">{icon("clock")}<span>Time</span></div>'
            '<div class="metric-value"><span class="num num--inf">∞</span></div>'
            '<div class="meter meter--inf" aria-hidden="true"><i></i></div>'
            '<div class="metric-foot"><b>No expiry</b></div></div>'
        )
    else:
        time_tone = "crit" if days_left <= 1 else ("warn" if days_left <= 3 else "")
        elapsed = min(1.0, max(0.0, 1 - days_left / days_total))
        elapsed = max(elapsed, 0.012) if elapsed > 0 else 0
        date_s = f"{expires_at:%b} {expires_at.day}, {expires_at:%Y}" if hasattr(expires_at, "strftime") else ""
        foot = f"Expires <b>{esc(date_s)}</b>" if date_s else f"of <b>{days_total}</b> days"
        time = (
            f'<div class="metric" data-tone="{time_tone}">'
            f'<div class="metric-label">{icon("clock")}<span>Time</span></div>'
            f'<div class="metric-value"><span class="num" data-count="{days_left}" data-dec="0">{days_left}</span>'
            f'<span class="unit">{"day" if days_left == 1 else "days"}</span><span class="of">left</span></div>'
            f'<div class="meter" style="--p:{elapsed:.4f}" role="progressbar" aria-label="Time elapsed" '
            f'aria-valuemin="0" aria-valuemax="{days_total}" aria-valuenow="{days_total - days_left}"><i></i></div>'
            f'<div class="metric-foot">{foot}</div></div>'
        )

    # devices
    if max_dev:
        shown = min(max_dev, 8)
        on = min(online, shown)
        slots = "".join('<i class="on"></i>' if k < on else "<i></i>" for k in range(shown))
        bar = (f'<div class="slots" aria-hidden="true">{slots}</div>' if max_dev <= 8 else
               f'<div class="meter" style="--p:{min(1, online / max_dev):.4f}" aria-hidden="true"><i></i></div>')
        of = f'<span class="of">of {max_dev}</span>'
    else:
        bar = '<div class="meter meter--inf" aria-hidden="true"><i></i></div>'
        of = '<span class="of">online</span>'
    foot = ("<b>Online now</b>" if online else "No active devices") if max_dev else "<b>No device limit</b>"
    devices = (
        '<div class="metric">'
        f'<div class="metric-label">{icon("devices")}<span>Devices</span></div>'
        f'<div class="metric-value"><span class="num">{online}</span>{of}</div>'
        f'{bar}<div class="metric-foot">{foot}</div></div>'
    )

    if total and pct >= 95:
        status = ("Almost out of data", "crit")
    elif not no_expiry and days_left <= 3:
        status = ("Expires soon", "warn" if days_left > 1 else "crit")
    elif total and pct >= 80:
        status = ("Running low", "warn")
    else:
        status = ("Active", "ok")
    return f'<div class="metrics">{data}{time}{devices}</div>', status


def render_subscription_page(*, title: str, configs: list, host: str, sub_path: str,
                             logo_b64: str, qr_endpoint: str, info: dict | None = None) -> str:
    name = title.split("·")[-1].strip() or title
    now = datetime.now(timezone.utc)

    # regions, in plan order
    groups: dict[str, list[tuple[int, dict]]] = {}
    for i, c in enumerate(configs):
        groups.setdefault(c.get("region") or "", []).append((i, c))
    regions = [r for r in groups if r]

    # pass card
    if info is not None:
        metrics, (status_text, status_tone) = _metrics(info)
        eyebrow = esc(info.get("plan_name") or "Subscription")
    else:
        metrics, (status_text, status_tone) = "", ("Live", "ok")
        eyebrow = "Instance"
    sub_bits = []
    if regions:
        sub_bits.append(f'<span><b>{len(regions)}</b> {"location" if len(regions) == 1 else "locations"}</span>')
    sub_bits.append(f'<span><b>{len(configs)}</b> {"config" if len(configs) == 1 else "configs"}</span>')
    pass_sub = '<span class="sep" aria-hidden="true"></span>'.join(sub_bits)

    # import panel
    base = f"https://{host}{sub_path}"
    formats = [
        ("v2ray", "v2ray", base, "", "Base64 list — works with v2rayNG, v2rayN, Hiddify, Streisand and NekoBox."),
        ("singbox", "sing-box", f"{base}?fmt=singbox&host={host}", "?fmt=singbox", "JSON outbounds for sing-box based clients."),
        ("clash", "Clash Meta", f"{base}?fmt=clash&host={host}", "?fmt=clash", "YAML profile for Clash Meta (mihomo) clients."),
    ]
    seg_btns = "".join(
        f'<button class="seg-btn" type="button" role="tab" data-action="format" data-fmt="{key}" '
        f'data-label="{esc(label)}" data-href="{esc(href)}" data-suffix="{esc(suffix)}" data-hint="{esc(hint)}" '
        f'aria-selected="{"true" if k == 0 else "false"}" tabindex="{0 if k == 0 else -1}">{esc(label)}</button>'
        for k, (key, label, href, suffix, hint) in enumerate(formats)
    )
    path_head, _, token = sub_path.rpartition("/")
    link_display = (
        f'<span class="lk-host"><span class="dim">https://</span>{esc(_middle(host, 10, 15))}</span>'
        f'<span class="lk-ell dim">…</span>'
        f'<span class="dim">{esc(path_head)}/</span>{esc(_middle(token, 6, 4))}'
        f'<span class="acc" id="link-acc"></span>'
    )

    # config groups
    filters = ""
    if len(regions) > 1:
        chips = [f'<button class="chip" type="button" data-action="filter" data-region="all" aria-pressed="true">'
                 f'All<span class="n">{len(configs)}</span></button>']
        chips += [
            f'<button class="chip" type="button" data-action="filter" data-region="r{k}" aria-pressed="false">'
            f'{esc(r)}<span class="n">{len(groups[r])}</span></button>'
            for k, r in enumerate(regions)
        ]
        filters = f'<div class="filters" role="group" aria-label="Filter by location">{"".join(chips)}</div>'

    group_html = []
    d = 0
    for g, (region, items) in enumerate(groups.items()):
        rows = []
        for i, c in items:
            pname, variant, mono, tone = _PROTOCOLS.get(c["protocol"], (c["protocol"], "", c["protocol"][:1].upper(), "vless"))
            parts = _transport(c["share_url"])
            meta = "".join(f"<span>{esc(p)}</span>" for p in parts)
            label = f"{pname} {variant}".strip()
            variant_html = f'<span class="v">{esc(variant)}</span>' if variant else ""
            sheet_title = f"{pname} · {variant}" if variant else pname
            sheet_sub = " · ".join([region, *parts] if region else parts)
            rows.append(
                f'<li class="cfg rise" style="--d:{d}" data-i="{i}" data-url="{esc(c["share_url"])}" '
                f'data-title="{esc(sheet_title)}" data-sub="{esc(sheet_sub)}">'
                '<div class="cfg-row">'
                f'<button class="cfg-main" type="button" data-action="toggle" aria-expanded="false" aria-controls="cfg-d{i}">'
                f'<span class="badge tone-{tone}" aria-hidden="true">{mono}</span>'
                f'<span class="cfg-text"><span class="cfg-title">{esc(pname)}{variant_html}</span>'
                f'<span class="cfg-meta">{meta}</span></span>'
                f'{icon("chevron", "ic cfg-chev")}</button>'
                '<div class="cfg-actions">'
                f'<button class="icon-btn" type="button" data-action="qr" aria-label="Show QR code for {esc(label)}">{icon("qr")}</button>'
                f'<button class="icon-btn" type="button" data-action="copy" aria-label="Copy {esc(label)} config">'
                f'<span class="swap">{icon("copy")}{icon("check")}</span></button>'
                '</div></div>'
                f'<div class="cfg-detail" id="cfg-d{i}"><div class="cfg-detail-in"><code class="code">{esc(c["share_url"])}</code></div></div>'
                '</li>'
            )
            d += 1
        head = (f'<div class="group-head">{icon("globe")}<span>{esc(region)}</span><span class="n">{len(items)}</span></div>'
                if region else "")
        key = f"r{regions.index(region)}" if region else "all"
        group_html.append(f'<section class="group" data-region="{key}">{head}<ul class="cfg-list">{"".join(rows)}</ul></section>')

    body = f"""<body data-qr="{esc(qr_endpoint)}">
{_BACKDROP}
<main class="shell">
  <header class="topbar reveal" style="--i:0">
    <div class="brand"><img src="data:image/png;base64,{logo_b64}" alt="" width="28" height="28"><span>Voidz</span></div>
    <div class="sync" data-tone="ok"><span class="dot" aria-hidden="true"></span>Updated <time datetime="{now.isoformat()}" data-ts>{now:%H:%M} UTC</time></div>
  </header>

  <section class="pass reveal" style="--i:1" aria-label="Subscription overview">
    <div class="pass-head">
      <div class="pass-id">
        <div class="eyebrow">{eyebrow}</div>
        <h1 class="pass-name">{esc(name)}</h1>
        <div class="pass-sub">{pass_sub}</div>
      </div>
      <span class="status" data-tone="{status_tone}"><span class="dot" aria-hidden="true"></span>{esc(status_text)}</span>
    </div>
    {metrics}
  </section>

  <section class="panel reveal" style="--i:2" aria-labelledby="import-title">
    <div class="panel-head">
      <div>
        <h2 class="panel-title" id="import-title">Import</h2>
        <p class="panel-desc">One link keeps every location in sync.</p>
      </div>
    </div>
    <div class="seg" role="tablist" aria-label="Subscription format"><span class="seg-ind" aria-hidden="true"></span>{seg_btns}</div>
    <div class="linkbox">{icon("link")}<span class="link-text" title="{esc(base)}">{link_display}</span></div>
    <div class="actions">
      <button class="btn btn--primary" type="button" data-action="copy-sub">
        <span class="swap"><span>{icon("copy")}Copy link</span><span>{icon("check")}Copied</span></span>
      </button>
      <button class="btn btn--ghost" type="button" data-action="qr-sub">{icon("qr")}QR code</button>
    </div>
    <p class="hint">{icon("info")}<span id="format-hint">{esc(formats[0][4])}</span></p>
  </section>

  <section class="panel reveal" style="--i:3" aria-labelledby="configs-title">
    <div class="panel-head">
      <h2 class="panel-title" id="configs-title">Configs <span class="count">{len(configs)}</span></h2>
      <button class="btn btn--ghost btn--sm" type="button" data-action="copy-all">
        <span class="swap"><span>{icon("copy")}Copy all</span><span>{icon("check")}Copied</span></span>
      </button>
    </div>
    {filters}
    {"".join(group_html)}
  </section>

  <footer class="foot reveal" style="--i:4">
    <span class="foot-note">{icon("shield")}Keep this link private &mdash; anyone with it can use this plan.</span>
    <span>Powered by Voidz</span>
  </footer>
</main>

<div class="sheet" id="sheet" role="dialog" aria-modal="true" aria-labelledby="sheet-title" aria-hidden="true">
  <div class="sheet-scrim" data-action="close"></div>
  <div class="sheet-card">
    <div class="sheet-head">
      <div><h2 class="sheet-title" id="sheet-title">QR code</h2><p class="sheet-sub" id="sheet-sub"></p></div>
      <button class="icon-btn sheet-close" type="button" data-action="close" aria-label="Close">{icon("close")}</button>
    </div>
    <div class="qr-frame" id="qr-slot"></div>
    <div class="sheet-actions">
      <button class="btn btn--ghost" type="button" data-action="sheet-copy">
        <span class="swap"><span>{icon("copy")}Copy link</span><span>{icon("check")}Copied</span></span>
      </button>
    </div>
  </div>
</div>

<div class="toast" id="toast" role="status" aria-live="polite" data-state="ok">{icon("check-circle", "ic t-ok")}{icon("alert", "ic t-err")}<span id="toast-msg"></span></div>
<script>{_SUB_JS}</script>
</body></html>"""
    return _head(title, logo_b64, _SUB_CSS) + body


# ---------------------------------------------------------------------------
# Notice page
# ---------------------------------------------------------------------------
_STATUS_LOOK = {
    200: ("ok", "check-circle", "All good"),
    400: ("warn", "alert", "Bad request"),
    403: ("warn", "lock", "Unavailable"),
    404: ("muted", "unlink", "Not found"),
    502: ("warn", "cloud-off", "Upstream error"),
    503: ("warn", "cloud-off", "Temporarily unavailable"),
}


def render_notice(title: str, body_html: str, status: int, logo_b64: str,
                  icon_name: str | None = None, tone: str | None = None) -> str:
    """``body_html`` is trusted markup written in gateway.py (may contain
    <b>/<code>); anything user-derived must be escaped by the caller."""
    look_tone, look_icon, label = _STATUS_LOOK.get(status, ("muted", "info", "Notice"))
    label = {"clock": "Expired", "data": "Limit reached"}.get(icon_name or "", label)
    tone = tone or look_tone
    code = f"{status} · {label}" if status != 200 else label
    return _head(f"{title} · Voidz", logo_b64, _NOTICE_CSS) + f"""<body>
{_BACKDROP}
<main class="notice">
  <section class="notice-card reveal" data-tone="{tone}">
    <div class="notice-icon">{icon(icon_name or look_icon)}</div>
    <div class="eyebrow">{esc(code)}</div>
    <h1>{esc(title)}</h1>
    <p>{body_html}</p>
    <div class="notice-brand"><img src="data:image/png;base64,{logo_b64}" alt="" width="18" height="18">Voidz</div>
  </section>
</main>
</body></html>"""
