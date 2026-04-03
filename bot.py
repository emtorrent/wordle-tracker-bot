import logging
import json
import os
import re
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# Token del bot
TOKEN = "8337410047:AAFLM4KKujKWoa8_vw6SMar_iugcfH8Xyu0"

# Archivo para guardar los datos
DATA_FILE = "scores.json"

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

def load_scores():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_scores(scores):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(scores, f, ensure_ascii=False, indent=2)

def parse_wordle_result(text):
    """
    Detecta resultados de Wordle en español.
    Formatos soportados:
    - "Wordle (ES) #1234 4/6"
    - "Wordle 1234 4/6"  
    - "#Wordle 1234 4/6"
    - "wordle.danielfrg.com #1234 4/6"
    - Cualquier variante con emojis de cuadros de colores
    """
    text_lower = text.lower()
    
    # Detectar si contiene emojis típicos de Wordle
    has_wordle_emojis = bool(re.search(r'[🟩🟨⬛⬜🟦🟧]', text))
    
    if not has_wordle_emojis:
        return None
    
    # Buscar patrón de intentos: X/6 o X/6* (con asterisco si en modo difícil)
    attempts_match = re.search(r'\b([1-6X])/6\*?', text)
    if not attempts_match:
        return None
    
    attempts_str = attempts_match.group(1)
    
    # X/6 significa que no lo adivinó
    if attempts_str == 'X':
        attempts = 7  # Más que 6 = derrota
        failed = True
    else:
        attempts = int(attempts_str)
        failed = False
    
    # Buscar número del puzzle (opcional)
    puzzle_match = re.search(r'[#\s](\d{3,4})', text)
    puzzle_num = puzzle_match.group(1) if puzzle_match else None
    
    return {
        "attempts": attempts,
        "failed": failed,
        "puzzle": puzzle_num
    }

def determine_winner(results):
    """
    Dado un dict {user_id: {name, attempts, failed}},
    determina ganador o empate.
    Retorna: {"winner": user_id o None, "is_draw": bool}
    """
    if len(results) < 2:
        return None
    
    users = list(results.values())
    
    # Si los dos fallaron
    if all(u["failed"] for u in users):
        return {"winner": None, "is_draw": True, "type": "both_failed"}
    
    # Si solo uno falló, gana el otro
    failed_users = [uid for uid, u in results.items() if u["failed"]]
    if len(failed_users) == 1:
        winner_id = [uid for uid in results if uid not in failed_users][0]
        return {"winner": winner_id, "is_draw": False, "type": "only_one_succeeded"}
    
    # Los dos acertaron: gana quien usó menos intentos
    user_ids = list(results.keys())
    a1 = results[user_ids[0]]["attempts"]
    a2 = results[user_ids[1]]["attempts"]
    
    if a1 < a2:
        return {"winner": user_ids[0], "is_draw": False, "type": "fewer_attempts"}
    elif a2 < a1:
        return {"winner": user_ids[1], "is_draw": False, "type": "fewer_attempts"}
    else:
        return {"winner": None, "is_draw": True, "type": "same_attempts"}

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return
    
    text = update.message.text
    user = update.message.from_user
    chat_id = str(update.message.chat_id)
    user_id = str(user.id)
    user_name = user.first_name or user.username or "Jugador"
    
    result = parse_wordle_result(text)
    if not result:
        return
    
    scores = load_scores()
    
    # Inicializar chat si no existe
    if chat_id not in scores:
        scores[chat_id] = {
            "players": {},
            "pending": {},
            "history": []
        }
    
    chat_data = scores[chat_id]
    
    # Registrar jugador
    chat_data["players"][user_id] = user_name
    
    puzzle_id = result["puzzle"] or "hoy"
    
    # Guardar resultado pendiente del usuario
    if "pending" not in chat_data:
        chat_data["pending"] = {}
    
    chat_data["pending"][user_id] = {
        "name": user_name,
        "attempts": result["attempts"],
        "failed": result["failed"],
        "puzzle": puzzle_id
    }
    
    attempts_display = "X" if result["failed"] else str(result["attempts"])
    await update.message.reply_text(
        f"✅ *{user_name}* registrado: *{attempts_display}/6*",
        parse_mode="Markdown"
    )
    
    # Si hay exactamente 2 jugadores con resultado, calcular ganador
    if len(chat_data["pending"]) >= 2:
        winner_info = determine_winner(chat_data["pending"])
        
        if winner_info:
            # Inicializar estadísticas
            if "stats" not in chat_data:
                chat_data["stats"] = {}
            
            for uid in chat_data["pending"]:
                if uid not in chat_data["stats"]:
                    chat_data["stats"][uid] = {"wins": 0, "draws": 0, "losses": 0}
            
            player_ids = list(chat_data["pending"].keys())
            
            if winner_info["is_draw"]:
                for uid in player_ids:
                    chat_data["stats"][uid]["draws"] += 1
                
                type_msg = winner_info.get("type", "")
                if type_msg == "both_failed":
                    result_msg = "💀 ¡Los dos la habéis cagado! Empate por fracaso mutuo 😂"
                else:
                    p1 = chat_data["pending"][player_ids[0]]
                    result_msg = f"🤝 ¡*Empate*! Los dos en *{p1['attempts']}/6* intentos"
                
            else:
                winner_id = winner_info["winner"]
                loser_id = [uid for uid in player_ids if uid != winner_id][0]
                
                chat_data["stats"][winner_id]["wins"] += 1
                chat_data["stats"][loser_id]["losses"] += 1
                
                winner_name = chat_data["pending"][winner_id]["name"]
                winner_att = chat_data["pending"][winner_id]["attempts"]
                loser_att = chat_data["pending"][loser_id]["attempts"]
                
                winner_att_str = "X" if chat_data["pending"][winner_id]["failed"] else str(winner_att)
                loser_att_str = "X" if chat_data["pending"][loser_id]["failed"] else str(loser_att)
                
                result_msg = f"🏆 ¡Gana *{winner_name}*! ({winner_att_str}/6 vs {loser_att_str}/6)"
            
            # Marcador actual
            stats = chat_data["stats"]
            scoreboard_lines = []
            for uid in player_ids:
                name = chat_data["players"].get(uid, "Jugador")
                s = stats.get(uid, {"wins": 0, "draws": 0, "losses": 0})
                scoreboard_lines.append(
                    f"• {name}: {s['wins']}V / {s['draws']}E / {s['losses']}D"
                )
            
            scoreboard = "\n".join(scoreboard_lines)
            
            await update.message.reply_text(
                f"{result_msg}\n\n📊 *Marcador:*\n{scoreboard}",
                parse_mode="Markdown"
            )
            
            # Guardar en historial y limpiar pendientes
            chat_data["history"].append({
                "puzzle": puzzle_id,
                "results": dict(chat_data["pending"]),
                "winner": winner_info
            })
            chat_data["pending"] = {}
    
    save_scores(scores)

async def marcador(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.message.chat_id)
    scores = load_scores()
    
    if chat_id not in scores or "stats" not in scores[chat_id]:
        await update.message.reply_text("📊 Todavía no hay resultados registrados.")
        return
    
    chat_data = scores[chat_id]
    stats = chat_data["stats"]
    players = chat_data["players"]
    
    if not stats:
        await update.message.reply_text("📊 Todavía no hay resultados registrados.")
        return
    
    lines = ["📊 *Marcador WordleTracker*\n"]
    
    # Ordenar por victorias
    sorted_players = sorted(stats.items(), key=lambda x: x[1]["wins"], reverse=True)
    
    medals = ["🥇", "🥈", "🥉"]
    for i, (uid, s) in enumerate(sorted_players):
        name = players.get(uid, "Jugador")
        medal = medals[i] if i < 3 else "▪️"
        total = s["wins"] + s["draws"] + s["losses"]
        lines.append(f"{medal} *{name}*")
        lines.append(f"   🏆 {s['wins']}V  🤝 {s['draws']}E  💀 {s['losses']}D  ({total} partidas)")
    
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")

async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.message.chat_id)
    scores = load_scores()
    
    if chat_id in scores:
        scores[chat_id]["stats"] = {}
        scores[chat_id]["pending"] = {}
        scores[chat_id]["history"] = []
        save_scores(scores)
    
    await update.message.reply_text("🔄 Marcador reiniciado. ¡A empezar de cero!")

async def ayuda(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = """🎯 *WordleTracker Bot*

Comparte el resultado del Wordle en el grupo y lo registro automáticamente.

*Comandos:*
/marcador — Ver el marcador actual
/reset — Reiniciar el marcador
/ayuda — Ver esta ayuda

*¿Cómo funciona?*
Cada uno comparte su resultado del Wordle (con los emojis de colores). Cuando los dos hayáis compartido el resultado del día, calculo quién ha ganado y actualizo el marcador.

Gana quien lo adivine en menos intentos. Si los dos fallan o usan los mismos intentos, es empate. 🤝"""
    
    await update.message.reply_text(msg, parse_mode="Markdown")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await ayuda(update, context)

def run_web_server():
    from http.server import HTTPServer, BaseHTTPRequestHandler
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"WordleTracker Bot running!")
        def log_message(self, format, *args):
            pass
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), Handler)
    server.serve_forever()

def main():
    import threading
    web_thread = threading.Thread(target=run_web_server, daemon=True)
    web_thread.start()

    app = Application.builder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("ayuda", ayuda))
    app.add_handler(CommandHandler("marcador", marcador))
    app.add_handler(CommandHandler("reset", reset))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("🤖 WordleTracker Bot arrancado!")
    app.run_polling()

if __name__ == "__main__":
    main()
