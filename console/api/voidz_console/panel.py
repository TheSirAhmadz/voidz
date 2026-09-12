"""Self-contained single-file panel (no external JS/CSS — platform-proxy-proof).

Served at /panel and as the SPA fallback for browser routes. Everything
(login, dashboard, wizard, instance pages, admin) is one HTML document with
inline CSS + JS talking to the existing JSON API.
"""
from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

router = APIRouter(include_in_schema=False)

PAGE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="color-scheme" content="dark">
<title>Voidz Console</title>
<meta name="theme-color" content="#05070a">
<link rel="icon" type="image/png" href="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAACAAAAAgCAYAAABzenr0AAAG6ElEQVR42u1XbVBU5xU+7713P1l2+RCXZVWyiBFQwEBEQPGCxQwComjvIlSN1QoxDiO0jZaayZVYGkOaMNLKFDWdoaVMXMb6MWjTxrpAM4KWppXxqzUuyjcoILCwC9x7T38AHUQl0TZpfvT8u3Pve89znuc9531egG9YkP95DovFQn8VWRGRmvED/4Rsxfbtb7hOouT5L1jwDBWzVisz+bAiI8N96ksKAIDnecro8BA7laqM8vP1O2gKMD+fSBxnoXmef24gHMfRAIA1cXFCS689dNuxisIBSitDRDJdCkIIAPhHaNNy8u/96nTDhbwPziyfQh8N44u+VEyApgAAIrJ57dsNrfy+31c7Qvb/NAEAgHuizONoARgNuyR2PWZk8VLa7oLyPUeqAp9lk04yRggFiVtytiTn/fyfq4vKkCStPwwAwLIsMxNnNEXTIPMNOO1jCsQN2/bivqKT9ou3hwqvIWoQkeAMTEwmP1R0JDBl086PY7ksDF63FWFR6D1gWTfWamVgRknHWSDGV3MjlUaTOM8UNHy8snassW0U9xafsIZnlsomNudjICZpPXfx0vItmTn9EavW4YtLY+10wGJBuX5T+iNAp3TEo2gqK0UAIG2/OVyvnR9Y29xiU1342CI4HnYND7Q3x6p7r7yan08kluWnakg4i4W29fVRiEj/7fqtknutndrBwYdDTbYbKhIU8kCgVTbvD8peZhH9eUQmnxDp6SywPAMAMDvrR+laUyCCTO1M2/n9kewf/0wIj09tCtm82QUQCXAcDdP0/MPlq9s2v74PgyK+5VBrPUYhKgapPfsukrDlZ5SvmFu1aVnof+zEzbV3W5OnMzF9UhE4/amr5uWVHQqZXFB5zRlZmWh2RCVlYGDK1j3TB0zkDw8mhB4pL+FLyx8siVo95jHHNALuHoI878B9P0QdAIC7u59O6x9W5hn/bdx1444NEGnymAQT/wSOo2D9ikExYHGhLG4N7ezvkf7+WR1l7+mU5O6zchFR7huVHGCIii80xq251ni59v0XR50bbjf81bO5tQn7utpEWXIq7Z+aWtFESD/L/0LT12frd1e71YUmp4Dc6F0HFCWemGnqchYLzSNSYda/fOi2KxdBpnB6+Mwbe8mcJS7Ymvup3H12g9zX/5egN8a+z3Gq/QeLGxaEREpyVzcHmPwlX8up/hJEP2hokAEA7HqzLHBpyamRqLrGugBET0AkM3YEy4+PTwIAxsqqctXrOQgK1fDc4AjJtCGzBQBcJlvhtbxDm+JS0tHFU+8ArW6U/u5Ou+HPdasn/3XpRltqSXtv74LahuNgAPWEduRpp8a/x+SGT674zUpMKyca3R/dDr7T4llQOCbz8Bp5YfmaEa+N2dEALAMcR69I2FhjCnoJabVmmI6OQcj5QRIAwPzNuf4LisqOZ1y1Xcns7kgCAKAIeSQ59VhyQpChCa77qHbvtcqzdYPNtja0968bOP7hOy4aF4Y2p40+tN2SY8fnrwHUCCG9IyHdXe3RHW3NI6JOpxTt9tM638XXdQXFh3qC/N57oFPUV4T6RRydbTjHIdLSRI4nVk4AIAJRu/ZM49mV+3895hYYtXLipABI+I4WfOa1aL6XJSpWvSJo5y7sA46jde5eBzy8jKheGDQUuP8tKfTk2RrDOesR7eGjZsBxjSlCgLMgPYM5QAL8AQI7dii0JRXn5/fQse4qbfrF4qyPgLfIIdZLgrg4AaJid8PnN4shPNypvHpD7W3wzfReFLDd6eq6zGnQC5pZbgO6sLC1f1oWXjfFYNBgNoszuxOeZyA/X3A7X/uWo7Ao36f9vtMQvLQ0URp698Cpox0CACyEha5jfHbowJ2r1S4aF2Q8vFAc6EcURqnuhnrR0dWhgFEhD7raDkFmpgzi46WZEj8CgLVamZq4OGHV3c6yxqpPtg6fqwKdjwl0ej0Ieq8O0Hs5nMLYKEGhnWZA7Dl5YvVwk21M/MdNCkQU5QzNKIKCW0xvv7mosb/fCWazBAD45f3ZxK4sBfA8OwK7nJ1dSwbtduF2R2e3q0LRMtfvhZvdTbeu346JsQGACpQud2i1Sk+UakHFyCV1cKhyJCJy90P+jZJJNr8aO8myDKEooMOifqI2mlAzP2DILzldjP7tmbvJiGpAJM9iXJ7Yhiwiw1ksNGex0GC1MqzVynCINPA8BbGxEkoSEeMSj+Fs/ZDLmMjo1m6k9NHLDlcRMsxWV9NPbrH/Zkw4JybJXGFYlSIZL1y+B/Xntc9TPTzlMPoiBAAARFAojzlWxJAeNV0KkYkD8JzVPzuASrMIAAi/u3RJnGP4TNF1vwIQCVRXS1/7Ncq7oCDoa7pNfVPjP7i0/D8m41/tm/bOnXxCkAAAAABJRU5ErkJggg==">
<style>
:root{--bg:#05070a;--bg2:#0b0f16;--sur:rgba(20,26,37,.58);--sur2:rgba(30,38,52,.62);--bd:rgba(148,175,199,.14);--bd2:rgba(56,214,217,.38);
--tx:#eaf1f7;--dim:#9fb0c3;--fnt:#5c6b80;--acc:#35d7dc;--accs:#7ce8ea;--acc2:#8b7bff;--accd:#032025;--blu:#6f9bff;
--grn:#38e0a4;--amb:#f2bd4f;--red:#ff5c6e;--mono:ui-monospace,"SF Mono",Menlo,Consolas,monospace;
--sans:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,"Helvetica Neue",sans-serif;--r:16px;--rs:11px;
--blur:blur(20px) saturate(150%);--ease:cubic-bezier(.16,1,.3,1);
--shadow:0 1px 2px rgba(0,0,0,.5),0 20px 48px rgba(0,0,0,.45)}
@media(prefers-reduced-motion:reduce){*,*::before,*::after{animation-duration:.001ms!important;animation-iteration-count:1!important;transition-duration:.001ms!important}}
*{box-sizing:border-box}html,body{height:100%}
body{margin:0;background:var(--bg);color:var(--tx);font:14px/1.5 var(--sans);-webkit-font-smoothing:antialiased;overflow-x:hidden;position:relative}
body::before,body::after{content:"";position:fixed;z-index:0;pointer-events:none;border-radius:50%;filter:blur(90px);opacity:.5}
body::before{width:60vw;height:60vw;top:-20vw;left:-12vw;background:radial-gradient(circle at 30% 30%,rgba(56,214,217,.22),transparent 70%);animation:drA 26s ease-in-out infinite}
body::after{width:55vw;height:55vw;bottom:-25vw;right:-14vw;background:radial-gradient(circle at 60% 60%,rgba(139,123,255,.18),transparent 70%);animation:drB 32s ease-in-out infinite}
@keyframes drA{0%,100%{transform:translate(0,0) scale(1)}50%{transform:translate(5vw,4vw) scale(1.08)}}
@keyframes drB{0%,100%{transform:translate(0,0) scale(1)}50%{transform:translate(-4vw,-5vw) scale(1.1)}}
@keyframes rv{from{opacity:0;transform:translateY(14px)}to{opacity:1;transform:none}}
a{color:var(--accs);text-decoration:none}
#app{position:relative;z-index:1}
.shell{display:flex;flex-direction:column;min-height:100vh}
.bm{width:26px;height:26px;flex:none;filter:drop-shadow(0 0 6px rgba(56,214,217,.5));animation:glow 4.5s ease-in-out infinite}
.bm img{width:100%;height:100%;object-fit:contain;display:block}
@keyframes glow{0%,100%{filter:drop-shadow(0 0 6px rgba(56,214,217,.45))}50%{filter:drop-shadow(0 0 16px rgba(56,214,217,.85))}}
.ni{display:flex;align-items:center;gap:9px;color:var(--dim);font-weight:550;cursor:pointer;border:1px solid transparent;background:none;font-family:inherit;transition:color .16s,background .16s,transform .15s ease}
.ni svg{width:15px;height:15px}
.topbar{display:flex;align-items:center;gap:10px;position:sticky;top:0;z-index:30;background:rgba(8,10,15,.78);backdrop-filter:var(--blur);-webkit-backdrop-filter:var(--blur);border-bottom:1px solid var(--bd);padding:12px 16px}
.main{min-width:0}.ct{padding:22px 18px 104px;max-width:1100px;margin:0 auto;width:100%}
.sndb{display:inline-flex;align-items:center;justify-content:center;width:28px;height:28px;border-radius:8px;border:1px solid transparent;background:none;color:var(--fnt);cursor:pointer}
.sndb:hover{color:var(--accs);background:rgba(56,214,217,.1);border-color:var(--bd2)}
.sndb svg{width:15px;height:15px}
.sndb.off{opacity:.55}
.bnav{display:flex;justify-content:center;position:fixed;bottom:0;left:0;right:0;z-index:30;background:rgba(8,10,15,.86);backdrop-filter:var(--blur);-webkit-backdrop-filter:var(--blur);border-top:1px solid var(--bd);padding:8px 10px calc(8px + env(safe-area-inset-bottom));box-shadow:0 -10px 30px rgba(0,0,0,.35)}
.bnav-in{display:flex;gap:6px;width:100%;max-width:460px}
.bnav .ni{flex:1;flex-direction:column;gap:4px;font-size:10.5px;align-items:center;padding:7px 4px;border-radius:14px}
.bnav .ni svg{width:22px;height:22px;transition:transform .18s ease}
.bnav .ni:hover{color:var(--dim);background:rgba(255,255,255,.04)}
.bnav .ni.act{color:var(--accs);background:rgba(56,214,217,.12);box-shadow:0 0 20px -8px rgba(56,214,217,.65);transform:translateY(-2px)}
.bnav .ni.act svg{filter:drop-shadow(0 0 6px rgba(56,214,217,.6))}
@media(max-width:640px){.ct{padding:18px 14px 100px}}
.btn{display:inline-flex;align-items:center;justify-content:center;gap:7px;padding:9px 14px;border-radius:var(--rs);border:1px solid var(--bd);background:var(--sur2);color:var(--tx);font:600 13px var(--sans);cursor:pointer;white-space:nowrap;transition:background .15s,border-color .15s,transform .08s,box-shadow .2s}
.btn:hover{background:rgba(255,255,255,.07);border-color:var(--bd2);transform:translateY(-1px)}.btn:disabled{opacity:.4;cursor:not-allowed;transform:none}
.btn.pri{background:linear-gradient(135deg,var(--acc),var(--acc2));border-color:transparent;color:#04141a;font-weight:700;box-shadow:0 6px 20px -6px rgba(56,214,217,.55)}
.btn.pri:hover{filter:brightness(1.08);box-shadow:0 8px 26px -6px rgba(56,214,217,.75)}
.btn.dng{color:var(--red);border-color:rgba(255,92,110,.35)}.btn.dng:hover{background:rgba(255,92,110,.1);border-color:rgba(255,92,110,.6)}
.btn.sm{padding:6px 11px;font-size:12px}
.inp{width:100%;padding:10px 12px;background:rgba(255,255,255,.03);color:var(--tx);border:1px solid var(--bd);border-radius:var(--rs);font:400 13.5px var(--sans);transition:border-color .15s,box-shadow .15s,background .15s}
.inp:focus{outline:none;border-color:var(--acc);background:rgba(56,214,217,.05);box-shadow:0 0 0 3px rgba(56,214,217,.16)}
.fld{margin-bottom:14px}.fld label{display:block;font-size:12px;font-weight:600;color:var(--dim);margin-bottom:5px}
.card{background:var(--sur);border:1px solid var(--bd);border-radius:var(--r);padding:18px;backdrop-filter:var(--blur);-webkit-backdrop-filter:var(--blur);box-shadow:var(--shadow);animation:rv .5s var(--ease) backwards}
.card h3{margin:0 0 6px;font-size:13.5px}
.sgs{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:24px}
@media(max-width:840px){.sgs{grid-template-columns:repeat(2,1fr)}}
.sg{background:var(--sur);border:1px solid var(--bd);border-radius:var(--r);padding:14px 16px;backdrop-filter:var(--blur);-webkit-backdrop-filter:var(--blur);transition:border-color .2s,transform .2s;animation:rv .5s var(--ease) backwards}
.sg:hover{border-color:var(--bd2);transform:translateY(-2px)}
.sgs .sg:nth-child(1){animation-delay:0ms}.sgs .sg:nth-child(2){animation-delay:60ms}.sgs .sg:nth-child(3){animation-delay:120ms}.sgs .sg:nth-child(4){animation-delay:180ms}
.sg .l{font-size:11px;text-transform:uppercase;letter-spacing:1px;color:var(--fnt)}
.sg .v{font:700 26px var(--mono);margin-top:3px;letter-spacing:-.4px}
.st{display:inline-flex;align-items:center;gap:6px;font-size:12px;font-weight:600}
.st .d{width:8px;height:8px;border-radius:50%;background:var(--fnt)}
.st.run .d{background:var(--grn);animation:pu 2.2s infinite}
.st.fail .d{background:var(--red)}.st.sto .d{background:var(--fnt)}.st.tr .d{background:var(--amb)}
@keyframes pu{0%{box-shadow:0 0 0 0 rgba(56,224,164,.5)}70%{box-shadow:0 0 0 8px rgba(56,224,164,0)}100%{box-shadow:0 0 0 0 rgba(56,224,164,0)}}
.ig{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:13px}
.ic{background:var(--sur);border:1px solid var(--bd);border-radius:var(--r);padding:16px;cursor:pointer;display:flex;flex-direction:column;gap:9px;transition:border-color .18s,transform .18s var(--ease),box-shadow .18s;backdrop-filter:var(--blur);-webkit-backdrop-filter:var(--blur);animation:rv .5s var(--ease) backwards}
.ic:nth-child(1){animation-delay:0ms}.ic:nth-child(2){animation-delay:45ms}.ic:nth-child(3){animation-delay:90ms}.ic:nth-child(4){animation-delay:135ms}.ic:nth-child(5){animation-delay:180ms}.ic:nth-child(n+6){animation-delay:220ms}
.ic:hover{border-color:var(--bd2);transform:translateY(-3px);box-shadow:0 14px 34px -14px rgba(56,214,217,.4)}
.ic .t{display:flex;align-items:center;justify-content:space-between;gap:8px}
.ic .nm{font-size:14.5px;font-weight:650}
.ic .ep{font-family:var(--mono);font-size:11px;color:var(--dim);background:rgba(0,0,0,.25);border:1px solid var(--bd);padding:6px 8px;border-radius:var(--rs);overflow:hidden;text-overflow:ellipsis;white-space:nowrap;max-width:100%}
.ic .mt{display:flex;gap:12px;color:var(--fnt);font-size:11.5px;flex-wrap:wrap}
.ph{display:flex;align-items:flex-start;justify-content:space-between;gap:12px;margin-bottom:22px;flex-wrap:wrap}
.ph h1{margin:0;font-size:21px;font-weight:750;letter-spacing:-.3px}.ph .sub{color:var(--dim);margin-top:4px;font-size:13px}
.ha{display:flex;gap:7px;flex-wrap:wrap}
.tabs{display:flex;gap:2px;border-bottom:1px solid var(--bd);margin-bottom:20px;overflow-x:auto;scrollbar-width:none}
.tabs::-webkit-scrollbar{display:none}
.tab{padding:9px 13px;font-size:12.5px;font-weight:600;color:var(--fnt);border:none;background:none;cursor:pointer;border-bottom:2px solid transparent;margin-bottom:-1px;white-space:nowrap;font-family:inherit;transition:color .15s,border-color .15s}
.tab:hover{color:var(--dim)}
.tab.act{color:var(--tx);border-bottom-color:var(--acc);text-shadow:0 0 18px rgba(56,214,217,.5)}
.tbl{width:100%;border-collapse:collapse;font-size:12.5px}
.tbl th{text-align:left;font-size:10.5px;text-transform:uppercase;letter-spacing:1px;color:var(--fnt);padding:8px 10px;border-bottom:1px solid var(--bd)}
.tbl td{padding:10px 10px;border-bottom:1px solid var(--bd)}
.tbl tr:last-child td{border-bottom:none}
.tbl tr:hover td{background:rgba(56,214,217,.035)}
.term{background:rgba(3,5,8,.75);border:1px solid var(--bd);border-radius:var(--r);font-family:var(--mono);font-size:11.5px;overflow:hidden;backdrop-filter:var(--blur);-webkit-backdrop-filter:var(--blur)}
.tb{display:flex;gap:7px;align-items:center;padding:8px 10px;border-bottom:1px solid var(--bd);background:rgba(255,255,255,.02);flex-wrap:wrap}
.tb .sp{flex:1}
.tbody{height:400px;overflow:auto;padding:10px 12px}
.ll{white-space:pre-wrap;word-break:break-all;animation:rv .25s var(--ease)}.ll .t{color:var(--fnt)}.ll .lv{font-weight:700}
.ll.info .lv{color:var(--blu)}.ll.warning .lv,.ll.warn .lv{color:var(--amb)}.ll.error .lv{color:var(--red)}.ll.ok .lv{color:var(--grn)}
.te{color:var(--fnt);padding:26px;text-align:center}
.empty{text-align:center;padding:56px 16px;color:var(--dim);border:1px dashed var(--bd2);border-radius:var(--r);background:rgba(255,255,255,.015)}
.empty b{display:block;color:var(--tx);margin-bottom:3px}
.kv{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:10px}
.kv .it{background:rgba(255,255,255,.025);border:1px solid var(--bd);border-radius:var(--rs);padding:10px 12px}
.kv .k{font-size:10.5px;text-transform:uppercase;letter-spacing:1px;color:var(--fnt)}
.kv .v{font-family:var(--mono);font-size:13.5px;margin-top:2px}
.optg{display:grid;grid-template-columns:1fr 1fr;gap:9px}
@media(max-width:640px){.optg{grid-template-columns:1fr}}
.opt{border:1px solid var(--bd);border-radius:var(--rs);padding:12px 14px;cursor:pointer;background:rgba(255,255,255,.02);transition:border-color .16s,background .16s,transform .12s}
.opt:hover{border-color:var(--acc2);transform:translateY(-1px)}
.opt.sel{border-color:var(--acc);background:rgba(56,214,217,.08);box-shadow:0 0 0 1px rgba(56,214,217,.25) inset}
.opt .t{font-weight:650;font-size:13px}.opt .d{font-size:11.5px;color:var(--fnt);margin-top:2px}
.mono{font-family:var(--mono);font-size:12px}
.mut{color:var(--dim)}.ftx{color:var(--fnt)}
.row{display:flex;align-items:center;gap:9px;flex-wrap:wrap}.grow{flex:1}
.chip{display:inline-flex;padding:2px 9px;border:1px solid var(--bd2);border-radius:999px;font-size:11px;color:var(--accs);font-family:var(--mono);background:rgba(56,214,217,.08)}
.tw{position:fixed;bottom:18px;right:18px;z-index:100;display:flex;flex-direction:column;gap:7px}
.to{background:var(--sur2);border:1px solid var(--bd2);border-left:3px solid var(--blu);border-radius:var(--rs);padding:10px 14px;min-width:220px;max-width:340px;font-size:12.5px;box-shadow:var(--shadow);backdrop-filter:var(--blur);-webkit-backdrop-filter:var(--blur);animation:toin .28s var(--ease)}
@keyframes toin{from{transform:translateY(10px) scale(.98);opacity:0}to{transform:none;opacity:1}}
.to.ok{border-left-color:var(--grn);box-shadow:var(--shadow),0 0 24px -10px rgba(56,224,164,.6)}.to.err{border-left-color:var(--red);box-shadow:var(--shadow),0 0 24px -10px rgba(255,92,110,.6)}
.sp1{width:16px;height:16px;border:2px solid var(--bd);border-top-color:var(--acc);border-radius:50%;animation:sp .7s linear infinite;display:inline-block;filter:drop-shadow(0 0 4px rgba(56,214,217,.6))}
@keyframes sp{to{transform:rotate(360deg)}}
.lw{min-height:100vh;display:flex;align-items:center;justify-content:center;padding:18px;position:relative;z-index:1}
.lc{width:380px;max-width:100%;text-align:center;animation:lcin .6s var(--ease)}
@keyframes lcin{from{opacity:0;transform:translateY(22px) scale(.97)}to{opacity:1;transform:none}}
.lc h2{margin:10px 0 0;font-size:23px;font-weight:750}
.lc .p{color:var(--dim);font-size:13px;margin:8px 0 22px}
.lc .bm{width:60px;height:60px;margin:0 auto}
.lc .card{padding:26px 24px;text-align:left;position:relative;overflow:hidden;background:linear-gradient(180deg,rgba(22,28,40,.7),rgba(12,15,22,.7))}
.lc .card::before{content:"";position:absolute;inset:-1px;padding:1px;border-radius:inherit;background:conic-gradient(from 0deg,rgba(56,214,217,.5),rgba(139,123,255,.4),transparent 40%,rgba(56,214,217,.5));-webkit-mask:linear-gradient(#000 0 0) content-box,linear-gradient(#000 0 0);-webkit-mask-composite:xor;mask-composite:exclude;animation:rot 6s linear infinite;opacity:.7;pointer-events:none}
@keyframes rot{to{transform:rotate(360deg)}}
.fn{color:var(--fnt);font-size:11px;margin-top:14px}
.copy{border:none;background:none;color:var(--fnt);cursor:pointer;font-family:var(--mono);font-size:11px;padding:2px 4px;transition:color .15s}
.copy:hover{color:var(--accs)}
.qr-ov{position:fixed;inset:0;background:rgba(0,0,0,.72);display:flex;align-items:center;justify-content:center;z-index:200}
.qr-c{background:var(--sur);border:1px solid var(--bd2);border-radius:14px;padding:20px;text-align:center;max-width:340px;backdrop-filter:var(--blur);-webkit-backdrop-filter:var(--blur)}
.qr-c .qrbox svg{width:240px;height:240px;display:block;margin:8px auto;background:#fff;border-radius:8px}
</style>
</head>
<body>
<div id="app"><div class="lw"><span class="sp1"></span></div></div>
<script>
(function(){"use strict";
// ───────────────────────────── helpers ─────────────────────────────
var CSRF="";
function $(s,el){return (el||document).querySelector(s)}
function esc(s){var d=document.createElement("div");d.textContent=s==null?"":String(s);return d.innerHTML}
var SNDKEY="voidz.sound";var sndOn=localStorage.getItem(SNDKEY)!=="off";var actx=null;
function actxGet(){if(!sndOn)return null;if(!actx){var AC=window.AudioContext||window.webkitAudioContext;if(!AC)return null;actx=new AC()}if(actx.state==="suspended")actx.resume();return actx}
function tone(freq,dur,type,gain,delay,glide){var c=actxGet();if(!c)return;var t0=c.currentTime+(delay||0);var o=c.createOscillator(),g=c.createGain();o.type=type||"sine";o.frequency.setValueAtTime(freq,t0);if(glide)o.frequency.exponentialRampToValueAtTime(Math.max(glide,1),t0+dur);g.gain.setValueAtTime(.0001,t0);g.gain.linearRampToValueAtTime(gain||.04,t0+.008);g.gain.exponentialRampToValueAtTime(.0001,t0+dur);o.connect(g);g.connect(c.destination);o.start(t0);o.stop(t0+dur+.03)}
var SND={click:function(){tone(720,.05,"sine",.035)},nav:function(){tone(460,.1,"triangle",.03,0,660)},toggle:function(){tone(600,.06,"square",.022)},
ok:function(){tone(520,.1,"sine",.05);tone(780,.18,"sine",.05,.09)},err:function(){tone(200,.24,"sawtooth",.045,0,85)},
setOn:function(v){sndOn=v;localStorage.setItem(SNDKEY,v?"on":"off");if(v)tone(660,.06,"sine",.04)},isOn:function(){return sndOn}};
function sndIcon(on){return on?'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M4 9v6h4l5 4V5L8 9H4Z"/><path d="M17 8.5a5 5 0 0 1 0 7"/><path d="M19.5 6a8.5 8.5 0 0 1 0 12"/></svg>':'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M4 9v6h4l5 4V5L8 9H4Z"/><path d="M17 9l5 6M22 9l-5 6"/></svg>'}
function wireSndBtn(id){var b=document.getElementById(id);if(!b)return;b.onclick=function(){var v=!SND.isOn();SND.setOn(v);b.classList.toggle("off",!v);b.innerHTML=sndIcon(v);b.title=v?"Mute sound effects":"Enable sound effects"}}
function toast(msg,kind,ms){var w=$(".tw");if(!w){w=document.createElement("div");w.className="tw";document.body.appendChild(w)}
var e=document.createElement("div");e.className="to "+(kind||"");e.textContent=msg;w.appendChild(e);setTimeout(function(){e.remove()},ms||3500);
if(kind==="ok")SND.ok();else if(kind==="err")SND.err()}
function fmtBytes(n){if(n==null)return"—";if(n<1024)return n+" B";if(n<1048576)return(n/1024).toFixed(1)+" KB";if(n<1073741824)return(n/1048576).toFixed(2)+" MB";return(n/1073741824).toFixed(2)+" GB"}
function fmtUp(s){if(s==null)return"—";var d=Math.floor(s/86400),h=Math.floor(s%86400/3600),m=Math.floor(s%3600/60);if(d>0)return d+"d "+h+"h";if(h>0)return h+"h "+m+"m";if(m>0)return m+"m "+s+"s";return s+"s"}
function ago(iso){if(!iso)return"—";var t=new Date(iso),df=(Date.now()-t.getTime())/1e3;if(df<60)return"just now";if(df<3600)return Math.floor(df/60)+"m ago";if(df<86400)return Math.floor(df/3600)+"h ago";return t.toLocaleDateString(undefined,{month:"short",day:"numeric"})}
function dur(ms){if(ms==null)return"—";if(ms<1e3)return ms+"ms";if(ms<6e4)return(ms/1e3).toFixed(1)+"s";return Math.floor(ms/6e4)+"m"}
var LBL={queued:"Queued",preparing:"Preparing",building:"Building",starting:"Starting",health_check:"Health check",running:"Running",failed:"Failed",stopping:"Stopping",stopped:"Stopped",deleted:"Deleted",online:"Running",offline:"Stopped",unknown:"—"};
var BUSY={queued:1,preparing:1,building:1,starting:1,health_check:1,stopping:1};
function stEl(s){var cls=s==="running"||s==="online"?"run":(s==="failed"?"fail":(s==="stopped"||s==="offline"||s==="deleted"?"sto":(s==="stopping"?"sto":"tr")));
var sp=document.createElement("span");sp.className="st "+cls;sp.innerHTML='<span class="d"></span>'+(LBL[s]||s);return sp}
function copyBtn(text){var b=document.createElement("button");b.className="copy";b.textContent="copy";
b.onclick=function(e){e.stopPropagation();if(navigator.clipboard){navigator.clipboard.writeText(text).then(function(){toast("Copied","ok",1200)})}else{toast("Copy not supported","err")}};return b}
// ───────────────────────────── api ─────────────────────────────
function api(method,path,body,retry){
  var h={"Content-Type":"application/json"};
  if(CSRF)h["X-Voidz-CSRF"]=CSRF;
  return fetch(path,{method:method,headers:h,credentials:"same-origin",body:body!==undefined?JSON.stringify(body):undefined})
  .then(function(r){
    // 429 = too fast; wait what the server asks (or 2s) and retry silently
    if(r.status===429&&(retry||0)<3){
      var wait=parseInt(r.headers.get("Retry-After")||"2",10)||2;
      return new Promise(function(res){setTimeout(res,wait*1e3)}).then(function(){return api(method,path,body,(retry||0)+1)});
    }
    return r.json().catch(function(){return{}}).then(function(d){
    if(!r.ok){
      if(r.status===401&&!(retry)&&!path.startsWith("/auth")){
        // confirm the session really died before bouncing the user
        return fetch("/auth/me",{credentials:"same-origin"}).then(function(m){return m.json()}).then(function(me){
          if(me.authenticated){CSRF=me.csrf_token;return api(method,path,body,3)}
          USER=null;render();throw new Error("please sign in again");
        });
      }
      throw new Error((d&&d.detail)||("HTTP "+r.status));
    }
    return d})})}

// ───────────────────────────── icons ─────────────────────────────
function ic(n){var p={dash:'<path d="M3 3h7v7H3zM14 3h7v7h-7zM3 14h7v7H3zM14 14h7v7h-7z"/>',
plus:'<path d="M12 5v14M5 12h14"/>',gear:'<path d="M12 3l8 4v5c0 5-3.5 8-8 9-4.5-1-8-4-8-9V7z"/>',
layers:'<path d="M12 3 2 8l10 5 10-5-10-5Z"/><path d="M2 13l10 5 10-5"/><path d="M2 18l10 5 10-5"/>',
gh:'<path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27s1.36.09 2 .27c1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.01 8.01 0 0 0 16 8c0-4.42-3.58-8-8-8Z" fill="currentColor" stroke="none"/>',
tg:'<path d="M21.9 4.6 18.9 19c-.2 1-.8 1.2-1.7.8l-4.6-3.4-2.2 2.1c-.3.3-.5.5-1 .5l.4-4.7L18.6 6c.4-.3-.1-.5-.6-.2L7.3 12.4l-4.3-1.4c-.9-.3-.9-.9.2-1.3L20.7 3.3c.8-.3 1.5.2 1.2 1.3Z" fill="currentColor" stroke="none"/>'};
return '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" style="width:15px;height:15px">'+p[n]+"</svg>"}
var MARK='<span class="bm"><img src="data:image/png;base64,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" alt="Voidz" draggable="false"></span>';
var MARKL='<span class="bm" style="width:60px;height:60px"><img src="data:image/png;base64,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" alt="Voidz" draggable="false"></span>';

// ───────────────────────────── shell/state ─────────────────────────────
var USER=null, cleanup=null, pollTimer=null;
function setCleanup(fn){if(cleanup)cleanup();cleanup=fn||null}
function stopPoll(){if(pollTimer){clearInterval(pollTimer);pollTimer=null}if(hiddenTimer){clearInterval(hiddenTimer);hiddenTimer=null}}
var hiddenTimer=null;
function every(ms,fn){return setInterval(function(){if(!document.hidden)fn()},ms)}
function shell(nav){
  stopPoll();setCleanup(null);
  var app=$("#app");
  app.innerHTML='<div class="shell">'+
    '<div class="topbar">'+MARK+'<b style="font-size:14px">Voidz</b>'+
    '<div style="margin-left:auto;display:flex;gap:6px;align-items:center">'+
    '<button class="sndb '+(SND.isOn()?"":"off")+'" id="sb2" title="'+(SND.isOn()?"Mute sound effects":"Enable sound effects")+'">'+sndIcon(SND.isOn())+'</button>'+
    '<button class="btn sm" id="lgm">Sign out</button></div></div>'+
    '<div class="ct" id="view"></div>'+
    '<nav class="bnav"><div class="bnav-in"><button class="ni '+(nav==="dash"?"act":"")+'" data-nav="dash">'+ic("dash")+'<span>Home</span></button>'+
    '<button class="ni '+(nav==="new"?"act":"")+'" data-nav="new">'+ic("plus")+'<span>Create</span></button>'+
    '<button class="ni '+(nav==="plans"?"act":"")+'" data-nav="plans">'+ic("layers")+'<span>Plans</span></button>'+
    (USER.is_admin?'<button class="ni '+(nav==="admin"?"act":"")+'" data-nav="admin">'+ic("gear")+'<span>Admin</span></button>':"")+
    '</div></nav></div>';
  var lgm=$("#lgm");if(lgm)lgm.onclick=logout;
  wireSndBtn("sb2");
  Array.prototype.forEach.call(document.querySelectorAll("[data-nav]"),function(b){
    b.onclick=function(){SND.nav();nav_(b.dataset.nav)}});
}
function nav_(name){stopPoll();setCleanup(null);
  if(name==="dash")viewDash();else if(name==="new")viewWizard();else if(name==="admin")viewAdmin();else if(name==="plans")viewPlans()}
function logout(){SND.click();api("POST","/auth/logout").then(function(){render()})}
// ───────────────────────────── login ─────────────────────────────
function viewLogin(){
  stopPoll();setCleanup(null);
  $("#app").innerHTML='<div class="lw"><div class="lc">'+
    '<div style="text-align:center">'+MARKL+'<h2>Voidz</h2>'+
    '<p class="p" style="text-align:center">Deploy and manage multi-protocol proxy instances.</p></div>'+
    '<div class="card">'+
    '<div class="fld"><label>Account name</label><input class="inp" id="u" placeholder="admin" autocomplete="username"></div>'+
    '<div class="fld"><label>Password</label><input class="inp" id="p" type="password" autocomplete="current-password"></div>'+
    '<button class="btn pri" id="go" style="width:100%">Sign in</button>'+
    '<p class="fn">Default account is <span class="mono">admin / admin</span> — change it in Admin → System.</p>'+
    '</div></div></div>';
  $("#go").onclick=function(){
    SND.click();
    var b=$("#go");b.disabled=true;
    api("POST","/auth/login-password",{name:$("#u").value.trim()||"admin",password:$("#p").value})
    .then(function(){render()}).catch(function(e){b.disabled=false;toast(e.message,"err")});
  };
  $("#p").addEventListener("keydown",function(e){if(e.key==="Enter")$("#go").click()});
}
// ───────────────────────────── dashboard ─────────────────────────────
function viewDash(){
  shell("dash");
  var v=$("#view");
  v.innerHTML='<div class="ph"><div><h1>Dashboard</h1><div class="sub">Your Voidz instances at a glance.</div></div>'+
    '<div class="ha"><button class="btn pri" data-go="new">+ Create Instance</button></div></div>'+
    '<div class="sgs" id="sgs"></div><h3 style="margin:0 0 10px;font-size:13.5px">Instances</h3><div id="il"></div>'+
    '<div class="card" style="margin-top:22px"><h3>Recent activity</h3><div id="ac" class="mut">—</div></div>';
  Array.prototype.forEach.call(v.querySelectorAll("[data-go]"),function(b){b.onclick=function(){nav_(b.dataset.go)}});
  var t=null;
  function load(){
    return Promise.all([api("GET","/api/instances"),api("GET","/api/activity")]).then(function(rs){
      var list=rs[0].instances, act=rs[1].activity;
      var run=0,sto=0,fail=0;list.forEach(function(i){if(i.status==="running")run++;else if(i.status==="failed")fail++;else sto++});
      $("#sgs").innerHTML=sg("Active instances",list.length)+sg("Running",run,"var(--grn)")+sg("Stopped",sto)+sg("Failed",fail,fail?"var(--red)":null);
      var il=$("#il");
      if(!list.length){il.innerHTML='<div class="empty"><b>No instances yet</b>Deploy your first one in under a minute.<div style="margin-top:14px"><button class="btn pri" data-go="new">Create your first instance</button></div></div>'}
      else{il.innerHTML='<div class="ig">'+list.map(card).join("")+"</div>";
        Array.prototype.forEach.call(il.querySelectorAll("[data-id]"),function(c){c.onclick=function(){viewInst(c.dataset.id)}})}
      $("#ac").innerHTML=act.length?act.slice(0,8).map(function(a){return '<div style="display:flex;gap:10px;padding:8px 0;border-bottom:1px solid var(--bd)"><span class="ftx mono" style="width:64px;flex:none">'+ago(a.ts)+'</span><span class="mut">'+esc(a.message)+"</span></div>"}).join(""):"Nothing yet.";
      var go=v.querySelector(".empty [data-go]");if(go)go.onclick=function(){nav_("new")};
      return list;
    });
  }
  function sg(l,v,c){return '<div class="sg"><div class="l">'+l+'</div><div class="v" style="'+(c?"color:"+c:"")+'">'+v+"</div></div>"}
  function card(i){
    var ep=i.endpoint_url||(i.domain&&i.domain.indexOf("-")>0&&i.domain.length>30?null:null);
    return '<div class="ic" data-id="'+i.id+'"><div class="t"><span class="nm">'+esc(i.name)+"</span>"+stEl(i.status).outerHTML+"</div>"+
      (i.endpoint_url?'<div class="ep">'+esc(i.endpoint_url)+"</div>":'<div class="ep ftx">no endpoint yet</div>')+
      '<div class="mt"><span>'+esc(i.region)+"</span><span>"+i.deployments_count+' deploys</span><span>created '+ago(i.created_at)+"</span></div></div>";
  }
  load().then(function(list){
    pollTimer=every(6000,function(){
      if(list.some(function(i){return BUSY[i.status]}))load();
    });
  });
}
// ───────────────────────────── wizard ─────────────────────────────
var PROTOS=[["vless-ws","VLESS over WebSocket","Widest client support (v2rayNG, NekoBox). Recommended."],
["trojan-ws","Trojan over WebSocket","TLS-like handshake, good under strict DPI."],
["shadowsocks","Shadowsocks AEAD","Lightweight AEAD (chacha20 / aes-gcm) over WebSocket."],
["xhttp-packet-up","VLESS xHTTP (packet-up)","HTTP-native transport, resists connection shaping."]];
function viewWizard(){
  shell("new");
  var m={name:"",region:"local",protocol:"vless-ws",protocols:["vless-ws"],cpu:0.5,mem:256},step=0;
  var v=$("#view");
  v.innerHTML='<div class="ph"><div><h1>Create Instance</h1><div class="sub">Name it, pick a protocol, deploy. No servers, no YAML.</div></div></div>'+
    '<div class="row" id="stb" style="gap:4px;margin-bottom:20px"></div><div class="card" id="sb"></div>'+
    '<div class="row" style="margin-top:18px"><button class="btn" id="bk">Back</button><div class="grow"></div><button class="btn pri" id="nx">Continue</button></div>';
  var steps=["Name","Region","Config","Networking","Review","Deploy"];
  function bar(){ $("#stb").innerHTML=steps.map(function(s,i){return '<div class="grow" style="height:3px;border-radius:2px;background:'+(i<step?"var(--acc)":i===step?"var(--blu)":"var(--bd)")+'"></div>'}).join("")}
  function show(){
    bar();var b=$("#sb");
    $("#bk").disabled=step===0;$("#nx").textContent=step===4?"Deploy":step===5?"Go to instance":"Continue";
    $("#nx").classList.toggle("pri",step!==5);
    if(step===0){b.innerHTML='<h3 style="margin:0 0 10px">Step 1 — Name</h3><div class="fld"><label>Instance name</label><input class="inp" id="f-n" maxlength="60" placeholder="e.g. Production" value="'+esc(m.name)+'"></div><div class="ftx" style="font-size:12px">Letters, numbers, dashes. Up to 25 instances per account.</div>';
      $("#f-n").oninput=function(e){m.name=e.target.value}}
    else if(step===1){b.innerHTML='<h3 style="margin:0 0 10px">Step 2 — Region</h3><div class="optg" id="rg"><div class="opt sel" data-id="local"><div class="t">Local node</div><div class="d">Default worker on this platform</div></div></div>';
      Array.prototype.forEach.call(b.querySelectorAll(".opt"),function(o){o.onclick=function(){SND.toggle();m.region=o.dataset.id;Array.prototype.forEach.call(b.querySelectorAll(".opt"),function(x){x.classList.toggle("sel",x===o)})}})}
    else if(step===2){b.innerHTML='<h3 style="margin:0 0 10px">Step 3 — Protocols & resources</h3><div class="fld"><div class="optg">'+PROTOS.map(function(p){return '<div class="opt '+(m.protocols.indexOf(p[0])>=0?"sel":"")+'" data-id="'+p[0]+'"><div class="t">'+p[1]+'</div><div class="d">'+p[2]+"</div></div>"}).join("")+'</div><p class="ftx" style="font-size:11.5px;margin-top:7px">Pick one or more \u2014 each selected protocol gets its own config in the subscription.</p></div><div class="row"><div class="fld" style="width:160px;margin:0"><label>CPU (cores)</label><select class="inp" id="f-c">'+[0.25,0.5,1,2,4].map(function(x){return '<option value="'+x+'" '+(m.cpu===x?"selected":"")+">"+x+"</option>"}).join("")+'</select></div><div class="fld" style="width:160px;margin:0"><label>Memory</label><select class="inp" id="f-m">'+[128,256,512,1024,2048].map(function(x){return '<option value="'+x+'" '+(m.mem===x?"selected":"")+">"+x+" MB</option>"}).join("")+"</select></div></div>";
      Array.prototype.forEach.call(b.querySelectorAll(".opt"),function(o){o.onclick=function(){
        SND.toggle();
        var i=m.protocols.indexOf(o.dataset.id);
        if(i>=0){if(m.protocols.length>1){m.protocols.splice(i,1);o.classList.remove("sel")}}
        else{m.protocols.push(o.dataset.id);o.classList.add("sel")}}});
      $("#f-c").onchange=function(e){m.cpu=parseFloat(e.target.value)};$("#f-m").onchange=function(e){m.mem=parseInt(e.target.value,10)}}
    else if(step===3){b.innerHTML='<h3 style="margin:0 0 10px">Step 4 — Networking</h3><div class="card" style="background:var(--bg2)"><div class="row"><span class="chip">https</span><span class="mono">&lt;console-host&gt;/i/&lt;private-token&gt;</span></div><p class="ftx" style="margin:9px 0 0;font-size:12.5px">WebSocket, xHTTP and all Voidz protocols work through this endpoint with automatic TLS. Ready on deploy.</p></div>'}
    else if(step===4){b.innerHTML='<h3 style="margin:0 0 10px">Step 5 — Review</h3><table class="tbl"><tr><td style="color:var(--fnt);width:40%">Name</td><td class="mono">'+(esc(m.name)||"—")+"</td></tr><tr><td style='color:var(--fnt)'>Region</td><td class='mono'>"+esc(m.region)+"</td></tr><tr><td style='color:var(--fnt)'>Protocols</td><td class='mono'>"+esc(m.protocols.join(", "))+"</td></tr><tr><td style='color:var(--fnt)'>CPU / Memory</td><td class='mono'>"+m.cpu+" core / "+m.mem+" MB</td></tr></table>"}
    else if(step===5){b.innerHTML='<h3 style="margin:0 0 10px">Step 6 — Deploy</h3><div class="kv"><div class="it"><div class="k">Status</div><div class="v" id="ds">Deploying…</div></div><div class="it"><div class="k">Deployment</div><div class="v" id="di">—</div></div></div><div class="term" style="margin-top:14px"><div class="tbody" id="dl" style="height:220px"><div class="ll"><span class="t">»</span> queued</div></div></div>'}
  }
  $("#bk").onclick=function(){SND.click();if(step>0&&step!==5){step--;show()}};
  $("#nx").onclick=function(){
    SND.click();
    if(step===0){if(m.name.trim().length<2){toast("Give the instance a name (2+ chars)","err");return}step=1}
    else if(step===4){step=5;show();$("#nx").disabled=true;
      api("POST","/api/instances",{name:m.name,region:m.region,config:{protocol:m.protocols[0],protocols:m.protocols,cpu_limit:m.cpu,memory_mb:m.mem}})
      .then(function(created){return api("POST","/api/instances/"+created.id+"/deploy").then(function(d){return{c:created,d:d}})})
      .then(function(r){
        $("#di").textContent=r.d.deployment_id.slice(0,8);var seen=0;
        pollTimer=every(2000,function(){
          if(document.hidden)return;
          Promise.all([api("GET","/api/instances/"+r.c.id+"/deployments/"+r.d.deployment_id+"/logs"),api("GET","/api/instances/"+r.c.id+"/deployments")])
          .then(function(rs){
            var logs=rs[0].logs;for(;seen<logs.length;seen++){var e=document.createElement("div");e.className="ll "+logs[seen].level;e.innerHTML='<span class="lv">'+logs[seen].level+"</span> "+esc(logs[seen].message);var dl=$("#dl");if(dl){dl.appendChild(e);dl.scrollTop=dl.scrollHeight}}
            var dep=(rs[1].deployments||[]).filter(function(d){return d.id===r.d.deployment_id})[0];
            if(dep){$("#ds").textContent=dep.status.replace("_"," ");
              if(dep.status==="running"){$("#ds").style.color="var(--grn)";stopPoll();$("#nx").disabled=false;$("#nx").textContent="Go to instance";$("#nx").onclick=function(){viewInst(r.c.id)};toast("Instance is running","ok")}
              else if(dep.status==="failed"){$("#ds").style.color="var(--red)";stopPoll();$("#nx").disabled=false;$("#nx").textContent="Retry";$("#nx").onclick=function(){viewInst(r.c.id)};toast("Deployment failed: "+(dep.error||"unknown"),"err",8000)}}
          }).catch(function(){});
        },1500);
      }).catch(function(e){toast(e.message,"err",6000);step=4;show();$("#nx").disabled=false});
      return}
    else if(step<5)step+=1;
    show();
  };
  show();
}
// ───────────────────────────── instance page ─────────────────────────────
var TABS=["config","overview","logs","networking","deployments","activity","settings"];
function viewInst(id){
  shell("dash");
  var v=$("#view");v.innerHTML='<div class="lw"><span class="sp1"></span></div>';
  var inst=null,tab="overview",logPaused=false,logBuf=[];
  function head(){
    var pd=(inst.domains||[]).filter(function(d){return d.kind==="path"})[0];
    v.innerHTML='<div class="ph"><div><div class="row" style="gap:11px"><h1>'+esc(inst.name)+"</h1>"+stEl(inst.status).outerHTML+'</div><div class="sub" id="ep"></div></div>'+
      '<div class="ha"><button class="btn" id="a-r">Restart</button><button class="btn" id="a-s">Stop</button><button class="btn" id="a-rd">Redeploy</button><button class="btn dng" id="a-d">Delete</button></div></div>'+
      '<div class="tabs">'+TABS.map(function(t){return '<button class="tab '+(t===tab?"act":"")+'" data-t="'+t+'">'+t[0].toUpperCase()+t.slice(1)+"</button>"}).join("")+'</div><div id="tb"></div>';
    var epEl=$("#ep");
    if(pd){var url=location.origin+"/i/"+pd.domain;
      epEl.innerHTML='<span class="mono">'+esc(url)+"</span> ";epEl.appendChild(copyBtn(url));var a=document.createElement("a");a.href=url;a.target="_blank";a.rel="noopener";a.textContent="open ↗";epEl.appendChild(a)}
    else epEl.textContent="no endpoint yet — deploy the instance";
    var busy=BUSY[inst.status];["a-r","a-s","a-rd","a-d"].forEach(function(x){var b=$("#"+x);if(b)b.disabled=!!busy});
    $("#a-r").onclick=function(){act("restart")};$("#a-s").onclick=function(){act("stop")};$("#a-rd").onclick=function(){act("redeploy")};
    $("#a-d").onclick=function(){if(confirm('Delete "'+inst.name+'"? This is permanent.')){api("DELETE","/api/instances/"+id).then(nav_("dash")).catch(function(e){toast(e.message,"err")})}};
    Array.prototype.forEach.call(v.querySelectorAll(".tab"),function(b){b.onclick=function(){tab=b.dataset.t;head();draw()}});
  }
  function act(k){api("POST","/api/instances/"+id+"/"+k).then(function(){toast({restart:"Restarting…",stop:"Stopping…",redeploy:"Redeploying…"}[k],"ok");refresh()}).catch(function(e){toast(e.message,"err")})}
  function refresh(){return api("GET","/api/instances/"+id).then(function(d){inst=d;head();draw()})}
  function draw(){
    var b=$("#tb");if(!b)return;
    if(tab==="config"){
      b.innerHTML='<div class="card"><div class="row" style="justify-content:space-between"><h3>Subscription</h3><button class="btn sm" id="cf-r">Refresh</button></div>'+
        '<p class="mut" style="font-size:12.5px;margin:6px 0 10px">One URL, <b>all 4 protocols</b> (VLESS, Trojan, Shadowsocks, xHTTP). Add it under Subscriptions in your client — it auto-updates.</p>'+
        '<div class="row"><div class="mono grow" id="suburl" style="background:var(--bg2);border:1px solid var(--bd);border-radius:7px;padding:8px 10px;word-break:break-all"></div><button class="btn sm pri" id="subc">Copy</button><a class="btn sm" id="subo" target="_blank" rel="noopener">Open</a></div>'+
        '<div class="row" style="margin-top:9px;gap:6px"><span class="ftx" style="font-size:11.5px">Formats:</span>'+
        '<button class="btn sm" id="sub-v2">v2ray/Clash Verge</button><button class="btn sm" id="sub-sb">sing-box</button><button class="btn sm" id="sub-cl">Clash Meta</button></div>'+
        '<div class="card" style="margin-top:14px"><div class="row" style="justify-content:space-between"><h3>Individual configs</h3><button class="btn sm" id="cf-r">Refresh</button></div><div id="cf-b" class="mut">Loading…</div></div>';
      function loadCfg(){
        // tell the server the public host we're browsing on (edge hides it)
        api("POST","/api/instances/"+id+"/announce-host",{host:location.host}).catch(function(){});
        $("#cf-b").innerHTML='<span class="mut">Loading…</span>';
        api("GET","/api/instances/"+id+"/config").then(function(d){
          var subUrl=location.origin+"/i/"+(d.endpoint_path||"").replace("/i/","")+"/sub";
          if(d.endpoint_path){$("#suburl").textContent=subUrl;
            $("#subc").onclick=function(){navigator.clipboard&&navigator.clipboard.writeText(subUrl).then(function(){toast("Subscription URL copied","ok",2500)})};
            $("#subo").href=subUrl+"?host="+location.host;
            var v2=location.origin+"/i/"+d.endpoint_path.split("/i/")[1]+"/sub?host="+location.host;
            $("#sub-v2").onclick=function(){navigator.clipboard&&navigator.clipboard.writeText(v2).then(function(){toast("v2ray sub URL copied","ok",2500)})};
            $("#sub-sb").onclick=function(){navigator.clipboard&&navigator.clipboard.writeText(v2+"&fmt=singbox").then(function(){toast("sing-box sub URL copied","ok",2500)})};
            $("#sub-cl").onclick=function(){navigator.clipboard&&navigator.clipboard.writeText(v2+"&fmt=clash").then(function(){toast("Clash sub URL copied","ok",2500)})};}
          if(!d.configs||!d.configs.length){
            $("#cf-b").innerHTML='<span class="ftx">'+esc(d.error||"No configs yet — if the instance shows Running, press Redeploy once (instances created before this fix get their links on redeploy).")+"</span>";
            return;
          }
          var pubHost=location.host;
          $("#cf-b").innerHTML=d.configs.map(function(c,idx){
            var url=c.share_url;
            var m=c.share_url.match(/^(vless|trojan):\/\/([^@]+)@([^\/?#]+)([^#]*)/);
            if(m){
              var proto=m[1],cred=m[2],inner=m[3],rest=m[4]||"";
              var innerHost=inner.split(":")[0];
              if(innerHost==="127.0.0.1"||innerHost==="localhost"||innerHost==="0.0.0.0"){
                url=proto+"://"+cred+"@"+pubHost+rest;
              }
            }
            return '<div style="margin-top:12px"><div class="row" style="justify-content:space-between"><b style="font-size:12.5px">'+esc(c.label)+'</b><span class="chip">'+esc(c.protocol)+"</span></div>"+
              '<div class="mono" style="margin-top:5px;background:var(--bg2);border:1px solid var(--bd);border-radius:7px;padding:8px 10px;word-break:break-all;max-height:90px;overflow:auto">'+esc(url)+"</div>"+
              '<div class="row" style="margin-top:6px"><button class="btn sm pri" data-copy="'+esc(url)+'">Copy</button><button class="btn sm" data-qr="'+esc(url)+'">QR</button></div></div>';
          }).join("");
          Array.prototype.forEach.call($("#cf-b").querySelectorAll("[data-copy]"),function(btn){
            btn.onclick=function(){navigator.clipboard&&navigator.clipboard.writeText(btn.dataset.copy).then(function(){toast("Copied — v2rayNG: Import from clipboard","ok",4000)})}});
          Array.prototype.forEach.call($("#cf-b").querySelectorAll("[data-qr]"),function(btn){
            btn.onclick=function(){
              var ov=document.createElement("div");ov.className="qr-ov";
              ov.innerHTML='<div class="qr-c"><b style="font-size:13px">Scan with your client</b><div class="qrbox" style="margin:10px 0"><span class="sp1"></span></div><button class="btn sm" id="qrx">Close</button></div>';
              document.body.appendChild(ov);
              ov.onclick=function(e){if(e.target===ov)ov.remove()};
              $("#qrx",ov).onclick=function(){ov.remove()};
              api("POST","/api/instances/"+id+"/qr",{text:btn.dataset.qr}).then(function(svg){
                $(".qrbox",ov).innerHTML=svg}).catch(function(e){ov.remove();toast(e.message,"err")});
            }});
        }).catch(function(e){$("#cf-b").innerHTML='<span class="ftx">'+esc(e.message)+"</span>"});
      }
      $("#cf-r").onclick=loadCfg;loadCfg();
    }
    else if(tab==="overview"){
      b.innerHTML='<div class="kv" id="okv"></div><div class="card" style="margin-top:16px"><h3>Latest deployment</h3><div id="odp" class="mut">—</div></div>';
      Promise.all([api("GET","/api/instances/"+id+"/status"),api("GET","/api/instances/"+id+"/metrics")]).then(function(rs){
        var st=rs[0],mt=rs[1],ld=inst.latest_deployment;
        $("#okv").innerHTML=
          '<div class="it"><div class="k">Status</div><div class="v">'+(LBL[inst.status]||inst.status)+"</div></div>"+
          '<div class="it"><div class="k">Uptime</div><div class="v">'+fmtUp(st.core_health&&st.core_health.uptime)+"</div></div>"+
          '<div class="it"><div class="k">Connections</div><div class="v">'+(st.core_health?st.core_health.connections:"—")+"</div></div>"+
          '<div class="it"><div class="k">Version</div><div class="v">'+esc(st.core_health&&st.core_health.version||"—")+"</div></div>"+
          '<div class="it"><div class="k">Region</div><div class="v">'+esc(inst.region)+"</div></div>"+
          '<div class="it"><div class="k">Health</div><div class="v" style="color:'+(st.healthy?"var(--grn)":"var(--fnt)")+'">'+(st.healthy?"healthy":"n/a")+"</div></div>";
        $("#odp").innerHTML=ld?'<div class="row">'+stEl(ld.status).outerHTML+'<span class="chip">v'+ld.version+'</span><span class="ftx">started '+ago(ld.started_at)+" · "+dur(ld.duration_ms)+"</span></div>"+(ld.error?'<p style="color:var(--red);font-size:12px;margin:7px 0 0">'+esc(ld.error)+"</p>":""):"—";
      }).catch(function(){});
    }
    else if(tab==="logs"){
      b.innerHTML='<div class="term"><div class="tb"><button class="btn sm" id="lp">Pause</button><div class="sp"></div><button class="btn sm" id="lc">Copy</button><button class="btn sm" id="ld">Download</button></div><div class="tbody" id="lb"><div class="te">Waiting for logs…</div></div></div>';
      $("#lp").onclick=function(e){logPaused=!logPaused;e.target.textContent=logPaused?"Resume":"Pause";e.target.classList.toggle("pri",logPaused)};
      $("#lc").onclick=function(){navigator.clipboard&&navigator.clipboard.writeText(logBuf.map(function(l){return l.level+" "+l.message}).join("\n")).then(function(){toast("Copied","ok",1200)})};
      $("#ld").onclick=function(){var blob=new Blob([logBuf.map(function(l){return new Date(l.ts*1e3).toISOString()+" "+l.level+" "+l.message}).join("\n")],{type:"text/plain"});var a=document.createElement("a");a.href=URL.createObjectURL(blob);a.download=inst.slug+"-logs.txt";a.click()};
      pollLogs();
    }
    else if(tab==="networking"){
      var list=(inst.domains||[]);
      b.innerHTML='<div class="card"><div class="row" style="justify-content:space-between"><h3>Endpoints</h3><button class="btn" id="rg">Regenerate</button></div><div id="dl2"></div></div>'+
        '<div class="card" style="margin-top:14px"><h3>Protocol paths</h3><table class="tbl"><tr><td>VLESS</td><td class="mono">/ws/&lt;uuid&gt; · /xhttp-siz10/…</td></tr><tr><td>Trojan</td><td class="mono">/trojan-ws · /txhttp-siz10/…</td></tr><tr><td>Shadowsocks</td><td class="mono">/ss-ws (AEAD)</td></tr></table><p class="ftx" style="font-size:12px;margin:9px 0 0">WebSocket upgrade, keep-alive and long-lived connections supported end-to-end. TLS at the edge.</p></div>';
      $("#dl2").innerHTML=list.length?list.map(function(d){var url=d.kind==="path"?(location.origin+"/i/"+d.domain):("https://"+d.domain);
        return '<div class="row" style="margin-top:9px"><span class="chip">'+d.kind+'</span><span class="mono" style="overflow:hidden;text-overflow:ellipsis;white-space:nowrap;max-width:70%">'+esc(url)+"</span></div>"}).join(""):'<p class="mut">No endpoints yet.</p>';
      $("#rg").onclick=function(){if(!confirm("Regenerate endpoints? Old links stop working."))return;
        api("POST","/api/instances/"+id+"/domains").then(function(){toast("Endpoints regenerated","ok");refresh()}).catch(function(e){toast(e.message,"err")})};
    }
    else if(tab==="deployments"){
      b.innerHTML='<div class="card" style="padding:0"><table class="tbl"><thead><tr><th>Version</th><th>Status</th><th>Started</th><th>Took</th><th>Error</th></tr></thead><tbody id="dt"></tbody></table></div>';
      api("GET","/api/instances/"+id+"/deployments").then(function(d){
        $("#dt").innerHTML=d.deployments.length?d.deployments.map(function(x){return "<tr><td class='mono'>v"+x.version+"</td><td>"+stEl(x.status).outerHTML+"</td><td class='ftx'>"+ago(x.started_at)+"</td><td>"+dur(x.duration_ms)+"</td><td class='ftx' style='max-width:220px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap'>"+esc(x.error||"")+"</td></tr>"}).join(""):'<tr><td colspan="5" class="ftx" style="text-align:center;padding:20px">No deployments yet.</td></tr>'});
    }
    else if(tab==="activity"){
      b.innerHTML='<div class="card"><h3>Activity</h3><div id="af"></div></div>';
      api("GET","/api/instances/"+id+"/activity").then(function(d){
        $("#af").innerHTML=d.activity.length?d.activity.map(function(a){return '<div style="display:flex;gap:10px;padding:8px 0;border-bottom:1px solid var(--bd)"><span class="ftx mono" style="width:64px;flex:none">'+ago(a.ts)+'</span><span class="mut">'+esc(a.message)+"</span></div>"}).join(""):'<span class="ftx">Nothing yet.</span>'});
    }
    else if(tab==="settings"){
      b.innerHTML='<div class="card" style="max-width:520px"><h3>Danger zone</h3><p class="mut" style="font-size:12.5px">Rotate credentials (endpoint token + internal token) and redeploy, or delete this instance.</p><div class="row" style="margin-top:14px"><button class="btn" id="s-rt">Rotate credentials</button><button class="btn dng" id="s-del">Delete instance</button></div></div>';
      $("#s-rt").onclick=function(){if(!confirm("Rotate credentials and redeploy? Clients must re-import the link."))return;
        api("POST","/api/instances/"+id+"/domains").then(function(){return api("POST","/api/instances/"+id+"/redeploy")}).then(function(){toast("Rotated — redeploying","ok");refresh()}).catch(function(e){toast(e.message,"err")})};
      $("#s-del").onclick=function(){if(confirm('Delete "'+inst.name+'"? This is permanent.')){api("DELETE","/api/instances/"+id).then(nav_("dash")).catch(function(e){toast(e.message,"err")})}};
    }
  }
  function pollLogs(){
    api("GET","/api/instances/"+id+"/logs?tail=200").then(function(d){
      if(!logPaused&&d.logs&&d.logs.length){logBuf=logBuf.concat(d.logs).slice(-600);var el=$("#lb");
        if(el){el.innerHTML=logBuf.map(function(l){var lv=(l.level||"info").toLowerCase();return '<div class="ll '+lv+'"><span class="t">'+new Date(l.ts*1e3).toLocaleTimeString()+"</span> <span class='lv'>"+lv.toUpperCase()+"</span> "+esc(l.message)+"</div>"}).join("");el.scrollTop=el.scrollHeight}}})
    .catch(function(){});
  }
  refresh().then(function(){
    pollTimer=every(5000,function(){
      if(tab==="logs")pollLogs();
      else if(BUSY[inst.status]||tab==="overview")refresh();
    });
  });
  setCleanup(function(){});
}
// ───────────────────────────── admin ─────────────────────────────
function viewAdmin(){
  shell("admin");
  var v=$("#view");
  v.innerHTML='<div class="ph"><div><h1>Admin</h1><div class="sub">Platform-wide state. Actions are audited.</div></div></div><div class="sgs" id="as"></div><div id="ab"></div>';
  var tab="instances";
  function stats(){api("GET","/api/admin/overview").then(function(s){
    $("#as").innerHTML='<div class="sg"><div class="l">Users</div><div class="v">'+s.users+'</div></div><div class="sg"><div class="l">Instances</div><div class="v">'+s.instances+'</div></div><div class="sg"><div class="l">Running</div><div class="v" style="color:var(--grn)">'+s.instances_running+'</div></div><div class="sg"><div class="l">Workers online</div><div class="v">'+s.workers_online+"</div></div>"})
  .catch(function(e){if(e.message.indexOf("admin")>=0)nav_("dash")})}
  function draw(){
    var b=$("#ab");
    if(tab==="instances"){
      api("GET","/api/admin/instances").then(function(d){
        b.innerHTML='<div class="card" style="padding:0;overflow-x:auto"><table class="tbl"><thead><tr><th>Instance</th><th>Owner</th><th>Status</th><th>Actions</th></tr></thead><tbody>'+
        d.instances.map(function(i){return '<tr data-id="'+i.id+'"><td><b>'+esc(i.name)+'</b> <span class="ftx mono">'+esc(i.slug)+'</span></td><td>@'+esc(i.owner_login)+"</td><td>"+stEl(i.status).outerHTML+
        '</td><td><div class="row" style="gap:5px"><button class="btn sm" data-a="restart">Restart</button><button class="btn sm" data-a="stop">Stop</button><button class="btn sm dng" data-a="del">Delete</button></div></td></tr>'}).join("")+"</tbody></table></div>";
        Array.prototype.forEach.call(b.querySelectorAll("tr[data-id] .btn"),function(btn){btn.onclick=function(){
          var id=btn.closest("tr").dataset.id,a=btn.dataset.a;
          var p=a==="del"?(confirm("Delete this instance?")?api("DELETE","/api/admin/instances/"+id):Promise.resolve())
            :api("POST","/api/admin/instances/"+id+"/actions/"+a);
          Promise.resolve(p).then(function(){toast(a+" done","ok");draw()}).catch(function(e){toast(e.message,"err")})}});
      });
    }
    else if(tab==="users"){
      api("GET","/api/admin/users").then(function(d){
        b.innerHTML='<div class="card" style="padding:0;overflow-x:auto"><table class="tbl"><thead><tr><th>User</th><th>Instances</th><th>Flags</th><th>Last login</th><th>Actions</th></tr></thead><tbody>'+
        d.users.map(function(u){return '<tr data-id="'+u.id+'"><td><b>'+esc(u.name||u.login)+"</b> <span class='ftx'>@"+esc(u.login)+"</span></td><td>"+u.instance_count+
        "</td><td>"+(u.is_admin?'<span class="chip">admin</span> ':"")+(u.is_disabled?'<span class="chip" style="color:var(--red)">disabled</span>':"")+"</td><td class='ftx'>"+ago(u.last_login_at)+
        '</td><td><div class="row" style="gap:5px"><button class="btn sm" data-a="adm">'+(u.is_admin?"Revoke admin":"Make admin")+'</button><button class="btn sm '+(u.is_disabled?"":"dng")+'" data-a="dis">'+(u.is_disabled?"Enable":"Disable")+"</button></div></td></tr>"}).join("")+"</tbody></table></div>";
        Array.prototype.forEach.call(b.querySelectorAll("tr[data-id] .btn"),function(btn){btn.onclick=function(){
          var id=btn.closest("tr").dataset.id,a=btn.dataset.a;
          var patch=a==="adm"?{is_admin:btn.textContent.indexOf("Make")===0}:{is_disabled:btn.textContent!=="Enable"};
          api("PATCH","/api/admin/users/"+id,patch).then(function(){toast("Updated","ok");draw()}).catch(function(e){toast(e.message,"err")})}});
      });
    }
    else if(tab==="workers"){
      api("GET","/api/admin/workers").then(function(d){
        b.innerHTML='<div class="card" style="padding:0;overflow-x:auto"><table class="tbl"><thead><tr><th>Node</th><th>Region</th><th>Status</th><th>CPU</th><th>Memory</th><th>Capacity</th><th>Heartbeat</th></tr></thead><tbody>'+
        (d.workers.length?d.workers.map(function(w){return "<tr><td class='mono'>"+esc(w.node_id)+"</td><td>"+esc(w.region)+"</td><td>"+stEl(w.status).outerHTML+"</td><td>"+(w.cpu_percent!=null?w.cpu_percent.toFixed(0)+"%":"—")+"</td><td>"+(w.mem_used_mb!=null?w.mem_used_mb+" / "+w.mem_total_mb+" MB":"—")+"</td><td>"+(w.instances||0)+" / "+(w.capacity||"?")+"</td><td class='ftx'>"+ago(w.last_heartbeat)+"</td></tr>"}).join(""):'<tr><td colspan="7" class="ftx" style="text-align:center;padding:20px">No workers reported yet.</td></tr>')+"</tbody></table></div>"});
    }
    else if(tab==="system"){
      Promise.all([api("GET","/api/admin/system"),api("GET","/auth/me")]).then(function(rs){
        b.innerHTML='<div class="card" style="max-width:540px"><h3>Change your password</h3>'+
        '<div class="fld"><label>Current password</label><input class="inp" id="cp" type="password"></div>'+
        '<div class="fld"><label>New password (min 8 chars)</label><input class="inp" id="np" type="password"></div>'+
        '<button class="btn pri" id="cpb">Update password</button></div>'+
        '<div class="card" style="max-width:540px;margin-top:14px"><h3>System</h3><table class="tbl">'+
        '<tr><td style="color:var(--fnt);width:45%">Database</td><td>'+(rs[0].database.ok?"PostgreSQL/SQLite OK":"down")+"</td></tr>"+
        '<tr><td style="color:var(--fnt)">GitHub OAuth</td><td>'+(rs[0].github_oauth?"configured":"not configured (password login)")+"</td></tr>"+
        '<tr><td style="color:var(--fnt)">Railway provider</td><td>'+(rs[0].provider.railway?"configured":"not configured")+"</td></tr></table></div>";
        $("#cpb").onclick=function(){
          api("POST","/auth/change-password",{current_password:$("#cp").value,new_password:$("#np").value})
          .then(function(){toast("Password updated","ok");$("#cp").value="";$("#np").value=""})
          .catch(function(e){toast(e.message,"err")});
        };
      });
    }
  }
  function tabs(){
    v.innerHTML=v.innerHTML.replace(/<div id="ab"><\/div>[\s\S]*$/,'<div class="tabs" id="atb"></div><div id="ab"></div>');
  }
  // simpler: re-render header tabs each time
  function rebuild(extra){
    var old=$("#ab");var head=v.querySelector(".ph"),sgs=$("#as");
    v.innerHTML="";v.appendChild(head);v.appendChild(sgs);
    var tb=document.createElement("div");tb.className="tabs";tb.id="atb";
    ["instances","users","workers","system"].forEach(function(t){var btn=document.createElement("button");btn.className="tab "+(t===tab?"act":"");btn.textContent=t[0].toUpperCase()+t.slice(1);btn.onclick=function(){tab=t;rebuild();draw()};tb.appendChild(btn)});
    var ab=document.createElement("div");ab.id="ab";v.appendChild(tb);v.appendChild(ab);
    draw();
  }
  stats();rebuild();
}
// ───────────────────────────── plans & customers ─────────────────────────────
function fmtGB(bytes){return (bytes/(1024*1024*1024)).toFixed(bytes && bytes<1073741824?3:1)}
function fmtExpiry(iso){if(!iso)return"never";var d=new Date(iso);var days=Math.ceil((d-new Date())/864e5);
  if(days<0)return"expired";if(days===0)return"today";return days+"d left"}

function viewPlans(){
  shell("plans");
  var v=$("#view");
  v.innerHTML='<div class="ph"><div><h1>Plans</h1><div class="sub">Multi-region bundles you sell as customer subscriptions.</div></div>'+
    '<div class="ha"><button class="btn pri" id="p-new">+ Create Plan</button></div></div>'+
    '<div id="p-list"><span class="sp1"></span></div>';
  $("#p-new").onclick=function(){SND.click();viewPlanCreate()};
  api("GET","/api/plans").then(function(d){
    var list=$("#p-list");
    if(!d.plans.length){
      list.innerHTML='<div class="empty"><b>No plans yet</b>Group a few running instances — one per region — into a plan, then sell subscriptions under it.<div style="margin-top:14px"><button class="btn pri" id="p-new2">Create your first plan</button></div></div>';
      $("#p-new2").onclick=function(){viewPlanCreate()};
    }else{
      list.innerHTML='<div class="ig">'+d.plans.map(function(p){
        return '<div class="ic" data-id="'+p.id+'"><div class="t"><span class="nm">'+esc(p.name)+'</span><span class="chip">'+esc(p.protocols.join(", "))+'</span></div>'+
          '<div class="mt"><span>'+p.instance_count+' region'+(p.instance_count===1?"":"s")+'</span><span>'+p.customer_count+' active customer'+(p.customer_count===1?"":"s")+'</span></div></div>';
      }).join("")+"</div>";
      Array.prototype.forEach.call(list.querySelectorAll("[data-id]"),function(card){
        card.onclick=function(){viewPlanDetail(card.dataset.id)}});
    }
  }).catch(function(e){$("#p-list").innerHTML='<p class="ftx">'+esc(e.message)+"</p>"});
}

var PLAN_PROTOS=[["vless-ws","VLESS"],["trojan-ws","Trojan"],["shadowsocks","Shadowsocks"],["xhttp-packet-up","xHTTP"]];

function viewPlanCreate(){
  shell("plans");
  var v=$("#view");
  v.innerHTML='<div class="ph"><div><h1>Create Plan</h1><div class="sub">Pick the running instances to bundle — normally one per region.</div></div></div>'+
    '<div id="pc-body"><span class="sp1"></span></div>';
  var sel={};sel[PLAN_PROTOS[0][0]]=true;
  api("GET","/api/instances").then(function(d){
    var running=(d.instances||[]).filter(function(i){return i.status==="running"});
    var body=$("#pc-body");
    body.innerHTML='<div class="card">'+
      '<div class="fld"><label>Plan name</label><input class="inp" id="pc-name" placeholder="e.g. Family 4-location plan"></div>'+
      '<div class="fld"><label>Protocols sold under this plan</label><div class="optg">'+
        PLAN_PROTOS.map(function(p){return '<div class="opt '+(sel[p[0]]?"sel":"")+'" data-p="'+p[0]+'"><div class="t">'+p[1]+"</div></div>"}).join("")+
      "</div></div>"+
      '<div class="fld"><label>Instances to bundle</label>'+
      (running.length?running.map(function(i){
        return '<div class="row" style="justify-content:space-between;padding:8px 0;border-bottom:1px solid var(--bd)">'+
          '<label class="row" style="gap:8px;cursor:pointer"><input type="checkbox" data-inst="'+i.id+'"><b>'+esc(i.name)+'</b><span class="ftx mono">'+esc(i.region)+"</span></label>"+
          '<input class="inp" style="width:170px" placeholder="Region label" data-label-for="'+i.id+'" value="'+esc(i.region)+'">'+
          "</div>";
      }).join(""):'<p class="ftx">No running instances yet — deploy at least one instance first (Create Instance), then come back here.</p>')+
      "</div>"+
      '<div class="row" style="margin-top:16px"><button class="btn" id="pc-back">Back</button><div class="grow"></div><button class="btn pri" id="pc-go">Create plan</button></div>'+
      "</div>";
    Array.prototype.forEach.call(body.querySelectorAll(".opt[data-p]"),function(o){
      o.onclick=function(){SND.toggle();var p=o.dataset.p;
        if(sel[p]){if(Object.keys(sel).length>1){delete sel[p];o.classList.remove("sel")}}
        else{sel[p]=true;o.classList.add("sel")}}});
    $("#pc-back").onclick=function(){SND.click();viewPlans()};
    $("#pc-go").onclick=function(){
      SND.click();
      var name=$("#pc-name").value.trim();
      if(name.length<2){toast("Give the plan a name (2+ chars)","err");return}
      var ids=[];var labels={};
      Array.prototype.forEach.call(body.querySelectorAll("[data-inst]"),function(cb){
        if(cb.checked){ids.push(cb.dataset.inst);
          var li=body.querySelector('[data-label-for="'+cb.dataset.inst+'"]');
          labels[cb.dataset.inst]=(li&&li.value.trim())||"";}});
      if(!ids.length){toast("Pick at least one instance","err");return}
      $("#pc-go").disabled=true;
      api("POST","/api/plans",{name:name,protocols:Object.keys(sel),instance_ids:ids,region_labels:labels})
        .then(function(plan){toast("Plan created","ok");viewPlanDetail(plan.id)})
        .catch(function(e){$("#pc-go").disabled=false;toast(e.message,"err",6000)});
    };
  }).catch(function(e){$("#pc-body").innerHTML='<p class="ftx">'+esc(e.message)+"</p>"});
}

function viewPlanDetail(planId){
  shell("plans");
  var v=$("#view");
  v.innerHTML='<div id="pd-body"><span class="sp1"></span></div>';
  function load(){
    return api("GET","/api/plans/"+planId).then(draw);
  }
  function draw(plan){
    var body=$("#pd-body");
    body.innerHTML='<div class="ph"><div><h1>'+esc(plan.name)+'</h1><div class="sub">'+esc(plan.protocols.join(", "))+" · "+plan.instances.length+" region"+(plan.instances.length===1?"":"s")+"</div></div>"+
      '<div class="ha"><button class="btn" id="pd-addcust">+ Add customer</button><button class="btn dng" id="pd-del">Delete plan</button></div></div>'+
      '<div class="card"><h3>Regions</h3><table class="tbl"><thead><tr><th>Region</th><th>Instance</th><th>Status</th></tr></thead><tbody>'+
      plan.instances.map(function(i){return "<tr><td><b>"+esc(i.region_label)+"</b></td><td>"+esc(i.instance_name)+"</td><td>"+stEl(i.status).outerHTML+"</td></tr>"}).join("")+
      "</tbody></table></div>"+
      '<div class="card" style="margin-top:14px" id="pd-newcust" hidden>'+
      '<h3>New customer</h3>'+
      '<div class="row"><div class="fld" style="width:200px;margin:0"><label>Name</label><input class="inp" id="nc-name" placeholder="e.g. Sister"></div>'+
      '<div class="fld" style="width:140px;margin:0"><label>Quota (GB, 0 = unlimited)</label><input class="inp" id="nc-gb" type="number" min="0" step="0.5" value="50"></div>'+
      '<div class="fld" style="width:140px;margin:0"><label>Duration (days, blank = never)</label><input class="inp" id="nc-days" type="number" min="1" value="30"></div></div>'+
      '<div class="fld"><label>Note (optional)</label><input class="inp" id="nc-note" placeholder="e.g. paid via bank transfer 12/09"></div>'+
      '<button class="btn pri" id="nc-go">Create customer</button>'+
      '</div>'+
      '<div class="card section-gap" style="margin-top:14px"><h3>Customers</h3><div id="pd-custs"></div></div>';
    $("#pd-del").onclick=function(){
      if(!confirm('Delete plan "'+plan.name+'"? This revokes every customer under it.'))return;
      api("DELETE","/api/plans/"+planId).then(function(){toast("Plan deleted","ok");viewPlans()}).catch(function(e){toast(e.message,"err")});
    };
    $("#pd-addcust").onclick=function(){SND.click();var f=$("#pd-newcust");f.hidden=!f.hidden};
    $("#nc-go").onclick=function(){
      SND.click();
      var name=$("#nc-name").value.trim();
      if(!name){toast("Give the customer a name","err");return}
      var gb=parseFloat($("#nc-gb").value||"0");
      var daysRaw=$("#nc-days").value.trim();
      var days=daysRaw?parseInt(daysRaw,10):null;
      $("#nc-go").disabled=true;
      api("POST","/api/plans/"+planId+"/customers",{name:name,limit_gb:gb,days:days,note:$("#nc-note").value.trim()})
        .then(function(cust){
          toast("Customer created","ok");
          $("#pd-newcust").hidden=true;
          showSubResult(cust);
          return load();
        }).catch(function(e){$("#nc-go").disabled=false;toast(e.message,"err",6000)});
    };
    drawCustomers(plan);
  }
  function showSubResult(cust){
    var ov=document.createElement("div");ov.className="qr-ov";
    ov.innerHTML='<div class="qr-c" style="max-width:400px;text-align:left">'+
      '<b style="font-size:14px">'+esc(cust.name)+" — subscription ready</b>"+
      '<div class="mono" style="margin:10px 0;background:var(--bg2);border:1px solid var(--bd);border-radius:8px;padding:8px 10px;word-break:break-all">'+esc(cust.sub_url)+"</div>"+
      '<div class="row"><button class="btn sm pri" id="sr-copy">Copy link</button><button class="btn sm" id="sr-qr">Show QR</button><button class="btn sm" id="sr-close" style="margin-left:auto">Done</button></div>'+
      '<div class="qrbox" style="margin-top:12px;display:none"></div>'+
      "</div>";
    document.body.appendChild(ov);
    ov.onclick=function(e){if(e.target===ov)ov.remove()};
    $("#sr-close",ov).onclick=function(){ov.remove()};
    $("#sr-copy",ov).onclick=function(){navigator.clipboard&&navigator.clipboard.writeText(cust.sub_url).then(function(){toast("Copied","ok",1500)})};
    $("#sr-qr",ov).onclick=function(){
      var box=ov.querySelector(".qrbox");box.style.display="block";box.innerHTML='<span class="sp1"></span>';
      var firstInst=plan_cache_instance_id;
      api("POST","/api/instances/"+firstInst+"/qr",{text:cust.sub_url}).then(function(svg){box.innerHTML=svg}).catch(function(e){box.innerHTML='<span class="ftx">'+esc(e.message)+"</span>"});
    };
  }
  var plan_cache_instance_id=null;
  function drawCustomers(plan){
    plan_cache_instance_id=plan.instances.length?plan.instances[0].instance_id:null;
    var host=$("#pd-custs");
    if(!plan.customers.length){
      host.innerHTML='<p class="ftx">No customers yet — add one above and hand them the subscription link.</p>';return;
    }
    host.innerHTML='<table class="tbl"><thead><tr><th>Name</th><th>Usage</th><th>Expires</th><th>Status</th><th></th></tr></thead><tbody>'+
      plan.customers.map(function(c){
        var pct=c.limit_bytes?Math.min(100,100*c.used_bytes_cached/c.limit_bytes):0;
        var usage=c.limit_bytes?fmtGB(c.used_bytes_cached)+" / "+fmtGB(c.limit_bytes)+" GB":fmtGB(c.used_bytes_cached)+" GB / ∞";
        var status=!c.active?'<span class="st fail"><span class="d"></span>Disabled</span>':'<span class="st run"><span class="d"></span>Active</span>';
        return "<tr data-cid=\""+c.id+"\"><td><b>"+esc(c.name)+"</b>"+(c.note?'<div class="ftx" style="font-size:11px">'+esc(c.note)+"</div>":"")+"</td>"+
          '<td><div style="width:110px">'+usage+'<div class="meter" style="margin-top:4px"><div class="'+(pct>90?"crit":pct>70?"warn":"")+'" style="width:'+pct+'%"></div></div></div></td>'+
          "<td>"+fmtExpiry(c.expires_at)+"</td><td>"+status+"</td>"+
          '<td><div class="row" style="gap:4px;flex-wrap:nowrap">'+
          '<button class="btn sm" data-act="copy">Copy link</button>'+
          '<button class="btn sm" data-act="extend">+30d</button>'+
          '<button class="btn sm" data-act="reset">Reset</button>'+
          '<button class="btn sm" data-act="toggle">'+(c.active?"Disable":"Enable")+"</button>"+
          '<button class="btn sm dng" data-act="del">Revoke</button>'+
          "</div></td></tr>";
      }).join("")+"</tbody></table>";
    Array.prototype.forEach.call(host.querySelectorAll("[data-act]"),function(btn){
      var tr=btn.closest("tr");var cid=tr.dataset.cid;
      var cust=plan.customers.filter(function(c){return c.id===cid})[0];
      btn.onclick=function(){
        SND.click();
        var act=btn.dataset.act;
        if(act==="copy"){
          var origin=location.origin;
          navigator.clipboard&&navigator.clipboard.writeText(origin+"/sub/"+cust.sub_token).then(function(){toast("Copied","ok",1500)});
          return;
        }
        if(act==="extend"){
          api("PATCH","/api/plans/"+planId+"/customers/"+cid,{extend_days:30}).then(function(){toast("Extended 30 days","ok");load()}).catch(function(e){toast(e.message,"err")});
          return;
        }
        if(act==="reset"){
          if(!confirm("Reset usage back to zero for "+cust.name+"?"))return;
          api("PATCH","/api/plans/"+planId+"/customers/"+cid,{reset_usage:true}).then(function(){toast("Usage reset","ok");load()}).catch(function(e){toast(e.message,"err")});
          return;
        }
        if(act==="toggle"){
          api("PATCH","/api/plans/"+planId+"/customers/"+cid,{active:!cust.active}).then(function(){toast(cust.active?"Disabled":"Enabled","ok");load()}).catch(function(e){toast(e.message,"err")});
          return;
        }
        if(act==="del"){
          if(!confirm('Revoke "'+cust.name+'"’s subscription? This deletes their credential in every region.'))return;
          api("DELETE","/api/plans/"+planId+"/customers/"+cid).then(function(){toast("Revoked","ok");load()}).catch(function(e){toast(e.message,"err")});
        }
      };
    });
  }
  load().catch(function(e){$("#pd-body").innerHTML='<p class="ftx">'+esc(e.message)+"</p>"});
}

// ───────────────────────────── boot ─────────────────────────────
function render(){
  api("GET","/auth/me").then(function(me){
    if(!me.authenticated){viewLogin();return}
    USER=me.user;CSRF=me.csrf_token;
    viewDash();
  }).catch(function(e){
    $("#app").innerHTML='<div class="lw"><div class="lc"><div class="card"><b>Voidz Console failed to load</b><p class="mut">'+esc(e.message)+"</p></div></div></div>";
  });
}
render();
})();
</script>
</body>
</html>
"""

router.add_api_route("/panel", lambda: HTMLResponse(PAGE), methods=["GET"], include_in_schema=False)
