from fastapi import FastAPI, Form, Request
from fastapi.responses import Response,PlainTextResponse
from twilio.rest import Client
from twilio.twiml.messaging_response import MessagingResponse
from twilio.request_validator import RequestValidator
import uvicorn

from config import config
from database import get_history, save_messages, is_human_mode, set_human_mode
from ai_engine import get_ai_response
from sheets import registrar_pedido

app = FastAPI(title="WhatsApp AI Bot")
twilio_client = Client(config.TWILIO_SID, config.TWILIO_TOKEN)


def send_whatsapp(to: str, body: str):
    """Envia un mensaje de WhatsApp via Twilio"""
    twilio_client.messages.create(
        body=body,
        from_="whatsapp:" + config.TWILIO_NUMBER,
        to=to  # ya viene como "whatsapp:+57..."
    )


@app.get("/health")
def health_check():
    """Endpoint de verificacion - Railway lo usa para saber si el bot vive"""
    return {"status": "ok", "bot": config.EMPRESA}


@app.post("/webhook")
async def webhook(From: str = Form(...), Body: str = Form(...)):
    phone = From
    text = Body.strip()
    print("[MSG] " + phone + ": " + text)

    # Comando vendedor: reactivar bot para un cliente
    if text.startswith("/bot-on"):
        partes = text.split(" ")
        if len(partes) == 2:
            numero = partes[1].strip()
            if not numero.startswith("whatsapp:"):
                numero = "whatsapp:" + numero
            set_human_mode(numero, False)
            reply = "Bot reactivado para " + numero
            send_whatsapp(phone, reply)
            return PlainTextResponse("", status_code=200)

    # Comando vendedor: desactivar bot para un cliente
    if text.startswith("/bot-off"):
        partes = text.split(" ")
        if len(partes) == 2:
            numero = partes[1].strip()
            if not numero.startswith("whatsapp:"):
                numero = "whatsapp:" + numero
            set_human_mode(numero, True)
            reply = "Bot desactivado para " + numero
            send_whatsapp(phone, reply)
            return PlainTextResponse("", status_code=200)

    if is_human_mode(phone):
        print("[HUMANO] " + phone + " bot desactivado")
        return PlainTextResponse("", status_code=200)

    triggers = ["humano", "asesor", "persona", "agente"]
    if any(w in text.lower() for w in triggers):
        set_human_mode(phone, True)
        reply = "Un asesor humano se comunicara contigo pronto. Horario: Lun-Sab 9am-7pm."
        send_whatsapp(phone, reply)
        save_messages(phone, text, reply)
        return PlainTextResponse("", status_code=200)

    try:
        history = get_history(phone)
        reply = await get_ai_response(phone, text, history)

        if "TRANSFERIR_HUMANO" in reply:
            set_human_mode(phone, True)
            reply = "No tengo esa informacion. Un asesor te contactara pronto."

        elif "PEDIDO_CONFIRMAR" in reply:
            # Extraer la linea tecnica del reply
            linea = ""
            for l in reply.split("\n"):
                if l.strip().startswith("PEDIDO_CONFIRMAR"):
                    linea = l.strip()
                    break

            # ✅ Limpiar la linea tecnica del mensaje visible al cliente
            reply_visible = "\n".join(
                l for l in reply.split("\n")
                if not l.strip().startswith("PEDIDO_CONFIRMAR")
            ).strip()

            print("[PEDIDO LINEA] " + linea)
            partes = linea.split("|")
            exito = False

            try:
                # Estructura esperada del prompt:
                # PEDIDO_CONFIRMAR|Nombre|Referencia|Servicio|Descripcion|Capacidad|Precio

                if len(partes) < 7:
                    raise ValueError("Linea tecnica incompleta: " + linea)

                nombre      = partes[1].strip()
                referencia  = partes[2].strip()
                servicio    = partes[3].strip()
                descripcion = partes[4].strip()
                capacidad   = partes[5].strip()
                precio_raw  = partes[6].strip().replace("$", "").replace(".", "").replace(",", "")
                precio      = int(precio_raw)

                # ✅ Extraer empresa y ciudad del mensaje visible
                # Formato nuevo: "🏢 Mi Empresa  |  📍 Bogota"
                empresa = ""
                ciudad  = ""
                for l in reply_visible.split("\n"):
                    l_clean = l.strip()
                    # Formato con emojis: 🏢 Empresa  |  📍 Ciudad
                    if "🏢" in l_clean and "📍" in l_clean:
                        partes_linea = l_clean.split("|")
                        if len(partes_linea) == 2:
                            empresa = partes_linea[0].replace("🏢", "").strip()
                            ciudad  = partes_linea[1].replace("📍", "").strip()
                    # Fallback formato texto plano: "Empresa: X" / "Ciudad: X"
                    elif l_clean.lower().startswith("empresa:"):
                        empresa = l_clean.split(":", 1)[1].strip()
                    elif l_clean.lower().startswith("ciudad:"):
                        ciudad = l_clean.split(":", 1)[1].strip()

                # ✅ Extraer numero limpio (sin "whatsapp:")
                telefono = phone.replace("whatsapp:", "").strip()

                ok = await registrar_pedido(
                    telefono=telefono,
                    nombre=nombre,
                    empresa=empresa,
                    ciudad=ciudad,
                    referencia=referencia,
                    servicio=servicio,
                    descripcion=descripcion,
                    capacidad=capacidad,
                    precio=precio
                )

                if ok:
                    # Enviar solo el mensaje visible, sin la linea tecnica
                    reply = reply_visible
                    exito = True
                    print("[PEDIDO OK] " + nombre + " | " + servicio)

            except Exception as ep:
                print("[ERROR PARSE PEDIDO_CONFIRMAR] " + str(ep))

            if not exito:
                reply = "❌ Hubo un problema procesando tu solicitud. Un asesor te ayudara."

        save_messages(phone, text, reply)
        send_whatsapp(phone, reply)
        print("[OK] Respuesta enviada a " + phone)

    except Exception as e:
        print("[ERROR] " + str(e))
        send_whatsapp(phone, "Tuve un problema tecnico. Intenta en unos minutos.")

    return PlainTextResponse("", status_code=200)


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=config.PORT, reload=True)
