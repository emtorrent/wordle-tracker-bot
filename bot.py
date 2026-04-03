import logging
import json
import os
import re
import threading
from datetime import time as dtime
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
    has_wordle_emojis = bool(re.search(r'[🟩🟨⬛⬜🟦🟧]', text))
    if not has_wordle_emojis:
        return None

    attempts_match = re.search(r'\b([1-6X])/6\*?', text)
    if not attempts_match:
        return None

    attempts_str = attempts_match.group(1)
    if attempts_str == 'X':
        attempts = 7
        failed = True
    else:
        attempts = int(attempts_str)
        failed = False

    puzzle_match = re.search(r'#(\d+)', text)
    puzzle_num = puzzle_match.group(1) if puzzle_match else None

    return {"attempts": attempts, "failed": failed, "puzzle": puzzle_num}

def build_ranking_message(pending, players, stats, puzzle_id):
    # Ordenar: acertados por intentos asc, fallidos al final
    sorted_players = sorted(
        pending.items(),
        key=lambda x: (x[1]["failed"], x[1]["attempts"])
    )

    # Calcular posiciones con empates
    positions = []
    prev_key = None
    pos = 0
    skip = 0
    for uid, data in sorted_players:
        key = (data["failed"], data["attempts"])
        if key != prev_key:
            pos += 1 + skip
            skip = 0
        else:
            skip += 1
        positions.append(pos)
        prev_key = key

    min_pos = min(positions)
    max_pos = max(positions)
    all_same = len(set(positions)) == 1

    # Actualizar estadísticas
    for uid, data in sorted_players:
        if uid not in stats:
            stats[uid] = {"wins": 0, "draws": 0, "losses": 0}

    winners = [sorted_players[i][0] for i, p in enumerate(positions) if p == min_pos]
    losers = [sorted_players[i][0] for i, p in enumerate(positions) if p == max_pos and not all_same]

    for i, (uid, data) in enumerate(sorted_players):
        if all_same:
            stats[uid]["draws"] += 1
        elif uid in winners:
            stats[uid]["wins"] += 1 if len(winners) == 1 else 0
            if len(winners) > 1:
                stats[uid]["draws"] += 1
        elif uid in losers:
            stats[uid]["losses"] += 1 if len(losers) == 1 else 0
            if len(losers) > 1:
                stats[uid]["draws"] += 1
        else:
            stats[uid]["draws"] += 1

    lines = [f"🎯 *Resultado del día #{puzzle_id}*\n"]
    medals = ["🥇", "🥈", "🥉"]

    for i, (uid, data) in enumerate(sorted_players):
        name = players.get(uid, "Jugador")
        att_str = "X" if data["failed"] else str(data["attempts"])
        if data["failed"]:
            icon = "💀"
        else:
            icon = medals[positions[i] - 1] if positions[i] - 1 < len(medals) else "▪️"
        lines.append(f"{icon} *{name}* — {att_str}/6")

    if all_same:
        if sorted_players[0][1]["failed"]:
            lines.append("\n😂 ¡Todos la habéis cagado! Empate por fracaso colectivo")
        else:
            lines.append(f"\n🤝 ¡Empate! Todos en {sorted_players[0][1]['attempts']}/6")
    else:
        winner_names = [players.get(uid, "Jugador") for uid in winners]
        if len(winner_names) == 1:
            lines.append(f"\n🏆 ¡Gana *{winner_names[0]}*!")
        else:
            lines.append(f"\n🏆 ¡Empate en el primer puesto: {', '.join(f'*{n}*' for n in winner_names)}!")

    lines.append("\n📊 *Marcador acumulado:*")
    sorted_stats = sorted(stats.items(), key=lambda x: (x[1]["wins"], -x[1]["losses"]), reverse=True)
    stat_medals = ["🥇", "🥈", "🥉"]
    for j, (uid, s) in enumerate(sorted_stats):
        name = players.get(uid, "Jugador")
        sm = stat_medals[j] if j < len(stat_medals) else "▪️"
        total = s["wins"] + s["draws"] + s["losses"]
        lines.append(f"{sm} *{name}*: {s['wins']}V / {s['draws']}E / {s['losses']}D ({total} partidas)")

    return "\n".join(lines)

async def close_round(bot, chat_id, chat_data):
    pending = chat_data.get("pending", {})
    if not pending:
        return

    if "stats" not in chat_data:
        chat_data["stats"] = {}

    puzzle_id = list(pending.values())[0].get("puzzle", "hoy")
    missing = [name for uid, name in chat_data["players"].items() if uid not in pending]

    msg = build_ranking_message(pending, chat_data["players"], chat_data["stats"], puzzle_id)

    if missing:
        msg += f"\n\n⚠️ Sin resultado hoy: {', '.join(missing)}"

    await bot.send_message(chat_id=int(chat_id), text=msg, parse_mode="Markdown")

    chat_data["history"].append({"puzzle": puzzle_id, "results": dict(pending)})
    chat_data["pending"] = {}

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

    if chat_id not in scores:
        scores[chat_id] = {"players": {}, "pending": {}, "stats": {}, "history": []}

    chat_data = scores[chat_id]
    chat_data["players"][user_id] = user_name

    if "pending" not in chat_data:
        chat_data["pending"] = {}
    if "stats" not in chat_data:
        chat_data["stats"] = {}

    already_shared = user_id in chat_data["pending"]
    chat_data["pending"][user_id] = {
        "name": user_name,
        "attempts": result["attempts"],
        "failed": result["failed"],
        "puzzle": result["puzzle"] or "hoy"
    }

    attempts_display = "X" if result["failed"] else str(result["attempts"])

    if already_shared:
        await update.message.reply_text(
            f"🔄 *{user_name}* actualizado: *{attempts_display}/6*",
            parse_mode="Markdown"
        )
    else:
        total = len(chat_data["players"])
        shared = len(chat_data["pending"])
        faltan = total - shared
        if faltan > 0:
            await update.message.reply_text(
                f"✅ *{user_name}* registrado: *{attempts_display}/6*\n⏳ Faltan {faltan} por compartir...",
                parse_mode="Markdown"
            )

    save_scores(scores)

    # Si todos han compartido, cerrar ronda
    all_shared = all(uid in chat_data["pending"] for uid in chat_data["players"])
    if all_shared and len(chat_data["pending"]) >= 2:
        puzzle_id = list(chat_data["pending"].values())[0].get("puzzle", "hoy")
        msg = build_ranking_message(chat_data["pending"], chat_data["players"], chat_data["stats"], puzzle_id)
        await update.message.reply_text(msg, parse_mode="Markdown")
        chat_data["history"].append({"puzzle": puzzle_id, "results": dict(chat_data["pending"])})
        chat_data["pending"] = {}
        save_scores(scores)

async def marcador(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.message.chat_id)
    scores = load_scores()

    if chat_id not in scores or not scores[chat_id].get("stats"):
        await update.message.reply_text("📊 Todavía no hay resultados registrados.")
        return

    chat_data = scores[chat_id]
    stats = chat_data["stats"]
    players = chat_data["players"]

    lines = ["📊 *Marcador WordleTracker*\n"]
    sorted_players = sorted(stats.items(), key=lambda x: (x[1]["wins"], -x[1]["losses"]), reverse=True)
    medals = ["🥇", "🥈", "🥉"]

    for i, (uid, s) in enumerate(sorted_players):
        name = players.get(uid, "Jugador")
        medal = medals[i] if i < len(medals) else "▪️"
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

🟩🟨⬛ Comparte tu resultado del Wordle en el grupo y lo registro automáticamente. Llevo el marcador de victorias, empates y derrotas para que todo el mundo sepa quién adivina mejor las palabras cada día. Sin trampas, sin excusas. ¡Que gane la mejor persona!

*Comandos:*
/marcador — Ver el marcador actual
/reset — Reiniciar el marcador
/ayuda — Ver esta ayuda

*¿Cómo funciona?*
Cada persona comparte su resultado del Wordle. Cuando todos hayan compartido, proclamo el ganador del día. Si alguien no comparte antes de las 23:59, cierro la ronda con los que hayan participado. 🤝"""

    await update.message.reply_text(msg, parse_mode="Markdown")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await ayuda(update, context)

async def cierre_diario(context: ContextTypes.DEFAULT_TYPE):
    scores = load_scores()
    for chat_id, chat_data in scores.items():
        if chat_data.get("pending"):
            await close_round(context.bot, chat_id, chat_data)
    save_scores(scores)

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
    web_thread = threading.Thread(target=run_web_server, daemon=True)
    web_thread.start()

    app = Application.builder().token(TOKEN).build()
    app.job_queue.run_daily(cierre_diario, time=dtime(23, 59, 0))

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("ayuda", ayuda))
    app.add_handler(CommandHandler("marcador", marcador))
    app.add_handler(CommandHandler("reset", reset))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("🤖 WordleTracker Bot arrancado!")
    app.run_polling()

if __name__ == "__main__":
    main()
