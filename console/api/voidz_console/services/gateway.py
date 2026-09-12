"""Instance endpoint gateway.

On platforms that expose a single public HTTP endpoint per deployment
(e.g. Lucity's workload domain with Gateway API HTTPRoutes), every Voidz
instance is reached through the Console's public URL under a private
endpoint token:

    https://<console-host>/i/<endpoint-token>/<core-path>

The gateway authenticates by endpoint token (un guessable, rotatable),
strips the prefix, and proxies HTTP and WebSocket traffic to the instance's
Voidz Core through the Worker. On self-hosted deployments with wildcard DNS
the same instances can additionally be exposed as real hostnames via the
bundled Caddy — both modes share this proxy path.

WebSocket proxying is implemented frame-by-frame (client ⇄ gateway ⇄ core)
because the standard HTTP client stack cannot pass an Upgrade through.
"""
from __future__ import annotations

import asyncio
import httpx
import websockets
from fastapi import APIRouter, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import Response, StreamingResponse

from ..db import get_pool
from ..logging import get

log = get("network", "voidz.console.gateway")

_LOGO_B64 = "iVBORw0KGgoAAAANSUhEUgAAAEAAAABACAYAAACqaXHeAAAUVElEQVR42u1bd3hUVd5+z7l3amYyJYWUSS8ECIokYBRxAAVEUXRxggqyIlZWRddecMi68CnYEAXBigiyGUR0gaUoydCrQEihBGIIIZA6M5l+y/n+IBF2PwssRfdb3ueZv2aee895f70McAmXcAmXcAk/AcbI/4NbkHO6h81WzLH/UCLsjNF/IuKMGQOQ1/+2+JvGPJZ7ShkY958k9ZISxgOAHaBXjbznaktBgebnSKD/qvg2m41Lj+MbmwJh6+PTPp3BGNMTQiTGGLEVF/+uibAVMw4AGziQiGs2VfUs++tbX7sgSvVbtwZgt5OzMP+Tat9r1OObitdsrxEZG/WjatkZtdvt9Hel7nY7PaXyl0V4PMHnXv12k5A84emnTxJztoKz2ykhBIjqmpA+7B7flrJqtuOwv2TSzOWDf1f+gTFis5263F0fLrNtb/OXr6qtZ5qnXv4OAKx2O//vPdxq5SkBaP7gCTG9BrEPFm9kb8zfyP708twvJ04r7nWKqxL+t4gYVuupi418YWb+iGkLltkPedk723Yxxbg/teG+P2czxgh+RVvJL39no4wVM0PuVZvgbsu/a/TDYRm8xu1qCeujoz7UxiS/9s7jtxzpdJSEEOmC27nNxjkcDgkA7n1tYUJLc/1LAUbuM11tVWjFVv/CT2ZrQ7Fxz5B5709nVjsPZ5H4S8/7JXYYbAAhRI5LinsKKiVZ+OE0ruV4TcjnaaVNdT9McB+t/v7pd5e99MCcHYZOR/kv4ee8endbcTHncDgkxhgd+8yrjxzbv2unp+nEwyTSSNzVZf5FU1/Shij3fd6j973NbDYOzqJfFcgvH9bhkGCzcQdWLt2gS0lfKvEK5aqlnzBZ9CMcCARbG+rMvpaWV7p1UexcVuV6gBCCIkLk8x0tOpwucxQWSkXTZvcb/fCzG47VVM9saaiLEzk+GGiqY6UzX+EDETqZV9BHdubnCz8K8Vdwpg6CNFHlZFNG1+Gu7zdz69d8xaxDb+fVaq3obqyTPI0JGZYrc+dsbQiMXX+4/dGn+sXusjNGiwiRz93PMUIIkVesWKH6vvzQlL1VFY8fOVrPhUUpqDLGcKGAh9/9zRJRtCSreY1mnrjUsRk2G4cOMzk3DTilBVT41rHXrzMuNaRmKHw+v7R+zRKoFCCJSUl8pBphb5srKPvEfrTpyIYXFm8cWkSIfK7mYD8ZjVhJSYnlQG1D6e695U9WHzwoh4LBEOVVfFAMk7Jvv2JChI7XWFLcvKtxEhgjcDjYmb7jbA5IaEzS66IpWjKYTVx7uxer/74A0SYdel/WjRq14JuP1gSaD5Zr63ft/GyI/QMzJk8+l5qCTJ48GcXFxUqvxC/Zvqeq4GB1tR+EEoByIhiqtnyLYDgkqa/oywfVmjnBHTvq8Ng7SlsxIzbGODBGf+39Z0aAwyHBbieeBW9s55KzSiSlWqE3m6XG48cx971piDEooIvQwOV2KZgYDgiuplh2pOqZoqIi2eZw/FtaUFJSwhFC5MSMnHsOHWvps7/6cECrjVAyWQZTKHCoYgcCXg9TZXVXSgmJDZIprQgAMHNiyFFIJAchEgiRQQizMcb9XDg8m8NRANBk57yrSstBuL0NptguqK6swISJExEKhUEIhSyJvBjwiUK7e0L+qIeTHIWFMs4yc2SMkQEDBsjzV6yIbGv3TfpubYmk4ggnyTKoWoP62gPwNNVDGRUtc916IGw2/UNRtjFD9fCkgaaPlgy7Ys/hWwY1uocN9oZ62crLdQ5CJBQVybD/X5M884MVFUlgjNTt27Ba2bXnYaKKUIYDXtkYbUbp2m/x9HPPQa1SQZRlIsqSyMJhPQ22vwCA2Sorz8IMGHnnHweVhBA5OyntsYM1Ry1HqqsFUQhTRjmcaDzOGmsPgBpMIJYkGkpNoWTL5nulgLdMKt+x1rfkyxXVb7/7ddn0d1eUf7RwR1lzoHxQbcNcfPh5CoqI/K8mcbbhisesWWF63U1mTVga4D6wR1CoNVQXoUd5eRmEcACJyRk4drSOuF3NTGLssugrChaXOBY0w26ncDrZL8X4HgCtrCyUVy6YKc2bOjNKlZL8xefzv1D6PC4iSRLxBoOoqdhOiEoFGpcgSVf0UbBuOSVs375XSKRutRwI7WGtzR6ppiZGqKjU+L7fI7bsq4vSm6PybhwywFZ5w20rxXRLc9HkyRRFRexswmAnZABwt9Z9buwS/2yEIZpvb2uG3kwRaTRi+fJvQAgPpVpDJFESGaFqyujzAO6xVVZSx0/UHNbSUup0OkVHYaEEAB8ccZlfXr6mf6hX9oSKskpT9YGqsF6joSLlUXtwF5gsgUYlQDaaKc3Lhyo98cXA6m+2yKcFfsXQEalan/Q2leQRwg/lwT3TDkt/6PVx4pj83FcIISOLGaOF/4YPwEk7slN8NKvay6S16vQcXqFSi15XMxOCfii1Ony7+u/we1rBKZR8yOcVwSvu7PHwM90cxcWdvoDYbDYOAEFRkex0OkXGmPqZuYuG3jrlnQ/e+njebhL2L02NNAxZ9s3XAsdkKhOKhvoaBNuaQM3RIDq9hD5XKmK652z2DxmyFXPmKGC18rBaedhsXGjV1z+0Hd83Sq0gNVoCJSJ1XDgYkrtwXBoA3EmpdLaJ0Cl02LPIQq95U9Ju1Hna4G5tgNfdDJ0pFoGwgD07NyI1uyckISxygqjWGJP/DELuz7zhBmU1EHI4HBLlOIy0f9CzufHgqPwxD41sDodyWnke7T4fJo4aFWyorKJVVZXUbDShzeNC05GDoHoDiD4Scpc4GG8ZgVyD4X0CMGt2NnM6neJpBQMHhyOk79av3iuRNH2Py8Q+PbPUrx1r2goA18gy7yREPHsN6AyJxcUclixcF7TEvSffOU6tTOshwmCE190MXsGjsbUFTcdqoFCrOO/RWlEbZbzrmQN1luqVK0N//GSX8fJbx49J6zdsjfObT8u2bix9cefu7Tm1VWXV7fsr3k8R/C9en5ZFlixdSjkms5DMcLz2AMDxDCYzoNPL7KabFT2z02v/Ulq1GIwR54CB0unFElm8WLKOn5CpjYi8wh2dEJ5w393qjaGQd/POA29TQuDsMOVzLkzy8qDo8d3G1b3XlzHu2mF+Ep8oUJ1eUMVaBG1UFyG3YKCQ1qtf8Orn32Ijvlw7PyYjryimR5/jEaldGY1PYoiNr0ScZSqflH7N4MGDIwDg829K//LWZ8tYatfLA5k9rxSiU3MEcJxA4xIFLitHwMi7/PnHWthrx5ueBAB7R/urM3PsbN8Nnvjq8q7jXpb6r94WHHeiVUbpjtvoyRh7noo1xggYI6vGjIko/OHo0pQt5YwfcquAuASBGkwCHxUnxCSnC92uul7IGjQynP/6QqZMzmDQ6lpgMM1CVNTAPEBxek1uGzs28ZXZX7SPGP2QlJCSHU7J7StwmgiBmKIEmpIm0F75AfUXS9gdRxs2bCou1thPy/RsxcUcISef9ND7y9+78d3lLG1dGeuxZacXr773BwIA572l10ECAMXl23e+HbetPMjdXBgmsV0EGh0r0KhYIbVnvpCVPyDY/b6Xxdg7H/sMgLnzoJ1+yGazKQFg/OMvTZrwwnSWc3kff1L2ZUJkXJIAjVagickCTUoNkMeeYnHrNu/MmTcv6vTWvdVeclILLAWaNbsOfPbBcYH1ONzMor5wlOHKgXkdv+UuSH1+elIVO/X172K37hFp4d0hLi5eIHEJgibOImT2sYYyrLew9PsnbwYhQF6eoiMHIZ2f4cOHawvHP3F48G13y5bU7FBcRg+BqDUCiY4VaExsiN58G6MffbYLU6bEdIZQ2GxcJwmPPT8rd9vh41tFxtjwYyfC6rkfvwlAhwsh+dMvPnrLgcjkB598JKJP/xoYo5nhvgdZwrY9YTzwqICUNAGxXYTYrB5Ceu/+oeTh45hpxH1Df/TUAKxWKw8AQ0eOLrzBNp716H1VMC4tR9BGxwnQ6QVqModonwKR2l85gOnTYwEAc+YoOm2ZAXTQH194/K61ldJsxtjdNXXrMGee9aRIKHBeG7iso8rqaIHd8vnf709/6PmDmt79GCKNfhppfBHxlnnmJ55i17Z5A9pnXhKQlCrwcQlCcm6fQPLVw5j5hrGLTiegs8N81eARq68cdBNLzugejE7JEohOHyaRRoFmdQ3Re+9nKOh3MwBgxgxV53EyewwckvnstL3Za3ez5E07yvG3JWN+dCknz0kuyKTliR1VA4fO+8fGjEenMlX+QAZzzGwYDKkAYOjbPw2X5fly3p4pDG1rD5NxDwowRwvGtOywJbevZOx3czusN1g6G68AkGsdktOzYFAou2e+EJuSJWhi4gVE6ARqSQ7QUXcx0vOyDaffJCbv+mtiHplUEj1nEdMt+OqQYvbcewAoAYCj5KxUnj/TgUMRIdIDc+xavveYqWVbyv90aMdu3lW1ZR+O7H8ErU3fnRRJpsq9bX0N6V3wt30ffzqu7XB1MP6hB/ljNYfgLdtNlApVmPd7dBpNhC0AvJUC8LWAGPK030EJVfp8vmBAEvlg0AcuIgLk8iuoXFkhsr1ljwKActzTwzWZqc+GTfprwkysDHnr75QffHIxAJFQCiZJnESIhI60+rwQYC0p4R0DiXj35s3dYkyZC8s27O9Vt3kvuMZ9y8WKVfeEvGiG1crD6ZRRXS0AIEylmsaB3Xli3nw+prUNxolPwPXEY/B7XFRDeBCG0QBm1DoHhJHnVQR9fhtlDGFJJCFJACOAlJklo7VFCbVmS/Tm8ny+tcUhh0MZgdbG0vDhg8NCU4pW/mjnixZxrLBQxnnvSp8cNSF9/lfXXbOmosX6xmrWd+J86ZoHpqwEwBNCf1Tjf0pDAZCCAQtpbi8GSgOmJ54SFK++KVC9QTAmZwq6bn1EPiuvL2OMJHa9fEB8Vi6LSc4K87EJAjRaQXlVfyF3ymvCuBWrQmOPNbG+lQd9Wes2fmCZPiX3VMyhnap+Tnb+8xpQXMyhkEjc3M8GeX3ysuZPFykVQYRjs7Nd/iNVY0GIyG4fycHh+Km+O2GaiNcIgY3EJ3KumTMQMe0N+K6xIrxhncgpNWpG+UJCyDYYYm1ahQI6hVLKzOrOR/W7Fgkj/4D05C5ydX29ct+O7a9UTJv6FjZsaENnJldYSOBwnJWqn/VoDIRA9fXKTG7W5y3RQ8ZIqT0Hefv+cQob/tyHswDghkdnqH6W/U4tuOn2b7i8qxjRRQZIeoaAov8RYI4OcZFmxkcllNmvKMi03nZ39bhps+Vxy9eHC776VoibMUdQP/hIEDeNYLiy37rTTREXYCZJfibcURDCTCtKVrm/XDE4euPGIFUqSWRCV2WixbKy5MNJN57aP5DJZIAUORwENhsD5WSAAYwBN92Wi5CwA1V7KF9fR/TDbobJFIsojxcReVcyLjc3JERotU0NtXK1cy2E0u+A1mYQtVbmYuMUGpWqn+f7bVvIgAEcTq/2ziP4n1R9QqS+dccLaioPD2YH9ofDTOB1vA7tzUfEJrVq2HXjJzlooGXmzoWzdhNCPJ0DiM60bhKg3prYM1pSmQ0Hc5KPavpem2aIMktyVDQRzGYcb21Cy4EK4v90thaHDkloOEYghMCJAqFGg0CjY9WCwfRl+2bnZlJYeMEu/5MEWGNsxAkgS6Pp7s/KRFNqpuBvOKIS2xoQoTcS14kagVdn356QkHH7kJfeOeJrdx055va6GnmFGI7QqalOZ55rMiSQSL1FmZQIbRcjZCHEDu2vIp51KxH64TBQdxTYvw8c5SQ+0khgMEDwusFBxZRaPS+ZY4JydMwkAATduzPgQu7Q/IT6E0LkW6oO9YxPtnz/dVUt3/DVMgFV5TKCAQZKAZnJ0Bs4lSVFpUjLgCItFV3SkqHSadDubkHoxDGX2Na0h3g9GznRt7Hhk4X3y7W1t6LxRIhwHCVdcwipOQw54INSbwKiYsCajxO1wSQoUzPVnrguH4YXzbv/bCY8588ECJFfPjnW2nvvoR9uHdUj+a/7sh7KdUlEFUcIRElGbSAAj9cDMRDwKWWh0ahU1CaacCAYbNkV3rV+l/To2P31brh+fGZ0QgPVqoZDr6fwuAFBYIiJIzi0j/GmKCKDQaGLlCPiknh/956+sCly6sWQ/i+OxztmcgwAuefIkVxBHdHNSDizXxLkH1wuV1vV/qP+71Y2uN99t/EE4PvJ3n5pKeecNYti8eIwyei2nLa7b6QeV4jp9Rwye0DetBa6Pv2hDPig1mhFYr1e3dot833f+NEPnwzDhRd83P6zeQAhhNmKi7nFhYXSp8nJewHs/SWyHAB9r7SUOJuaGAptcgd5YkfJCmYyvEk57kZOFAn8fqgZg8dghkavh15vYHJWN1573SC/UYfpewGCCtsFl/6Zro8RMEZsAOkOkFIAKC2Fs6mJoaKCdfTX2a8NO2ArpFxD21Z1Q31vuflEOCLewvmFEJIuLwAizWLc3aPVOWnxH89JTxxfzBhXeBGWLc60GGIghDnOaZ9lAAeHU2S3j32PEe5jzuOG2O6GIaYLIqIS4M5I59Mzk0PJbcfeAmOk4gzm+ucLF2fby+mUABBZJX0pJCTWU3OsUgwFmUZnhBgTL5L83nx1oP3LF3v1KrcB52Wv4PdFAMBgt3NYsMAjdolfKKVlESLJEgxGBDPTeF9MpLB39/ZpYIw4HA5cTFzMfT8ZAJiKfCRaLEGm1nEs0iS6c7vxbnfjMtcdd+wBQC+G5/9tCOgcq03/634hOtrJLKkKFhcLT4SC+Tetf71jswMXG/Q3eB+RI7TzxOQ0+LO7qkLellI899wmAORiS//iE1BUJAFgUIRWyBZLvZyZTuTD+98EIcDkyb+r9dsLud7KAYB2xsfzo5euOgqA+y3/m8Bf9DeetHOidp1Yogy4dwGQrJMn805AxH8ZeHTMBv97QQj+23GJgUu4hEu4hEv4DfG/6EuMK/pOl5gAAAAASUVORK5CYII="

HOP_BY_HOP = {
    "connection", "keep-alive", "proxy-authenticate", "proxy-authorization",
    "te", "trailers", "transfer-encoding", "upgrade", "host", "content-length",
    "authorization",  # replaced with the worker token below
}


FRIENDLY_404 = """<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Voidz</title>
<style>body{{margin:0;min-height:100vh;display:flex;align-items:center;justify-content:center;
background:#05070a;color:#eaf1f7;font-family:-apple-system,'Segoe UI',Roboto,sans-serif;
background-image:radial-gradient(900px 420px at 20% -10%,rgba(56,214,217,.14),transparent),radial-gradient(700px 340px at 90% 110%,rgba(139,123,255,.12),transparent)}}
.c{{max-width:420px;text-align:center;padding:30px;border:1px solid rgba(148,175,199,.16);border-radius:16px;
background:rgba(20,26,37,.6);backdrop-filter:blur(20px)}}
h2{{margin:0 0 8px}}p{{color:#9fb0c3;font-size:13.5px;line-height:1.55}}
code{{background:rgba(255,255,255,.05);border:1px solid rgba(148,175,199,.16);border-radius:6px;padding:1px 6px;font-size:12px}}</style></head>
<body><div class="c"><h2>{title}</h2><p>{body}</p></div></body></html>"""


def _page(title: str, body: str, status: int = 200) -> "HTMLResponse":
    from fastapi.responses import HTMLResponse

    return HTMLResponse(FRIENDLY_404.format(title=title, body=body), status_code=status)


import json as _json_mod  # noqa: E402

def _sub_html_page(title: str, configs: list, host: str, sub_path: str,
                   qr_path: str = "", info: dict | None = None) -> str:
    """Premium subscription page: QRs inline, copy buttons, app links,
    EN/FA toggle. Browsers get it; clients are UA-sniffed to raw data."""
    import html as _html
    import io

    import qrcode
    import qrcode.image.svg

    esc = _html.escape

    def qr_svg(text: str) -> str:
        img = qrcode.make(text, image_factory=qrcode.image.svg.SvgPathImage,
                          box_size=11, border=1)
        buf = io.BytesIO()
        img.save(buf)
        return buf.getvalue().decode()

    PROTO_META = {
        "vless-ws": ("VLESS", "WebSocket", "#6f9bff"),
        "trojan-ws": ("Trojan", "WebSocket", "#ef6b73"),
        "shadowsocks": ("Shadowsocks", "AEAD", "#4ecb95"),
        "xhttp-packet-up": ("xHTTP", "packet-up", "#e3b341"),
        "xhttp-stream-up": ("xHTTP", "stream-up", "#e3b341"),
    }
    cards = ""
    for i, c in enumerate(configs):
        pname, transport, color = PROTO_META.get(c["protocol"], (c["protocol"], "", "#6f9bff"))
        qr = qr_svg(c["share_url"])
        region_chip = f'<span class="chip" style="margin-right:5px">{esc(c["region"])}</span>' if c.get("region") else ""
        cards += f'''
        <div class="cfg" style="--pc:{color}">
          <div class="ch"><div><span class="pn">{esc(pname)}</span><span class="tr">{esc(transport)}</span></div><div>{region_chip}<span class="chip">{esc(c["protocol"])}</span></div></div>
          <div class="u" id="u{i}">{esc(c["share_url"])}</div>
          <div class="row">
            <button onclick="cp(\'u{i}\')">Copy <span class="en">config</span><span class="fa" hidden>کانفیگ</span></button>
            <button class="g" onclick="tg(\'q{i}\',this)">QR</button>
          </div>
          <div class="qr" id="q{i}">{qr}</div>
        </div>'''

    sub_url = f"https://{host}{sub_path}"
    sub_qr = qr_svg(sub_url)
    sb_url = f"https://{host}{sub_path}?fmt=singbox&host={host}"
    cl_url = f"https://{host}{sub_path}?fmt=clash&host={host}"

    info_card = ""
    if info is not None:
        used_gb = info["used_gb"]
        total_gb = info.get("total_gb")
        pct = max(0.0, min(100.0, info.get("pct") or 0.0))
        unlimited = total_gb is None
        ring_circ = 2 * 3.14159265 * 42
        ring_offset = ring_circ * (1 - (0 if unlimited else pct / 100))
        ring_color = "#ef6b73" if pct > 90 else ("#e3b341" if pct > 70 else "#35d7dc")
        days_left = info.get("days_left")
        days_total = info.get("days_total")
        no_expiry = info.get("no_expiry", True)
        online_count = info.get("online_count", 0)
        max_devices = info.get("max_devices") or 0
        is_online = online_count > 0
        data_lbl = (f"{used_gb:.2f} GB <span class='sm'>used</span>" if unlimited
                   else f"{used_gb:.2f} <span class='sm'>/ {total_gb:.0f} GB</span>")
        day_val = "∞" if no_expiry else str(max(0, days_left))
        day_lbl = ("unlimited" if no_expiry else f"of {days_total} days total")
        day_lbl_fa = ("نامحدود" if no_expiry else f"از {days_total} روز کل")
        dev_val = f"{online_count}/{max_devices}" if max_devices else str(online_count)
        info_card = f'''
        <div class="card stat-card">
          <div class="stats">
            <div class="stat">
              <div class="ring-wrap">
                <svg viewBox="0 0 100 100" class="ring">
                  <circle cx="50" cy="50" r="42" class="ring-bg"/>
                  <circle cx="50" cy="50" r="42" class="ring-fg" style="stroke:{ring_color};stroke-dasharray:{ring_circ:.1f};stroke-dashoffset:{ring_circ:.1f}" data-offset="{ring_offset:.1f}"/>
                </svg>
                <div class="ring-mid">{data_lbl}</div>
              </div>
              <div class="stat-lbl en">Data used</div>
              <div class="stat-lbl fa" hidden>حجم مصرفی</div>
            </div>
            <div class="stat">
              <div class="big-num">{day_val}</div>
              <div class="stat-lbl en">{"Unlimited" if no_expiry else "days left"} <span class="sm">{"" if no_expiry else "· "+day_lbl}</span></div>
              <div class="stat-lbl fa" hidden>{"نامحدود" if no_expiry else "روز باقیمانده"} <span class="sm">{"" if no_expiry else "· "+day_lbl_fa}</span></div>
            </div>
            <div class="stat">
              <div class="dev-pill {'on' if is_online else 'off'}"><span class="dot"></span>{dev_val}</div>
              <div class="stat-lbl en">{"Online now" if is_online else "Offline"}</div>
              <div class="stat-lbl fa" hidden>{"الان آنلاین" if is_online else "آفلاین"}</div>
            </div>
          </div>
        </div>'''

    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(title)}</title>
<style>
*{{box-sizing:border-box}}
body{{background:#05070a;color:#eaf1f7;font-family:-apple-system,'Segoe UI',Roboto,'Vazirmatn',sans-serif;margin:0;padding:0 14px 70px;
background-image:radial-gradient(1000px 460px at 50% -140px,rgba(56,214,217,.16),transparent),radial-gradient(700px 300px at 85% 110%,rgba(139,123,255,.14),transparent)}}
.w{{max-width:600px;margin:0 auto}}
.top{{display:flex;align-items:center;gap:11px;padding:26px 4px 4px}}
.moon{{width:34px;height:34px;object-fit:contain;filter:drop-shadow(0 0 8px rgba(56,214,217,.55))}}
h1{{font-size:22px;margin:0;letter-spacing:.3px;font-weight:750}}
.sub2{{color:#9fb0c3;font-size:12.5px}}
.hero{{text-align:center;padding:10px 0 22px}}
.hero h2{{margin:0 0 6px;font-size:17px}}
.hero p{{margin:0;color:#9fb0c3;font-size:13px}}
.card{{background:rgba(20,26,37,.6);backdrop-filter:blur(18px);border:1px solid rgba(148,175,199,.16);border-radius:16px;padding:17px;margin-bottom:14px;box-shadow:0 16px 36px rgba(0,0,0,.4)}}
.card h3{{margin:0 0 4px;font-size:14px}}
.lbl{{color:#9fb0c3;font-size:12.5px;margin:0 0 10px}}
.subu{{display:flex;gap:8px;align-items:stretch}}
.subu .u{{flex:1;font-family:ui-monospace,monospace;font-size:11px;background:rgba(0,0,0,.25);border:1px solid rgba(148,175,199,.16);border-radius:8px;padding:9px 10px;word-break:break-all}}
.btn{{padding:8px 14px;border-radius:8px;border:none;background:linear-gradient(135deg,#35d7dc,#8b7bff);color:#04141a;font-weight:700;font-size:12.5px;cursor:pointer;box-shadow:0 6px 18px -6px rgba(56,214,217,.5)}}
.btn.g{{background:rgba(255,255,255,.06);color:#eaf1f7;box-shadow:none;border:1px solid rgba(148,175,199,.2)}}
.fmts{{display:flex;gap:7px;flex-wrap:wrap;margin-top:10px}}
.fmt{{font-size:11px;color:#9fb0c3;border:1px solid rgba(148,175,199,.2);border-radius:999px;padding:3px 11px;text-decoration:none}}
.fmt:hover{{color:#eaf1f7;border-color:rgba(56,214,217,.4)}}
.cfg{{background:rgba(255,255,255,.03);border:1px solid rgba(148,175,199,.16);border-left:3px solid var(--pc);border-radius:12px;padding:13px 14px;margin-bottom:11px}}
.ch{{display:flex;justify-content:space-between;align-items:center;gap:8px}}
.pn{{font-weight:700;font-size:13.5px}}
.tr{{color:#5c6b80;font-size:11px;margin-left:7px}}
.chip{{font-size:10px;color:#7ce8ea;border:1px solid rgba(56,214,217,.35);background:rgba(56,214,217,.08);border-radius:999px;padding:1px 8px;font-family:monospace}}
.u{{font-family:ui-monospace,monospace;font-size:10.5px;color:#9fb0c3;background:rgba(0,0,0,.25);border:1px solid rgba(148,175,199,.16);border-radius:8px;padding:7px 9px;margin:9px 0;word-break:break-all;max-height:64px;overflow:auto}}
.row{{display:flex;gap:7px}}
.qr{{display:none;margin-top:11px;text-align:center}}
.qr svg{{width:216px;height:216px;background:#fff;border-radius:10px}}
.apps{{display:flex;flex-wrap:wrap;gap:7px;margin-top:9px}}
.apps a{{font-size:11.5px;color:#7ce8ea;text-decoration:none;border:1px solid rgba(148,175,199,.2);border-radius:999px;padding:4px 12px}}
.apps a:hover{{border-color:#35d7dc}}
.ft{{text-align:center;color:#5c6b80;font-size:11.5px;margin-top:26px}}
.ft a{{color:#7ce8ea;text-decoration:none}}
.fa{{display:none}}
body.fa .en{{display:none}}
body.fa .fa{{display:inline}}
#lang{{position:fixed;top:14px;right:14px;z-index:9;background:rgba(20,26,37,.7);backdrop-filter:blur(12px);border:1px solid rgba(148,175,199,.2);color:#9fb0c3;border-radius:999px;padding:4px 12px;font-size:11px;cursor:pointer}}
.stat-card{{padding:20px 14px}}
.stats{{display:flex;justify-content:space-around;align-items:center;gap:6px;flex-wrap:wrap}}
.stat{{display:flex;flex-direction:column;align-items:center;gap:8px;min-width:92px}}
.ring-wrap{{position:relative;width:96px;height:96px}}
.ring{{width:96px;height:96px;transform:rotate(-90deg)}}
.ring-bg{{fill:none;stroke:rgba(148,175,199,.16);stroke-width:8}}
.ring-fg{{fill:none;stroke-width:8;stroke-linecap:round;transition:stroke-dashoffset 1.1s cubic-bezier(.22,.9,.35,1)}}
.ring-mid{{position:absolute;inset:0;display:flex;align-items:center;justify-content:center;text-align:center;font-size:12.5px;font-weight:700;line-height:1.2;padding:0 6px}}
.ring-mid .sm{{display:block;font-weight:500;color:#9fb0c3;font-size:10px}}
.big-num{{font-size:34px;font-weight:800;line-height:1;background:linear-gradient(135deg,#35d7dc,#8b7bff);-webkit-background-clip:text;background-clip:text;color:transparent;animation:pop .5s cubic-bezier(.22,.9,.35,1)}}
.stat-lbl{{font-size:11.5px;color:#9fb0c3;text-align:center}}
.stat-lbl .sm{{color:#6b7a8f;font-size:10px}}
.dev-pill{{display:flex;align-items:center;gap:7px;font-size:15px;font-weight:700;padding:9px 16px;border-radius:999px;border:1px solid rgba(148,175,199,.2);background:rgba(255,255,255,.03)}}
.dev-pill.on{{border-color:rgba(78,203,149,.5);color:#4ecb95}}
.dev-pill.off{{color:#9fb0c3}}
.dot{{width:8px;height:8px;border-radius:50%;background:#5c6b80;flex:none}}
.dev-pill.on .dot{{background:#4ecb95;box-shadow:0 0 0 rgba(78,203,149,.6);animation:pulse 1.8s infinite}}
@keyframes pulse{{0%{{box-shadow:0 0 0 0 rgba(78,203,149,.55)}}70%{{box-shadow:0 0 0 9px rgba(78,203,149,0)}}100%{{box-shadow:0 0 0 0 rgba(78,203,149,0)}}}}
@keyframes pop{{0%{{transform:scale(.7);opacity:0}}100%{{transform:scale(1);opacity:1}}}}
</style></head><body>
<div class="w">
<div class="top"><img class="moon" src="data:image/png;base64,{_LOGO_B64}" alt="Voidz">
<div><h1>Voidz</h1><div class="sub2">{esc(title)}</div></div></div>
<div class="hero"><h2 class="en">Your configs are ready</h2><h2 class="fa" hidden>کانفیگ‌های شما آماده است</h2>
<p class="en">Import the subscription into your client, or copy each config individually.</p>
<p class="fa" hidden>سابسکریپشن را وارد کلاینت کنید یا هر کانفیگ را جدا کپی کنید.</p></div>
{info_card}
<div class="card">
<h3 class="en">Subscription — all protocols</h3><h3 class="fa" hidden>سابسکریپشن — همه پروتکل‌ها</h3>
<p class="lbl en">One URL, every config, auto-updates. Add it under Subscriptions in your client.</p>
<p class="lbl fa" hidden>یک لینک برای همه کانفیگ‌ها — در بخش Subscriptions اپ وارد کنید.</p>
<div class="subu"><div class="u" id="subu">{esc(sub_url)}</div><button class="btn" onclick="cp('subu')"><span class="en">Copy</span><span class="fa" hidden>کپی</span></button></div>
<div class="fmts">
<a class="fmt" href="{esc(sb_url)}" target="_blank" rel="noopener">sing-box JSON</a>
<a class="fmt" href="{esc(cl_url)}" target="_blank" rel="noopener">Clash Meta YAML</a>
<a class="fmt" href="{esc(sub_url)}" target="_blank" rel="noopener">v2ray base64</a>
</div>
<div class="qr" style="display:block;margin-top:12px">{sub_qr}</div>
<div style="color:#5d6678;font-size:10.5px;text-align:center">Scan the subscription with your client</div>
</div>
<div class="card"><h3 class="en">Individual configs</h3><h3 class="fa" hidden>کانفیگ‌های جداگانه</h3>{cards}</div>
<p class="ft">Powered by Voidz</p>
</div>
<script>
function cp(id){{navigator.clipboard.writeText(document.getElementById(id).textContent.trim()).then(function(){{
var t=document.createElement('div');t.textContent='Copied \u2713';t.style.cssText='position:fixed;bottom:24px;left:50%;transform:translateX(-50%);background:#171b24;border:1px solid #2a3242;color:#4ecb95;padding:8px 18px;border-radius:999px;font-size:13px;z-index:99';document.body.appendChild(t);setTimeout(function(){{t.remove()}},1800)}})}}
function tg(id,btn){{var b=document.getElementById(id);var open=b.style.display!=='block';b.style.display=open?'block':'none';btn.textContent=open?'Hide':'QR'}}
requestAnimationFrame(function(){{requestAnimationFrame(function(){{
  document.querySelectorAll('.ring-fg').forEach(function(el){{el.style.strokeDashoffset=el.dataset.offset}})
}})}})
</script></body></html>"""

def _singbox_outbound(url: str) -> dict:
    """vless:// / trojan:// URI -> sing-box outbound. Shadowsocks links pass
    through parsed minimally; unsupported schemes are skipped by caller."""
    import base64 as _b64u
    from urllib.parse import urlparse, parse_qs, unquote

    u = urlparse(url)
    q = {k: v[0] for k, v in parse_qs(u.query).items()}
    tag = unquote(u.fragment) or "voidz"
    common = {"tag": tag}
    if u.scheme in ("vless", "trojan"):
        inner = {
            "server": u.hostname or "",
            "server_port": u.port or 443,
            "uuid": u.username or "" if u.scheme == "vless" else None,
            "password": u.username or "" if u.scheme == "trojan" else None,
            "tls": {
                "enabled": q.get("security") == "tls",
                "server_name": q.get("sni") or u.hostname or "",
                "utls": {"enabled": True, "fingerprint": q.get("fp", "chrome")} if q.get("fp") else None,
            },
            "transport": {
                "type": "ws",
                "path": q.get("path", "/"),
                "headers": {"Host": q.get("host") or u.hostname or ""},
            } if q.get("type") == "ws" else None,
        }
        common["type"] = u.scheme
        out = {k: v for k, v in inner.items() if v is not None}
        tls = out.get("tls") or {}
        if tls.get("utls") is None:
            tls.pop("utls", None)
        if out.get("transport") is None:
            out.pop("transport", None)
        out.update(common)
        return out
    if u.scheme == "ss":
        userinfo = u.username or ""
        pad = "=" * (-len(userinfo) % 4)
        try:
            method, password = _b64u.b64decode(userinfo + pad).decode().split(":", 1)
        except Exception:
            method, password = "aes-256-gcm", ""
        return {"type": "shadowsocks", "tag": tag, "server": u.hostname or "",
                "server_port": u.port or 443, "method": method, "password": password}
    return {"type": u.scheme, "tag": tag}


def _clash_proxy(url: str) -> dict | None:
    """vless/trojan URI -> Clash Meta proxy map (vless needs Meta)."""
    from urllib.parse import urlparse, parse_qs, unquote

    u = urlparse(url)
    q = {k: v[0] for k, v in parse_qs(u.query).items()}
    name = unquote(u.fragment) or "voidz"
    if u.scheme == "vless":
        return {"name": name, "type": "vless", "server": u.hostname or "",
                "port": u.port or 443, "uuid": u.username or "",
                "udp": True, "tls": q.get("security") == "tls",
                "servername": q.get("sni") or u.hostname or "",
                "client-fingerprint": q.get("fp", "chrome"),
                "network": "ws", "ws-opts": {"path": q.get("path", "/"),
                "headers": {"Host": q.get("host") or u.hostname or ""}}}
    if u.scheme == "trojan":
        return {"name": name, "type": "trojan", "server": u.hostname or "",
                "port": u.port or 443, "password": u.username or "",
                "udp": True, "sni": q.get("sni") or u.hostname or "",
                "client-fingerprint": q.get("fp", "chrome"),
                "network": "ws", "ws-opts": {"path": q.get("path", "/"),
                "headers": {"Host": q.get("host") or u.hostname or ""}}}
    if u.scheme == "ss":
        import base64 as _b64u

        pad = "=" * (-len(u.username or "") % 4)
        try:
            method, password = _b64u.b64decode((u.username or "") + pad).decode().split(":", 1)
        except Exception:
            return None
        return {"name": name, "type": "ss", "server": u.hostname or "",
                "port": u.port or 443, "cipher": method, "password": password}
    return None


def _clash_quote(s: str) -> str:
    return '"' + s.replace('"', '\\"') + '"'


def _clash_inline(p: dict) -> str:
    import json as _json

    return _json.dumps(p, ensure_ascii=False)


router = APIRouter(include_in_schema=False)


async def _resolve_endpoint(request: Request, token: str) -> dict | None:
    """endpoint token -> {instance_id, worker_url, status}"""
    pool = get_pool(request)
    from ..config import settings as _s
    from ..security.token_codec import decode_token

    log.info("resolve enter: token[:20]=%s", token[:20])
    instance_id = decode_token(token, _s.secret_key)
    log.info("resolve: token[:16]=%s decoded=%s", token[:16], instance_id)
    if instance_id is not None:
        row = await pool.fetchrow(
            """
            SELECT i.id, i.status,
                   (SELECT d.domain FROM domains d WHERE d.instance_id = i.id
                     AND d.is_active = TRUE AND d.kind = 'path'
                     ORDER BY d.created_at DESC LIMIT 1) AS endpoint_token,
                   (SELECT dep.node_id FROM deployments dep WHERE dep.instance_id = i.id
                     ORDER BY dep.started_at DESC LIMIT 1) AS node_id
            FROM instances i WHERE i.id = $1
            """,
            instance_id,
        )
    else:
        row = await pool.fetchrow(
            """
            SELECT i.id, i.status,
                   (SELECT d.domain FROM domains d WHERE d.instance_id = i.id
                     AND d.is_active = TRUE AND d.kind = 'path'
                     ORDER BY d.created_at DESC LIMIT 1) AS endpoint_token,
                   (SELECT dep.node_id FROM deployments dep WHERE dep.instance_id = i.id
                     ORDER BY dep.started_at DESC LIMIT 1) AS node_id
            FROM instances i
            WHERE i.id IN (SELECT instance_id FROM domains
                            WHERE kind = 'path' AND domain = $1 AND is_active = TRUE)
            """,
            token,
        )
    if row is not None and row["endpoint_token"] is None:
        row = None
    if row is None or row["status"] != "running":
        log.info("resolve MISS: decoded=%s row=%s status=%s", instance_id,
                 row is not None, row["status"] if row else None)
        return None
    from ..services.workers import worker_url_for

    return {
        "instance_id": str(row["id"]),
        "worker_url": worker_url_for(row["node_id"] or "local"),
        "upstream": f"/worker/api/instances/{row['id']}/proxy",
    }


@router.get("/i/{token}")
async def instance_status_page(token: str, request: Request):
    """Browser-friendly view of a proxy endpoint (the path itself is for
    proxy clients, not people)."""
    target = await _resolve_endpoint(request, token)
    if target is None:
        return _page(
            "Endpoint not found",
            "This endpoint doesn't exist or its instance was removed. "
            "If you recently redeployed Voidz without a persistent volume, "
            "create a new instance in the panel and copy its fresh config "
            "from the <b>Config</b> tab.",
            status=404,
        )
    return _page(
        "This endpoint is live",
        "This address is the private transport path for your proxy client — "
        "there is no web page here. Open the Voidz panel, choose your "
        "instance, open the <b>Config</b> tab and copy the "
        "<code>vless://</code> link into your client (v2rayNG, NekoBox, "
        "Streisand, …).",
    )


@router.post("/i/{token}/api/qr")
async def instance_qr_public(token: str, request: Request):
    """QR (SVG) for the subscription page — authorized by the endpoint token."""
    import io

    import qrcode
    import qrcode.image.svg
    from fastapi.responses import Response as _Response

    target = await _resolve_endpoint(request, token)
    if target is None:
        raise HTTPException(status_code=404, detail="unknown endpoint")
    body = await request.json()
    text = str(body.get("text") or "")[:4096]
    if not text:
        raise HTTPException(status_code=400, detail="text required")
    img = qrcode.make(text, image_factory=qrcode.image.svg.SvgPathImage, box_size=12, border=2)
    buf = io.BytesIO()
    img.save(buf)
    return _Response(content=buf.getvalue(), media_type="image/svg+xml")


@router.get("/i/{token}/sub")
async def instance_subscription(token: str, request: Request):
    """Subscription: ALL protocols of this instance. Auth = endpoint token.
    Formats via ?fmt=: singbox | clash | (default) base64 v2ray list.
    Content host: ?host=, panel-announced host, or request host."""
    import base64 as _b64

    import httpx as _httpx

    from ..config import settings as _settings

    fmt = (request.query_params.get("fmt") or "").strip().lower()

    target = await _resolve_endpoint(request, token)
    if target is None:
        return _page(
            "Endpoint not found",
            "This subscription doesn't exist or its instance was removed. "
            "Create a new instance in the Voidz panel and copy its "
            "subscription URL from the Config tab.",
            status=404,
        )
    pool = get_pool(request)
    inst = await pool.fetchrow(
        "SELECT name, public_host, status FROM instances WHERE id = $1", target["instance_id"]
    )
    if inst is None or inst["status"] != "running":
        return _page("Instance not running",
                     "The subscription will work once the instance is running.", status=503)
    host = (request.query_params.get("host")
            or inst["public_host"]
            or (request.headers.get("x-forwarded-host") or "").split(",")[0].strip()
            or request.headers.get("host") or "").split(":")[0]
    if not host:
        return _page("Missing host", "Append ?host=<your-domain> to this URL.", status=400)
    try:
        async with _httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                f"{target['worker_url'].rstrip('/')}{target['upstream']}/core/api/share",
                json={"host": host, "path_prefix": f"/i/{token}", "uuids": []},
                headers={"Authorization": f"Bearer {_settings.worker_token}",
                         "Content-Type": "application/json"},
            )
            resp.raise_for_status()
            configs = [c for c in resp.json().get("links", []) if c.get("share_url")]
            links = [c["share_url"] for c in configs]
    except Exception as exc:
        return _page("Unavailable", f"Could not read the instance configs: {str(exc)[:160]}",
                     status=502)
    title = f"Voidz \u00b7 {inst['name']}"
    from fastapi.responses import Response as _Response

    # ── Browser detection: HTML page for people, raw payload for clients ──
    # DEFAULT IS RAW: proxy clients (v2rayN, v2rayNG, Happ, …) may send
    # browser-like or empty User-Agents, so UA guessing alone would feed them
    # the HTML page and break imports. HTML is served only when the request
    # looks like a real web browser: Mozilla-style UA *and* "Accept:
    # text/html" (browsers always send both; proxy clients never do).
    # Explicit ?fmt= always forces raw data.
    ua = (request.headers.get("user-agent") or "").lower()
    accept = (request.headers.get("accept") or "").lower()
    looks_like_browser = "mozilla" in ua and "text/html" in accept

    if looks_like_browser and not fmt:
        from fastapi.responses import HTMLResponse

        return HTMLResponse(_sub_html_page(title, configs, host, f"/i/{token}/sub",
                                           qr_path=f"/i/{token}/api/qr"))

    def _headers(extra: dict | None = None) -> dict:
        h = {
            "profile-title": "base64:" + _b64.b64encode(title.encode()).decode(),
            "subscription-userinfo": "upload=0; download=0; total=0; expire=0",
            "profile-update-interval": "24",
            "profile-web-page-url": f"{request.url.scheme}://{request.headers.get('host', host)}",
        }
        if extra:
            h.update(extra)
        return h

    # Format negotiation:
    #   ?fmt=singbox  -> sing-box JSON (Outbounds)
    #   ?fmt=clash    -> Clash YAML (proxies)
    #   default       -> base64 v2ray list (v2rayNG, NekoBox, Streisand)
    if fmt in ("singbox", "sing-box", "sb"):
        import json as _json

        outbounds = [_singbox_outbound(u) for u in links]
        payload = _json.dumps({"outbounds": outbounds}, ensure_ascii=False, indent=2)
        return _Response(content=payload, media_type="application/json",
                         headers=_headers({"subscription-userinfo": "upload=0; download=0; total=0; expire=0"}))

    if fmt in ("clash", "clash-meta", "yaml"):
        proxies = [_clash_proxy(u) for u in links]
        proxies = [p for p in proxies if p]
        names = [p["name"] for p in proxies]
        payload = (
            "port: 7890\nsocks-port: 7891\nallow-lan: false\nmode: rule\nlog-level: warning\n"
            "proxies:\n"
            + "\n".join("  - " + _clash_inline(p) for p in proxies)
            + "\nproxy-groups:\n  - name: Voidz\n    type: select\n    proxies:\n"
            + "".join(f"      - {_clash_quote(n)}\n" for n in names)
            + "rules:\n  - MATCH,Voidz\n"
        )
        return _Response(content=payload, media_type="text/yaml", headers=_headers())

    body = _b64.b64encode("\n".join(links).encode()).decode()
    return _Response(content=body, media_type="text/plain", headers=_headers())


@router.get("/sub/{sub_token}")
async def plan_subscription(sub_token: str, request: Request):
    """Multi-region subscription: one config per region in the customer's
    plan, sharing one pooled quota/expiry enforced by services/quota.py.
    Same UA-sniffing / ?fmt= negotiation as /i/{token}/sub."""
    import base64 as _b64
    from datetime import datetime, timezone

    from ..services import workers as worker_svc
    from ..services.workers import worker_url_for

    fmt = (request.query_params.get("fmt") or "").strip().lower()
    pool = get_pool(request)
    cust = await pool.fetchrow(
        "SELECT c.*, p.name AS plan_name FROM customers c JOIN plans p ON p.id = c.plan_id "
        "WHERE c.sub_token = $1",
        sub_token,
    )
    if cust is None or not cust["active"]:
        return _page(
            "Endpoint not found",
            "This subscription doesn't exist or has been revoked. Contact "
            "whoever gave you this link for a new one.",
            status=404,
        )
    now = datetime.now(timezone.utc)
    if cust["expires_at"] and cust["expires_at"] < now:
        return _page("Subscription expired",
                     "This subscription's time has run out. Contact whoever "
                     "gave you this link to renew it.", status=403)
    if cust["limit_bytes"] and cust["used_bytes_cached"] >= cust["limit_bytes"]:
        return _page("Data limit reached",
                     "This subscription has used all of its allotted data. "
                     "Contact whoever gave you this link to top it up.", status=403)

    pi_rows = await pool.fetch(
        "SELECT pi.instance_id, pi.region_label, i.status, "
        "(SELECT dep.node_id FROM deployments dep WHERE dep.instance_id = i.id "
        " ORDER BY dep.started_at DESC LIMIT 1) AS node_id, "
        "(SELECT d.domain FROM domains d WHERE d.instance_id = i.id "
        " AND d.kind = 'path' AND d.is_active = TRUE ORDER BY d.created_at DESC LIMIT 1) AS endpoint_token "
        "FROM plan_instances pi JOIN instances i ON i.id = pi.instance_id "
        "WHERE pi.plan_id = $1 ORDER BY pi.position",
        cust["plan_id"],
    )
    host = (request.query_params.get("host")
            or (request.headers.get("x-forwarded-host") or "").split(",")[0].strip()
            or request.headers.get("host") or "").split(":")[0]
    if not host:
        return _page("Missing host", "Append ?host=<your-domain> to this URL.", status=400)

    from ..services.quota import _link_uuid

    plan_protocols_str = await pool.fetchval("SELECT protocols FROM plans WHERE id = $1", cust["plan_id"])
    plan_protocols = [p for p in (plan_protocols_str or "").split(",") if p]
    wanted_uuids = [_link_uuid(cust["cred_uuid"], proto) for proto in plan_protocols]

    configs = []
    for pi in pi_rows:
        if pi["status"] != "running" or not pi["endpoint_token"]:
            continue
        worker_url = worker_url_for(pi["node_id"] or "local")
        try:
            data = await worker_svc.worker_call(
                worker_url, "POST",
                f"/worker/api/instances/{pi['instance_id']}/proxy/core/api/share",
                {"host": host, "path_prefix": f"/i/{pi['endpoint_token']}",
                 "uuids": wanted_uuids},
            )
        except worker_svc.WorkerError:
            continue
        for c in data.get("links", []):
            if c.get("share_url"):
                c["region"] = pi["region_label"]
                configs.append(c)

    if not configs:
        return _page("No locations available right now",
                     "None of this subscription's locations are currently "
                     "reachable. Try again shortly.", status=503)

    links = [c["share_url"] for c in configs]
    title = f"Voidz · {cust['name']}"

    ua = (request.headers.get("user-agent") or "").lower()
    accept = (request.headers.get("accept") or "").lower()
    looks_like_browser = "mozilla" in ua and "text/html" in accept
    if looks_like_browser and not fmt:
        from fastapi.responses import HTMLResponse

        device_ips: set[str] = set()
        wanted_str = ",".join(wanted_uuids)
        for pi in pi_rows:
            if pi["status"] != "running":
                continue
            worker_url = worker_url_for(pi["node_id"] or "local")
            try:
                conn_data = await worker_svc.worker_call(
                    worker_url, "GET",
                    f"/worker/api/instances/{pi['instance_id']}/proxy/core/api/connections?uuids={wanted_str}",
                )
            except worker_svc.WorkerError:
                continue
            for conn in conn_data.get("connections", []):
                if conn.get("ip"):
                    device_ips.add(conn["ip"])

        limit_bytes = int(cust["limit_bytes"] or 0)
        used_bytes = int(cust["used_bytes_cached"] or 0)
        import math

        no_expiry = cust["expires_at"] is None
        days_left = days_total = None
        if not no_expiry:
            days_left = max(0, math.ceil((cust["expires_at"] - now).total_seconds() / 86400))
            days_total = max(1, math.ceil((cust["expires_at"] - cust["created_at"]).total_seconds() / 86400))
        info = {
            "used_gb": used_bytes / (1024 ** 3),
            "total_gb": (limit_bytes / (1024 ** 3)) if limit_bytes else None,
            "pct": (used_bytes / limit_bytes * 100) if limit_bytes else 0,
            "days_left": days_left,
            "days_total": days_total,
            "no_expiry": no_expiry,
            "online_count": len(device_ips),
            "max_devices": int(cust["max_devices"] or 0),
        }
        return HTMLResponse(_sub_html_page(title, configs, host, f"/sub/{sub_token}", info=info))

    def _headers(extra: dict | None = None) -> dict:
        expire_ts = int(cust["expires_at"].timestamp()) if cust["expires_at"] else 0
        h = {
            "profile-title": "base64:" + _b64.b64encode(title.encode()).decode(),
            "subscription-userinfo": (
                f"upload=0; download={int(cust['used_bytes_cached'])}; "
                f"total={int(cust['limit_bytes'])}; expire={expire_ts}"
            ),
            "profile-update-interval": "6",
            "profile-web-page-url": f"{request.url.scheme}://{request.headers.get('host', host)}",
        }
        if extra:
            h.update(extra)
        return h

    from fastapi.responses import Response as _Response

    if fmt in ("singbox", "sing-box", "sb"):
        import json as _json

        outbounds = [_singbox_outbound(u) for u in links]
        payload = _json.dumps({"outbounds": outbounds}, ensure_ascii=False, indent=2)
        return _Response(content=payload, media_type="application/json", headers=_headers())

    if fmt in ("clash", "clash-meta", "yaml"):
        proxies = [_clash_proxy(u) for u in links]
        proxies = [p for p in proxies if p]
        names = [p["name"] for p in proxies]
        payload = (
            "port: 7890\nsocks-port: 7891\nallow-lan: false\nmode: rule\nlog-level: warning\n"
            "proxies:\n"
            + "\n".join("  - " + _clash_inline(p) for p in proxies)
            + "\nproxy-groups:\n  - name: Voidz\n    type: select\n    proxies:\n"
            + "".join(f"      - {_clash_quote(n)}\n" for n in names)
            + "rules:\n  - MATCH,Voidz\n"
        )
        return _Response(content=payload, media_type="text/yaml", headers=_headers())

    body = _b64.b64encode("\n".join(links).encode()).decode()
    return _Response(content=body, media_type="text/plain", headers=_headers())


@router.api_route("/i/{token}/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"])
async def instance_http_gateway(token: str, path: str, request: Request):
    target = await _resolve_endpoint(request, token)
    if target is None:
        return _page(
            "Endpoint not found",
            "This endpoint doesn't exist or its instance is not running. "
            "Check the panel — if the instance is Running, copy the fresh "
            "config from its <b>Config</b> tab.",
            status=404,
        )

    worker_url = target["worker_url"].rstrip("/")
    url = f"{worker_url}{target['upstream']}/{path}"
    if request.url.query:
        url += f"?{request.url.query}"
    headers = [(k, v) for k, v in request.headers.items() if k.lower() not in HOP_BY_HOP]
    headers.append(("X-Voidz-Endpoint", token))
    from ..config import settings as _cfg

    headers.append(("Authorization", f"Bearer {_cfg.worker_token}"))

    client = httpx.AsyncClient(timeout=None)
    try:
        if request.method in ("GET", "HEAD", "OPTIONS"):
            upstream_req = client.build_request(
                request.method, url, headers=headers, params=None,
            )
            upstream_resp = await client.send(upstream_req, stream=True)
            return StreamingResponse(
                upstream_resp.aiter_raw(),
                status_code=upstream_resp.status_code,
                headers={k: v for k, v in upstream_resp.headers.items()
                         if k.lower() not in HOP_BY_HOP},
                background=_close_client(client, upstream_resp),
            )

        body = await request.body()
        upstream_resp = await client.request(request.method, url, headers=headers, content=body)
        return Response(
            content=upstream_resp.content,
            status_code=upstream_resp.status_code,
            headers={k: v for k, v in upstream_resp.headers.items()
                     if k.lower() not in HOP_BY_HOP},
        )
    except httpx.HTTPError:
        raise HTTPException(status_code=502, detail="instance upstream unavailable")


def _close_client(client: httpx.AsyncClient, resp):
    from starlette.background import BackgroundTask

    async def _cleanup() -> None:
        await resp.aclose()
        await client.aclose()

    return BackgroundTask(_cleanup)


@router.websocket("/i/{token}/{path:path}")
async def instance_ws_gateway(ws: WebSocket, token: str, path: str):
    """Frame-level WebSocket relay into the instance's Voidz Core.

    Accept the client up front (so failures produce proper close codes, not
    Starlette's HTTP 403 rejection), then open the upstream through the
    worker's ws-proxy and pump frames in both directions.
    """
    await ws.accept()
    try:
        target = await _resolve_endpoint(ws, token)
    except Exception as _exc:
        import traceback as _tb

        log.error("WS resolve failed: %s | %s", _exc, _tb.format_exc()[-400:])
        target = None
    if target is None:
        await ws.close(code=1008, reason="unknown or inactive instance endpoint")
        return

    # Build the upstream ws URL through the worker's websocket proxy
    # (separate route from the HTTP /proxy path).
    worker_ws = target["worker_url"].replace("http://", "ws://").replace("https://", "wss://").rstrip("/")
    from ..config import settings as _settings

    upstream_url = (
        f"{worker_ws}/worker/api/instances/{target['instance_id']}/ws-proxy/{path}"
        f"?token={_settings.worker_token}"
    )

    # Forward selected client headers so Core sees the real client IP etc.
    client_headers = {}
    for key in ("x-forwarded-for", "x-real-ip", "user-agent"):
        val = ws.headers.get(key)
        if val:
            client_headers[key] = val
    client_headers["x-voidz-endpoint"] = token

    try:
        async with websockets.connect(
            upstream_url,
            additional_headers=client_headers,  # type: ignore[arg-type]
            max_size=None,
            ping_interval=20,
            ping_timeout=20,
            close_timeout=5,
        ) as upstream:
            async def client_to_upstream() -> None:
                try:
                    while True:
                        msg = await ws.receive()
                        if msg["type"] == "websocket.disconnect":
                            return
                        data = msg.get("bytes")
                        if data is not None:
                            await upstream.send(data)
                        else:
                            text = msg.get("text")
                            if text is not None:
                                await upstream.send(text)
                except (WebSocketDisconnect, Exception):
                    return

            async def upstream_to_client() -> None:
                try:
                    async for message in upstream:
                        if isinstance(message, (bytes, bytearray)):
                            await ws.send_bytes(bytes(message))
                        else:
                            await ws.send_text(message)
                except Exception:
                    return

            done, pending = await asyncio.wait(
                {
                    asyncio.create_task(client_to_upstream()),
                    asyncio.create_task(upstream_to_client()),
                },
                return_when=asyncio.FIRST_COMPLETED,
            )
            for task in pending:
                task.cancel()
    except (websockets.exceptions.WebSocketException, OSError) as exc:
        log.info("gateway ws upstream failed: %s", type(exc).__name__)
        await ws.close(code=1014, reason="upstream unavailable")
        return
    finally:
        try:
            await ws.close()
        except Exception:
            pass
