import os
import json
import asyncio
import threading
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

# ===== CONFIGURACIÓN =====
TOKEN = os.environ.get("BOT_TOKEN")  # Pon tu token en Render como variable de entorno
VIP_LIST_FILE = "vip_list.json"

# Carga la lista VIP desde el archivo
def cargar_vips():
    try:
        with open(VIP_LIST_FILE, "r") as f:
            return json.load(f)
    except:
        return []

vip_list = cargar_vips()

# Almacén temporal de verificaciones (se borra al reiniciar)
verificaciones = {}

# ===== CREAR APLICACIÓN DEL BOT =====
application = Application.builder().token(TOKEN).build()

# ===== COMANDO /vip =====
async def vip_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Verificar argumentos
    if not context.args:
        await update.message.reply_text("❌ Usa: `/vip @usuario`", parse_mode="Markdown")
        return

    mencion = context.args[0].strip()
    if not mencion.startswith("@"):
        await update.message.reply_text("❌ El formato debe ser @usuario")
        return

    username = mencion[1:]  # quita el @

    # Obtener ID del usuario mencionado
    try:
        chat_usuario = await context.bot.get_chat(f"@{username}")
        target_id = chat_usuario.id
    except:
        await update.message.reply_text("❌ No se pudo obtener información de ese usuario.")
        return

    # Verificar si está en la lista VIP (insensible a mayúsculas)
    if username.lower() not in [v.lower() for v in vip_list]:
        await update.message.reply_text(f"❌ El usuario @{username} **NO** está en la lista VIP.", parse_mode="Markdown")
        return

    # Preparar mensaje con botón
    initiator_id = update.effective_user.id
    texto = (
        f"🔍 Verificación solicitada por {update.effective_user.mention_html()}\n"
        f"para @{username}.\n\n"
        f"Si eres @{username}, presiona el botón para confirmar que eres VIP."
    )
    boton = InlineKeyboardButton("✅ Confirmar VIP", callback_data=f"confirm_{update.message.message_id}")
    teclado = InlineKeyboardMarkup([[boton]])

    # Enviar mensaje al grupo
    mensaje_enviado = await update.message.reply_text(
        texto,
        reply_markup=teclado,
        parse_mode="HTML"
    )

    # Guardar datos de la verificación (usamos el message_id del mensaje enviado)
    verificaciones[f"confirm_{mensaje_enviado.message_id}"] = {
        "target_id": target_id,
        "initiator_id": initiator_id,
        "target_username": username
    }

# ===== MANEJADOR DEL BOTÓN =====
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()  # quita el relojito

    data = query.data
    if not data.startswith("confirm_"):
        return

    # Buscar la información guardada
    info = verificaciones.get(data)
    if not info:
        await query.edit_message_text("❌ Esta verificación ya no es válida.")
        return

    # Verificar que quien presiona es el usuario correcto
    if query.from_user.id != info["target_id"]:
        await query.answer("⛔ No tienes permiso para confirmar esto.", show_alert=True)
        return

    # ✅ Confirmación exitosa
    target_username = info["target_username"]
    initiator_id = info["initiator_id"]

    # Editar el mensaje del grupo
    nuevo_texto = f"✅ **Confirmado** @{target_username} es VIP en 🛰️ CriptoRuta | Saldo & Criptos"
    boton_contacto = InlineKeyboardButton(
        f"📩 Contactar a @{target_username}",
        url=f"tg://user?id={info['target_id']}"
    )
    nuevo_teclado = InlineKeyboardMarkup([[boton_contacto]])
    await query.edit_message_text(
        nuevo_texto,
        reply_markup=nuevo_teclado,
        parse_mode="Markdown"
    )

    # Enviar mensaje privado al que pidió la verificación
    try:
        await context.bot.send_message(
            chat_id=initiator_id,
          text=f"✅ **Confirmado** @{target_username} es VIP en 🛰️ CriptoRuta | Saldo & Criptos",
            parse_mode="Markdown"
        )
    except:
        # Si el usuario no ha iniciado el bot, ignoramos (no pasa nada)
        pass

    # Limpiar el registro de verificación
    del verificaciones[data]

# ===== REGISTRAR MANEJADORES =====
application.add_handler(CommandHandler("vip", vip_command))
application.add_handler(CallbackQueryHandler(button_handler, pattern="^confirm_"))

# ===== SERVIDOR FLASK (para mantener vivo el bot y dar salud) =====
app = Flask(__name__)

@app.route("/")
def health():
    return "Bot funcionando ✅", 200

def iniciar_bot():
    # Usamos polling (sin webhook)
    application.run_polling(allowed_updates=["message", "callback_query"])

if __name__ == "__main__":
    # Ejecutar el bot en un hilo separado
    hilo_bot = threading.Thread(target=iniciar_bot)
    hilo_bot.start()

    # Ejecutar Flask en el hilo principal (así Render ve un puerto HTTP)
    app.run(host="0.0.0.0", port=5000)
