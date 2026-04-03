# 🎯 WordleTracker Bot

Bot de Telegram para llevar el marcador del Wordle entre dos jugadores.

## ¿Cómo funciona?

- Cada jugador comparte su resultado del Wordle en el grupo (con los emojis de colores)
- Cuando los dos han compartido, el bot calcula quién ganó y actualiza el marcador
- Gana quien adivine en menos intentos. Empate si usan los mismos o los dos fallan.

## Comandos

- `/marcador` — Ver el marcador actual
- `/reset` — Reiniciar el marcador
- `/ayuda` — Ver ayuda

---

## 🚀 Despliegue en Railway (gratis)

### 1. Sube el código a GitHub

1. Crea una cuenta en [github.com](https://github.com) si no tienes
2. Crea un repositorio nuevo (ej: `wordle-tracker-bot`)
3. Sube los archivos `bot.py` y `requirements.txt`

### 2. Despliega en Railway

1. Ve a [railway.app](https://railway.app) y regístrate con tu cuenta de GitHub
2. Haz clic en **"New Project"** → **"Deploy from GitHub repo"**
3. Selecciona tu repositorio `wordle-tracker-bot`
4. Railway detectará automáticamente que es Python
5. En **Settings → Start Command** pon: `python bot.py`
6. Haz clic en **Deploy**

¡Listo! El bot estará corriendo 24/7 de forma gratuita.

### 3. Añade el bot al grupo

1. Crea un grupo de Telegram con tu mujer
2. Añade el bot `@WordleTrackerESPbot` al grupo
3. Escribe `/start` para que se presente
4. ¡A jugar! 🎯

---

## 🛠 Ejecutar en local (opcional)

```bash
pip install -r requirements.txt
python bot.py
```

---

## 📁 Archivos

- `bot.py` — Código principal del bot
- `requirements.txt` — Dependencias
- `scores.json` — Se crea automáticamente para guardar el marcador
