"""Diario de trades: cruza el log del bot con el export de BingX.

Sin claves ni API: usa solo dos archivos locales.
  - logs/live_trading_log.txt (líneas "[ORDEN REAL ENVIADA] ... -> orderId=<id>")
  - export de BingX "Perpetual Futures" (CSV; hora Asia/Shanghai = UTC+8)

Uso:
  python diario_trades.py --log logs/live_trading_log.txt \
      --export "USDⓢ_M_Perpetual_Futures.csv" --salida results/diario

Genera <salida>_trades.csv (un trade por fila) y <salida>_resumen.txt
(por estrategia, símbolo, ventana horaria y apalancamiento). Los trades cuya
orden de entrada no está en el log (manuales u otros sistemas) quedan como
estrategia "sin_match".
"""
import argparse
import csv
import re
from collections import defaultdict
from datetime import datetime, timedelta, timezone

RE_ORDEN = re.compile(
    r"\[ORDEN REAL ENVIADA\] (\S+) (\S+) (buy|sell) \S+ size=\S+ "
    r"entry~=(\S+) SL=(\S+) TP=\S+ -> orderId=(\d+)"
)
EPS = 1e-9


def parsear_log(lineas):
    """-> {orderId: {symbol, strat, side, entry, sl}}"""
    out = {}
    for ln in lineas:
        m = RE_ORDEN.search(ln)
        if not m:
            continue
        sym, strat, side, entry, sl, oid = m.groups()
        try:
            e, s = float(entry), float(sl)
        except ValueError:
            e = s = None
        out[oid] = {
            "pair": sym.replace("/USDT:USDT", "-USDT"),
            "strat": strat,
            "side": side,
            "entry": e,
            "sl": s,
        }
    return out


def _utc(txt):
    return (datetime.strptime(txt, "%Y-%m-%d %H:%M:%S") - timedelta(hours=8)).replace(
        tzinfo=timezone.utc
    )


def leer_export(filas):
    """filas: iterable de dicts del CSV. -> lista de fills ordenada por hora."""
    fills = []
    for r in filas:
        tipo = r["Type"].strip()
        if not tipo.startswith(("Open", "Close")):
            continue
        fills.append({
            "oid": r["Order No."].strip(),
            "t": _utc(r["Time(Asia/Shanghai)"].strip()),
            "pair": r["Pair"].strip(),
            "abre": tipo.startswith("Open"),
            "lado": tipo.split()[1].lower(),
            "lev": r["Leverage"].strip().upper(),
            "px": float(r["DealPrice"]),
            "qty": float(r["Quantity"]),
            "fee": float(r["Fee"] or 0),
            "pnl": float(r["Realized PNL"] or 0),
            "tipo_orden": r.get("Order Type", "").strip(),
        })
    fills.sort(key=lambda f: (f["pair"], f["t"], not f["abre"]))
    return fills


def armar_trades(fills, ordenes):
    """Un trade = desde que la posición de un par/lado abre hasta que vuelve a 0."""
    trades = []
    abiertas = {}  # (pair, lado) -> trade en curso
    for f in fills:
        k = (f["pair"], f["lado"])
        t = abiertas.get(k)
        if f["abre"]:
            if t is None:
                t = {
                    "pair": f["pair"], "lado": f["lado"], "lev": f["lev"],
                    "t_entrada": f["t"], "oid": f["oid"], "qty_abierta": 0.0,
                    "qty_cerrada": 0.0, "notional": 0.0, "pnl": 0.0, "fees": 0.0,
                    "t_salida": None, "tipo_orden": f["tipo_orden"],
                }
                abiertas[k] = t
            t["qty_abierta"] += f["qty"]
            t["notional"] += f["qty"] * f["px"]
        else:
            if t is None:
                continue  # cierre sin apertura en el export (posición previa)
            t["qty_cerrada"] += f["qty"]
            t["t_salida"] = f["t"]
        t["pnl"] += f["pnl"]
        t["fees"] += f["fee"]
        if not f["abre"] and t["qty_cerrada"] >= t["qty_abierta"] - EPS:
            trades.append(abiertas.pop(k))
    for t in abiertas.values():
        t["abierta"] = True
        trades.append(t)
    out = []
    for t in trades:
        o = ordenes.get(t["oid"])
        entry_px = t["notional"] / t["qty_abierta"] if t["qty_abierta"] else 0.0
        neto = t["pnl"] + t["fees"]
        r = None
        if o and o["sl"] is not None and o["entry"] is not None:
            riesgo = t["qty_abierta"] * abs(o["entry"] - o["sl"])
            r = neto / riesgo if riesgo > 0 else None
        out.append({
            "t_entrada_utc": t["t_entrada"].strftime("%Y-%m-%d %H:%M:%S"),
            "t_salida_utc": t["t_salida"].strftime("%Y-%m-%d %H:%M:%S") if t["t_salida"] else "",
            "estado": "abierta" if t.get("abierta") else "cerrada",
            "pair": t["pair"],
            "estrategia": o["strat"] if o else "sin_match",
            "lado": t["lado"],
            "apalancamiento": t["lev"],
            "ventana": ventana(t["t_entrada"]),
            "precio_entrada": round(entry_px, 8),
            "cantidad": t["qty_abierta"],
            "pnl_bruto": round(t["pnl"], 6),
            "fees": round(t["fees"], 6),
            "neto": round(neto, 6),
            "R": round(r, 3) if r is not None else "",
            "order_no": t["oid"],
            "tipo_orden": t["tipo_orden"],
        })
    out.sort(key=lambda x: x["t_entrada_utc"])
    return out


def ventana(ts):
    """Ventana UTC de la entrada (las mismas del bot)."""
    m = ts.hour * 60 + ts.minute
    if 13 * 60 + 30 <= m < 16 * 60:
        return "NY"
    if 21 * 60 <= m < 24 * 60:
        return "noche"
    if 8 * 60 <= m < 13 * 60 + 30:
        return "londres"
    return "otra"


def resumir(trades, campo):
    g = defaultdict(list)
    for t in trades:
        if t["estado"] == "cerrada":
            g[t[campo]].append(t)
    filas = []
    for k, ts in sorted(g.items()):
        netos = [t["neto"] for t in ts]
        gan = sum(x for x in netos if x > 0)
        per = -sum(x for x in netos if x < 0)
        rs = [t["R"] for t in ts if t["R"] != ""]
        filas.append((
            k, len(ts), sum(netos),
            (gan / per) if per > 0 else float("inf"),
            sum(1 for x in netos if x > 0) / len(ts),
            (sum(rs) / len(rs)) if rs else None,
        ))
    return filas


def texto_resumen(trades):
    cerr = [t for t in trades if t["estado"] == "cerrada"]
    lin = [f"Trades cerrados: {len(cerr)} | abiertos: {len(trades) - len(cerr)} | "
           f"neto total: {sum(t['neto'] for t in cerr):.2f} USDT", ""]
    for campo in ("estrategia", "pair", "ventana", "apalancamiento"):
        lin.append(f"== Por {campo} ==")
        lin.append(f"{'':<28}{'n':>5}{'neto':>10}{'PF':>7}{'win%':>7}{'R medio':>9}")
        for k, n, neto, pf, w, r in resumir(trades, campo):
            pf_t = "inf" if pf == float("inf") else f"{pf:.2f}"
            r_t = "-" if r is None else f"{r:.2f}"
            lin.append(f"{k:<28}{n:>5}{neto:>10.2f}{pf_t:>7}{w*100:>6.0f}%{r_t:>9}")
        lin.append("")
    lin.append("Nota: R solo existe para trades con match en el log (usa SL del log). "
               "'sin_match' = manuales u otros sistemas en la misma cuenta.")
    return "\n".join(lin)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--log", required=True)
    ap.add_argument("--export", required=True)
    ap.add_argument("--salida", default="results/diario")
    a = ap.parse_args(argv)
    with open(a.log, encoding="utf-8", errors="replace") as f:
        ordenes = parsear_log(f)
    with open(a.export, encoding="utf-8-sig", newline="") as f:
        fills = leer_export(csv.DictReader(f))
    trades = armar_trades(fills, ordenes)
    import os
    os.makedirs(os.path.dirname(a.salida) or ".", exist_ok=True)
    if trades:
        with open(a.salida + "_trades.csv", "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(trades[0].keys()))
            w.writeheader()
            w.writerows(trades)
    txt = texto_resumen(trades)
    with open(a.salida + "_resumen.txt", "w", encoding="utf-8") as f:
        f.write(txt + "\n")
    print(txt)


if __name__ == "__main__":
    main()
