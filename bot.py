import os
import logging
from dotenv import load_dotenv
import nextcord # Nextcord instead of Discord.py until Discord.py 2.6 fixes VC connecting
from nextcord.ext import commands
from nextcord import FFmpegPCMAudio
from helpers.voice import validate_voice
import yt_dlp
from helpers.youtube import get_youtube_audio, queue_is_empty, add_to_queue, clear_queue, remove_from_queue, list_queue, play_next_in_queue

# Logging/Debug Config
logging.getLogger("nextcord.gateway").setLevel(logging.WARNING)

##############################
# Load Environment Variables #
##############################
load_dotenv()   # Gather data from secret .env file
TOKEN = os.getenv("TOKEN")
CREATOR_ID = int(os.getenv("CREATOR_ID"))
GUILD_IDS = [
    int(gid.strip())
    for gid in os.getenv("GUILD_IDS", "").split(",")
    if gid.strip()
]

################################
# Load and Parse Sounds Folder #
################################
def load_sound_files(folder: str) -> list[str]:
    try:
        files = os.listdir(folder)
        sound_list = [
            os.path.splitext(f)[0]
            for f in files
            if f.endswith((".mp3", ".wav", ".ogg"))
        ]
        sound_list.sort()  # Sort alphabetically
        print("Sounds folder loaded")
        return sound_list
    except FileNotFoundError:
        print("The sounds folder doesn't exist.", ephemeral=True)
        return []

SOUND_FOLDER = "./sounds"
sound_files = load_sound_files(SOUND_FOLDER)

###############
# Startup Bot #
###############
intents = nextcord.Intents.default()
intents.voice_states = True
bot = commands.Bot(command_prefix='!', intents=intents)

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    try:
        for gid in GUILD_IDS:
            await bot.sync_application_commands(guild_id=gid)
            print(f"Synced commands to guild {gid}")
    except Exception as e:
        print(f"Error syncing commands: {e}")

##################
# Basic Commands #
##################
@bot.slash_command(name="join", description="The bot connects to your voice channel.", guild_ids=GUILD_IDS)
async def join_channel(interaction: nextcord.Interaction):
    # Get the voice state of the user who invoked the command
    if not interaction.user.voice or not interaction.user.voice.channel:
        await interaction.response.send_message("You are not connected to a voice channel.", ephemeral=True)
        print(f"{interaction.user.name} - Failed to join {channel.name}")
        return
    
    # Check if bot is already connected to a voice channel
    voice_client = nextcord.utils.get(bot.voice_clients, guild=interaction.guild)
    if voice_client and voice_client.is_connected():
        await interaction.response.send_message("I'm already connected to a voice channel.", ephemeral=True)
        return

    # Connect the bot to the voice channel
    channel = interaction.user.voice.channel
    try:
        await channel.connect(timeout=10.0, reconnect=False)
        await interaction.response.send_message(f"Joined {channel.name}!", ephemeral=True, delete_after=3.0)
        print(f"{interaction.user.name} - Joined {channel.name}")
    except Exception as e:
        await interaction.response.send_message(f"Failed to connect: {e}", ephemeral=True)
        print(f"Failed to join {channel.name}")
        raise

@bot.slash_command(name='leave', description="Disconnect the bot from the voice channel.", guild_ids=GUILD_IDS)
async def leave_channel(interaction: nextcord.Interaction):
    # Get the voice client for the guild
    voice_client = nextcord.utils.get(bot.voice_clients, guild=interaction.guild)

    # Check if bot/user is/isn't in a voice channel or in same voice channel
    if not await validate_voice(interaction, voice_client): return

    # Disconnect the bot from the voice channel
    channel = interaction.user.voice.channel

    await voice_client.disconnect()
    await interaction.response.send_message("Disconnected from {channel.name}!", ephemeral=True, delete_after=3.0)
    print(f"{interaction.user.name} - Disconnected from {channel.name}")

########################
# Soundboard Commmands #
########################
@bot.slash_command(name='list', description="List available sound files.", guild_ids=GUILD_IDS)
async def list_sounds(interaction: nextcord.Interaction):
    # Check if there are any sound files
    if not sound_files:
        await interaction.response.send_message("No sound files found.", ephemeral=True)
        print("{interaction.user.name} - No sound files in folder")
        return

    # Format list nicely
    formatted_list = "\n".join(f"- {name}" for name in sound_files)
    await interaction.response.send_message(f"**Available Sounds:**\n{formatted_list}", ephemeral=True)
    print(f"{interaction.user.name} - Viewed soundboard")

@bot.slash_command(name='request', description="Submit link of sound to be added to list (manually added by Creator).", guild_ids=GUILD_IDS)
async def request(interaction: nextcord.Interaction, sound_link: str):
    # Gather data from request
    user_name = interaction.user.name
    guild_name = interaction.guild.name

    # Acknowledge the request
    await interaction.response.send_message("Your request has been sent to the Creator.", ephemeral=True, delete_after=5.0)

    # Create DMChannel to creator
    creator_user = await bot.fetch_user(CREATOR_ID)
    if creator_user:
        await creator_user.send(content=f"**Sound Request from {user_name} in {guild_name}!**\n {sound_link}")

@bot.slash_command(name="sound", description="Play specified sound.", guild_ids=GUILD_IDS)
async def play_sound(interaction: nextcord.Interaction, sound_name: str):
    voice_client = nextcord.utils.get(bot.voice_clients, guild=interaction.guild)

    # Check if bot/user is/isn't in a voice channel or in same voice channel
    if not await validate_voice(interaction, voice_client): return
    
    # Check if audio stream is taken
    if voice_client.is_playing():
        await interaction.response.send_message("Currently playing other audio.", ephemeral=True, delete_after=2.0)
        print(f"{interaction.user.name} - Failed to play sound (vc is busy)")
        return

    # Play sound
    audio_source = FFmpegPCMAudio(f"./sounds/{sound_name}.mp3")
    await interaction.response.send_message(f"Now playing: {sound_name}", ephemeral=True, delete_after=2.0)
    print(f"{interaction.user.name} - Played {sound_name}")
    voice_client.play(audio_source)

####################
# YouTube Commands #
####################
@bot.slash_command(name="play", description="Play audio of YouTube video URL.", guild_ids=GUILD_IDS)
async def play_youtube(interaction: nextcord.Interaction, youtube_url: str):
    voice_client = nextcord.utils.get(bot.voice_clients, guild=interaction.guild)

    # Check if bot/user is/isn't in a voice channel or in same voice channel
    if not await validate_voice(interaction, voice_client): return
    
    # Defer interaction (prevents "The application did not respond" error)
    await interaction.response.defer(ephemeral=True)

    # Play YouTube audio
    try:
        source, title = get_youtube_audio(youtube_url)
        add_to_queue(interaction.guild.id, source, title)

        if not voice_client.is_playing():   # If nothing playing, play next in queue
            await play_next_in_queue(voice_client, interaction.guild.id)
            await interaction.followup.send(f"Now playing: **{title}**", ephemeral=True, delete_after=3.0)
            print(f"{interaction.user.name} - Played {title}")
        else:
            await interaction.followup.send(f"Queued: **{title}**", ephemeral=True, delete_after=3.0)
            print(f"{interaction.user.name} - Queued {title}")
        
    except Exception as e:
        await interaction.followup.send("Could not play video.")
        print(f"{interaction.user.name} - Playback error: {e}")

@bot.slash_command(name="stop", description="Stop YouTube audio.", guild_ids=GUILD_IDS)
async def stop_youtube(interaction: nextcord.Interaction):
    voice_client = nextcord.utils.get(bot.voice_clients, guild=interaction.guild)

    # Check if bot/user is/isn't in a voice channel or in same voice channel
    if not await validate_voice(interaction, voice_client): return
    
    # Stop bot
    clear_queue(interaction.guild.id)
    voice_client.stop()
    await interaction.response.send_message("Playback stopped!", ephemeral=True, delete_after=3.0)
    print(f"{interaction.user.name} - Playback stopped")

@bot.slash_command(name="skip", description="Skip YouTube audio.", guild_ids=GUILD_IDS)
async def skip_youtube(interaction: nextcord.Interaction):
    voice_client = nextcord.utils.get(bot.voice_clients, guild=interaction.guild)

    # Check if bot/user is/isn't in a voice channel or in same voice channel
    if not await validate_voice(interaction, voice_client): return
    
    # Skip YouTube audio
    voice_client.stop()
    await interaction.response.send_message("Skipped!", ephemeral=True, delete_after=3.0)
    print(f"{interaction.user.name} - Skipped video")

@bot.slash_command(name="clear", description="Clear YouTube video queue.", guild_ids=GUILD_IDS)
async def clear_youtube_queue(interaction: nextcord.Interaction, index: int = None):
    if index is None:
        clear_queue(interaction.guild.id)
        await interaction.response.send_message("Queue cleared!", ephemeral=True, delete_after=3.0)
        print(f"{interaction.user.name} - Cleared queue")
    else:
        # Remove specific song at index (starting at 1)
        success = remove_from_queue(interaction.guild.id, index)
        if success:
            await interaction.response.send_message(f"Removed song #{index} from queue!", ephemeral=True, delete_after=3.0)
            print(f"{interaction.user.name} - Removed song #{index} from queue")
        else:
            await interaction.response.send_message("Invalid index!", ephemeral=True, delete_after=3.0)
            print(f"{interaction.user.name} - Failed to remove song from queue (invalid index)")

@bot.slash_command(name="queue", description="View YouTube video queue.", guild_ids=GUILD_IDS)
async def list_youtube_queue(interaction: nextcord.Interaction):
    queue_list = list_queue(interaction.guild.id)
    await interaction.response.send_message(queue_list, ephemeral = True)
    print(f"{interaction.user.name} - Viewed queue")

# Run bot
bot.run(TOKEN)