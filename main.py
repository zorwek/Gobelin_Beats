import discord
from discord.ext import commands
import yt_dlp
import asyncio
import os
import shutil

TOKEN = os.getenv("DISCORD_TOKEN")  # Utilise une variable d'environnement (⚠️ plus sûr que hardcodé)

intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True

bot = commands.Bot(command_prefix='!', intents=intents)

if not os.path.exists("temp"):
    os.makedirs("temp")

ytdl_opts = {
    'format': 'bestaudio/best',
    'outtmpl': 'temp/%(id)s.%(ext)s',
    'cookiefile': 'cookies.txt',  # <- Utilisation du fichier cookies
    'quiet': True,
    'no_warnings': True,
}
ytdl = yt_dlp.YoutubeDL(ytdl_opts)


class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, filepath, volume=0.5):
        super().__init__(source, volume)
        self.data = data
        self.filepath = filepath

    @classmethod
    async def from_url(cls, url, *, loop, stream=False):
        data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=not stream))
        if 'entries' in data:
            data = data['entries'][0]
        filename = ytdl.prepare_filename(data)
        return cls(discord.FFmpegPCMAudio(filename), data=data, filepath=filename)


@bot.event
async def on_ready():
    print(f'Connecté en tant que {bot.user}')


@bot.command()
async def join(ctx):
    if ctx.author.voice:
        await ctx.author.voice.channel.connect()


@bot.command()
async def leave(ctx):
    if ctx.voice_client:
        await ctx.voice_client.disconnect()
        vider_temp()


@bot.command()
async def play(ctx, url):
    try:
        async with ctx.typing():
            player = await YTDLSource.from_url(url, loop=bot.loop, stream=False)

            def after_playing(error):
                try:
                    if error:
                        print(f"Erreur après lecture: {error}")
                    if os.path.exists(player.filepath):
                        os.remove(player.filepath)
                except Exception as e:
                    print(f"Erreur suppression fichier: {e}")

            ctx.voice_client.play(player, after=after_playing)

        await ctx.send(f'Lecture: {player.data["title"]}')
    except Exception as e:
        await ctx.send(f"Erreur: {e}")


@bot.command()
async def stop(ctx):
    if ctx.voice_client:
        ctx.voice_client.stop()
        await ctx.voice_client.disconnect()
        vider_temp()


def vider_temp():
    if os.path.exists("temp"):
        for filename in os.listdir("temp"):
            filepath = os.path.join("temp", filename)
            try:
                os.remove(filepath)
            except Exception as e:
                print(f"Erreur suppression {filepath} : {e}")


@bot.event
async def on_disconnect():
    print("Bot déconnecté de Discord.")
    vider_temp()


bot.run(TOKEN)
