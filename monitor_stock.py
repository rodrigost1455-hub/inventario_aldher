"""
=============================================================
  BOT MONITOR DE STOCK v2 — Con Dashboard Web
  Proveedor: https://vauxoo-psadurango.odoo.com/shop
  Dashboard: Tu URL de Vercel
  Sincronización: JSONBin.io
=============================================================
  INSTALACIÓN:
    pip install requests beautifulsoup4 twilio schedule
=============================================================
"""

import re
import requests
from bs4 import BeautifulSoup
from twilio.rest import Client
import schedule
import time
import json
import sys
from datetime import datetime

# =============================================================
#  ⚙️  CONFIGURACIÓN — GENERADA DESDE EL DASHBOARD
#  (O llénala manualmente si no usas el dashboard)
# =============================================================

TWILIO_ACCOUNT_SID = "AC429fa88153b36d1fdb50a5842baa66ff"   # Tu Account SID
TWILIO_AUTH_TOKEN  = "5f62f864a81dce89da7eeb317e6ce069"     # Tu Auth Token
TWILIO_WA_FROM     = "whatsapp:+17125825720"                # Número Twilio (sandbox)
TU_WHATSAPP        = "whatsapp:+526182781423"              # Tu WhatsApp Business (con código de país)

JSONBIN_BIN_ID     = "TU_BIN_ID"
JSONBIN_API_KEY    = "TU_API_KEY"

PRODUCTOS = [
    {"nombre": "USB 16GB Stylos ST100", "sku": "STMUSB2B", "stock_minimo": 50},
    # Agrega más productos aquí o usa el Dashboard para configurarlos
]

HORA_REVISION_1 = "08:00"
HORA_REVISION_2 = "13:00"
HORA_REVISION_3 = "18:00"

# =============================================================
#  NO MODIFICAR ABAJO DE ESTA LÍNEA
# =============================================================

URL_TIENDA   = "https://vauxoo-psadurango.odoo.com/shop"
JSONBIN_URL  = f"https://api.jsonbin.io/v3/b/{JSONBIN_BIN_ID}"
HEADERS_JSON = {
    "Content-Type": "application/json",
    "X-Master-Key": JSONBIN_API_KEY
}

# Estado en memoria del día
estado_global = {
    "productos": [],
    "ultima_revision": "—",
    "revisiones_hoy": 0,
    "alertas": []
}


# ─── SCRAPER ────────────────────────────────────────────────

def obtener_info_producto(sku):
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    try:
        url = f"{URL_TIENDA}?search={sku}"
        res = requests.get(url, headers=headers, timeout=15)
        res.raise_for_status()
        soup = BeautifulSoup(res.text, "html.parser")
        page_text = soup.get_text()
        resultado = {"sku": sku, "encontrado": False, "stock": 0, "precio": "N/A"}

        if sku.upper() in page_text.upper():
            resultado["encontrado"] = True
            disp = soup.find(string=lambda t: t and "Disponible" in t)
            if disp:
                nums = re.findall(r'\d+', str(disp))
                if nums:
                    resultado["stock"] = int(nums[0])
            precio_el = soup.find("span", class_="oe_price") or \
                        soup.find("span", class_="monetary_field")
            if precio_el:
                resultado["precio"] = precio_el.get_text(strip=True)

        return resultado

    except requests.exceptions.ConnectionError:
        return {"sku": sku, "error": "Sin conexión", "encontrado": False}
    except requests.exceptions.Timeout:
        return {"sku": sku, "error": "Timeout", "encontrado": False}
    except Exception as e:
        return {"sku": sku, "error": str(e), "encontrado": False}


# ─── WHATSAPP ───────────────────────────────────────────────

def enviar_whatsapp(mensaje):
    try:
        client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        msg = client.messages.create(body=mensaje, from_=TWILIO_WA_FROM, to=TU_WHATSAPP)
        print(f"  ✅ WhatsApp enviado ({msg.sid})")
    except Exception as e:
        print(f"  ❌ Error WhatsApp: {e}")


# ─── JSONBIN SYNC ────────────────────────────────────────────

def sync_dashboard():
    """Sube el estado actual al dashboard vía JSONBin"""
    if not JSONBIN_BIN_ID or JSONBIN_BIN_ID == "TU_BIN_ID":
        return  # Sin JSONBin configurado, saltar silenciosamente
    try:
        requests.put(JSONBIN_URL, headers=HEADERS_JSON,
                     data=json.dumps(estado_global), timeout=10)
        print("  📊 Dashboard sincronizado")
    except Exception as e:
        print(f"  ⚠️  No se pudo sincronizar dashboard: {e}")


def registrar_alerta(tipo, producto, mensaje):
    """Agrega una alerta al log del dashboard"""
    hora = datetime.now().strftime("%d/%m %H:%M")
    alerta = {"tipo": tipo, "producto": producto, "mensaje": mensaje, "hora": hora}
    estado_global["alertas"].append(alerta)
    # Mantener solo las últimas 50 alertas
    if len(estado_global["alertas"]) > 50:
        estado_global["alertas"] = estado_global["alertas"][-50:]


# ─── REVISIÓN PRINCIPAL ──────────────────────────────────────

def revisar_stock():
    ahora = datetime.now().strftime("%d/%m/%Y %H:%M")
    hora_actual = datetime.now().strftime("%H:%M")
    print(f"\n{'═'*52}")
    print(f"  🔍 Revisión iniciada: {ahora}")
    print(f"{'═'*52}")

    fecha_actual = datetime.now().strftime("%d/%m/%Y")
    if estado_global.get("fecha_actual") != fecha_actual:
        estado_global["revisiones_hoy"] = 0
        estado_global["fecha_actual"] = fecha_actual

    estado_global["ultima_revision"] = ahora
    estado_global["revisiones_hoy"] += 1
    estado_global["productos"] = []

    alertas_msg = []

    for prod in PRODUCTOS:
        nombre = prod["nombre"]
        sku    = prod["sku"]
        minimo = prod["stock_minimo"]

        print(f"\n  📦 {nombre} ({sku})...")
        info = obtener_info_producto(sku)

        if "error" in info:
            msg = f"Error al revisar: {info['error']}"
            print(f"  ⚠️  {msg}")
            estado_global["productos"].append({
                "nombre": nombre, "sku": sku,
                "stock": None, "estado": "danger",
                "mensaje": msg
            })
            registrar_alerta("danger", nombre, msg)
            alertas_msg.append(f"⚠️ ERROR — {nombre}: {info['error']}")
            continue

        if not info["encontrado"] or info["stock"] == 0:
            print(f"  🚨 SIN STOCK — no aparece en tienda o stock es 0")
            estado_global["productos"].append({
                "nombre": nombre, "sku": sku,
                "stock": 0, "estado": "danger",
                "mensaje": "No aparece en tienda (sin stock)"
            })
            registrar_alerta("danger", nombre, "Sin stock — no aparece en tienda")
            alertas_msg.append(f"🚨 SIN STOCK — {nombre} ({sku})")

        elif info["stock"] < minimo:
            print(f"  ⚠️  BAJO — {info['stock']} uds (mínimo: {minimo})")
            estado_global["productos"].append({
                "nombre": nombre, "sku": sku,
                "stock": info["stock"], "estado": "warn",
                "mensaje": f"Stock bajo: {info['stock']} uds (mínimo: {minimo})"
            })
            registrar_alerta("warn", nombre, f"Stock bajo: {info['stock']} uds")
            alertas_msg.append(f"⚠️ STOCK BAJO — {nombre}: {info['stock']} uds")

        else:
            print(f"  ✅ OK — {info['stock']} uds | {info['precio']}")
            estado_global["productos"].append({
                "nombre": nombre, "sku": sku,
                "stock": info["stock"], "estado": "ok",
                "mensaje": f"OK — {info['stock']} uds disponibles"
            })

    # Enviar WhatsApp si hay alertas
    if alertas_msg:
        wa_msg  = f"🤖 *ALERTA DE STOCK*\n📅 {ahora}\n\n"
        wa_msg += "\n".join(alertas_msg)
        wa_msg += f"\n\n🔗 {URL_TIENDA}"
        enviar_whatsapp(wa_msg)

    # Reporte matutino si todo OK
    if not alertas_msg and hora_actual == HORA_REVISION_1:
        wa_msg = f"✅ *Reporte Matutino*\n📅 {ahora}\n\nTodo en orden:\n"
        for p in estado_global["productos"]:
            wa_msg += f"• {p['nombre']}: {p['stock']} uds\n"
        enviar_whatsapp(wa_msg)

    # Sincronizar con dashboard
    sync_dashboard()
    print(f"\n  {'─'*48}")
    print(f"  Revisión completa. Alertas enviadas: {len(alertas_msg)}")


# ─── INICIO ─────────────────────────────────────────────────

if __name__ == "__main__":
    modo_test = "--test" in sys.argv

    print("""
╔══════════════════════════════════════════════════╗
║  🤖 STOCKBOT v2 — Monitor de Stock + Dashboard   ║
╚══════════════════════════════════════════════════╝
    """)

    if modo_test:
        print("🧪 MODO PRUEBA — Ejecutando revisión única\n")
        revisar_stock()
        print("\n✅ Prueba completada.")
        sys.exit(0)

    # Revisión inmediata al arrancar
    revisar_stock()

    # Programar revisiones
    schedule.every().day.at(HORA_REVISION_1).do(revisar_stock)
    schedule.every().day.at(HORA_REVISION_2).do(revisar_stock)
    schedule.every().day.at(HORA_REVISION_3).do(revisar_stock)

    print(f"\n  ⏰ Revisiones: {HORA_REVISION_1} | {HORA_REVISION_2} | {HORA_REVISION_3}")
    print("  💡 Presiona Ctrl+C para detener\n")

    while True:
        schedule.run_pending()
        time.sleep(60)
