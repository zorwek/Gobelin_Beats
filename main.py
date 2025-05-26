import discord
from discord.ext import commands
import yt_dlp
import asyncio
import os
import uuid

TOKEN = os.getenv("DISCORD_TOKEN")

os.makedirs("temp", exist_ok=True)

intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True  # Nécessaire pour détecter les déconnexions vocales
bot = commands.Bot(command_prefix="!", intents=intents)

ffmpeg_options = {'options': '-vn'}
ytdl_format_options = {
    'format': 'bestaudio',
    'noplaylist': True,
    'quiet': True
}
ytdl = yt_dlp.YoutubeDL(ytdl_format_options)

class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, filepath, volume=0.5):
        super().__init__(source, volume)
        self.data = data
        self.title = data.get("title")
        self.filepath = filepath

    @classmethod
    async def from_url(cls, url, *, loop=None, stream=False):
        loop = loop or asyncio.get_event_loop()
        data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=not stream))
        if "entries" in data:
            data = data["entries"][0]

        if stream:
            filename = data["url"]
        else:
            downloaded_filename = ytdl.prepare_filename(data)
            temp_filename = f"temp/{uuid.uuid4().hex}.mp3"
            os.rename(downloaded_filename, temp_filename)
            filename = temp_filename

        return cls(discord.FFmpegPCMAudio(filename, **ffmpeg_options), data=data, filepath=filename)

async def cleanup_temp_folder():
    for f in os.listdir("temp"):
        path = os.path.join("temp", f)
        try:
            os.remove(path)
        except Exception as e:
            print(f"Erreur lors de la suppression de {path} : {e}")

async def cleanup_file(filepath):
    await asyncio.sleep(1)
    try:
        if os.path.exists(filepath):
            os.remove(filepath)
            print(f"Fichier supprimé : {filepath}")
    except Exception as e:
        print(f"Erreur lors de la suppression du fichier : {e}")

def after_playing(error):
    if error:
        print(f"Erreur de lecture : {error}")
    # Lance la suppression du fichier joué
    asyncio.run_coroutine_threadsafe(cleanup_file(player.filepath), bot.loop)

@bot.command()
async def join(ctx):
    if ctx.author.voice:
        await ctx.author.voice.channel.connect()
    else:
        await ctx.send("Tu dois être dans un salon vocal pour que je te rejoigne.")

@bot.command()
async def play(ctx, *, url):
    global player
    if not ctx.voice_client:
        if ctx.author.voice:
            await ctx.author.voice.channel.connect()
        else:
            await ctx.send("Tu dois être dans un salon vocal pour jouer de la musique.")
            return

    async with ctx.typing():
        player = await YTDLSource.from_url(url, loop=bot.loop, stream=False)
        ctx.voice_client.play(player, after=after_playing)
        await ctx.send(f"🎶 Lecture en cours : **{player.title}**")

@bot.command()
async def stop(ctx):
    if ctx.voice_client and ctx.voice_client.is_playing():
        ctx.voice_client.stop()
    await cleanup_temp_folder()  # Vide tout le dossier temp

@bot.command()
async def leave(ctx):
    if ctx.voice_client:
        await ctx.voice_client.disconnect()
    await cleanup_temp_folder()  # Vide tout le dossier temp

@bot.event
async def on_voice_state_update(member, before, after):
    # Si c’est le bot qui est déconnecté manuellement du vocal, on vide le dossier temp
    if member == bot.user:
        # Déconnecté du vocal (avant avait un channel, après none)
        if before.channel is not None and after.channel is None:
            await cleanup_temp_folder()

@bot.event
async def on_ready():
    print(f"Bot connecté en tant que {bot.user}")

bot.run(TOKEN)
