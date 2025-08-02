from nextcord import FFmpegPCMAudio
import asyncio
import yt_dlp

def get_youtube_audio(url):
    ydl_opts = {
            'format': 'bestaudio/best',
            'quiet': True,
            'no_warnings': True,
            'default_search': 'auto',
            'noplaylist': True,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        audio_url = info['url']
        title = info.get('title', 'Unknown title')

    source = FFmpegPCMAudio(audio_url)
    return source, title

queues = {} # {guild_id: [(source, title), ...]}

def queue_is_empty(guild_id: int) -> bool:
    return guild_id not in queues or len(queues[guild_id]) == 0

def add_to_queue(guild_id: int, source, title):
    if guild_id not in queues:
        queues[guild_id] = []
    queues[guild_id].append((source, title))

def clear_queue(guild_id: int):
    if guild_id in queues:
        queues[guild_id].clear()

def remove_from_queue(guild_id: int, index: int):
    if guild_id not in queues:
        return False
    queue = queues[guild_id]
    if index < 1 or index > len(queue):
        return False
    queue.pop(index - 1)
    return True

def list_queue(guild_id: int):
    if queue_is_empty:
        return "Queue is empty!"
    else:
        lines = [f"{i+1}. {title}" for i, (_, title) in enumerate(queues[guild_id])]
        return "**Queue:**\n" + "\n".join(lines)

async def play_next_in_queue(voice_client, guild_id: int):
    if guild_id not in queues or not queues[guild_id]:
        return  # Nothing to play
    
    source, title = queues[guild_id].pop(0)

    def after_playing(error):
        if error:
            print(f"Playback error: {error}")
        else:
            coro = play_next_in_queue(voice_client, guild_id)
            fut = asyncio.run_coroutine_threadsafe(coro, voice_client.loop)
            fut.result()    # Wait for result or catch error
    
    voice_client.play(source, after=after_playing)