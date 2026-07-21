"""
Lance en parallèle :
- le bot Discord (discord.py)
- un serveur web FastAPI qui sert le site de configuration ET l'API que
  le site utilise pour lire/écrire la config

Variables d'environnement à définir sur Railway :
- DISCORD_TOKEN       : le token de ton bot
- DASHBOARD_API_KEY   : un mot de passe que tu choisis, à saisir dans le site web
- PORT                : fournie automatiquement par Railway
"""

import asyncio
import os

import discord
import uvicorn
from discord.ext import commands, tasks
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from config_store import config, update_config

DISCORD_TOKEN = os.environ.get("DISCORD_TOKEN")
API_KEY = os.environ.get("DASHBOARD_API_KEY", "change-moi")

# ---------------------------------------------------------------------------
# API web + site
# ---------------------------------------------------------------------------
app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def check_key(x_api_key: str | None):
    if x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Clé API invalide")


@app.get("/api/config")
def get_config():
    return config


@app.post("/api/config")
async def post_config(request: Request, x_api_key: str | None = Header(default=None)):
    check_key(x_api_key)
    new_values = await request.json()
    update_config(new_values)
    return {"status": "ok"}


# Sert le site (index.html) à la racine — place ton fichier HTML dans ./static/index.html
app.mount("/", StaticFiles(directory="static", html=True), name="static")

# ---------------------------------------------------------------------------
# Bot Discord
# ---------------------------------------------------------------------------
intents = discord.Intents.default()
intents.members = True
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)


@bot.event
async def on_ready():
    print(f"Connecté en tant que {bot.user}")


@bot.event
async def on_member_join(member: discord.Member):
    w = config.get("welcome", {})
    if w.get("enabled") and w.get("channel"):
        channel = discord.utils.get(member.guild.text_channels, name=w["channel"].lstrip("#"))
        if channel:
            text = w.get("message", "").format(
                user=member.mention, server=member.guild.name, membercount=member.guild.member_count
            )
            await channel.send(text)

    ar = config.get("autorole", {})
    if ar.get("enabled") and ar.get("name"):
        role = discord.utils.get(member.guild.roles, name=ar["name"])
        if role:
            await member.add_roles(role)

    b = config.get("bank", {})
    if b.get("enabled"):
        # branche ici ta logique de solde de départ (base de données, etc.)
        pass


@bot.event
async def on_member_remove(member: discord.Member):
    leave = config.get("leave", {})
    if leave.get("enabled") and leave.get("channel"):
        channel = discord.utils.get(member.guild.text_channels, name=leave["channel"].lstrip("#"))
        if channel:
            text = leave.get("message", "").format(user=member.name, server=member.guild.name)
            await channel.send(text)


@bot.event
async def on_raw_reaction_add(payload: discord.RawReactionActionEvent):
    if payload.member is None or payload.member.bot:
        return
    rr = config.get("reactionRoles", {})
    for pair in rr.get("pairs", []):
        if str(payload.emoji) == pair.get("emoji"):
            role = discord.utils.get(payload.member.guild.roles, name=pair.get("role"))
            if role:
                await payload.member.add_roles(role)


@bot.event
async def on_raw_reaction_remove(payload: discord.RawReactionActionEvent):
    rr = config.get("reactionRoles", {})
    for pair in rr.get("pairs", []):
        if str(payload.emoji) == pair.get("emoji"):
            guild = bot.get_guild(payload.guild_id)
            if not guild:
                continue
            role = discord.utils.get(guild.roles, name=pair.get("role"))
            member = guild.get_member(payload.user_id)
            if role and member:
                await member.remove_roles(role)


@tasks.loop(minutes=60)
async def auto_messages_loop():
    """Envoie chaque message automatique une fois par heure écoulée selon son intervalle."""
    auto_messages_loop.current_hour = getattr(auto_messages_loop, "current_hour", 0) + 1
    for msg in config.get("autoMessages", []):
        interval = int(msg.get("interval", 24)) or 24
        if auto_messages_loop.current_hour % interval == 0:
            for guild in bot.guilds:
                channel = discord.utils.get(guild.text_channels, name=str(msg.get("channel", "")).lstrip("#"))
                if channel:
                    await channel.send(msg.get("text", ""))


@auto_messages_loop.before_loop
async def before_auto_messages():
    await bot.wait_until_ready()


auto_messages_loop.start()


# ---------------------------------------------------------------------------
# Lancement conjoint bot + serveur web
# ---------------------------------------------------------------------------
async def main():
    port = int(os.environ.get("PORT", 8000))
    config_uvicorn = uvicorn.Config(app, host="0.0.0.0", port=port, log_level="info")
    server = uvicorn.Server(config_uvicorn)
    await asyncio.gather(
        server.serve(),
        bot.start(DISCORD_TOKEN),
    )


if __name__ == "__main__":
    asyncio.run(main())
