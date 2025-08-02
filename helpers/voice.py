async def validate_voice(interaction, voice_client) -> bool:
    # Check if bot is not in a voice channel
    if voice_client and not voice_client.is_connected():
        await interaction.response.send_message("I am not connected to any voice channels.", ephemeral=True)
        print(f"{interaction.user.name} - Voice Validation Fail #1")
        return False
    
    # Check if user is not in a voice channel
    if not interaction.user.voice or not interaction.user.voice.channel:
        await interaction.response.send_message("You must be in a voice channel to use this command.", ephemeral=True)
        print(f"{interaction.user.name} - Voice Validation Fail #2")
        return False
    
    # Check if bot and user are in the same voice channel
    if voice_client.channel != interaction.user.voice.channel:
        await interaction.response.send_message("You must be in the same channel as the bot to use this command.", ephemeral=True)
        print(f"{interaction.user.name} - Voice Validation Fail #3")
        return False

    return True