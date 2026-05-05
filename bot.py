import discord
from discord.ext import commands
import os
from dotenv import load_dotenv
from elevenlabs.client import ElevenLabs
from elevenlabs import VoiceSettings
import asyncio
import io
import datetime

# Load environment variables
load_dotenv()

# Bot configuration
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
ELEVENLABS_API_KEY = os.getenv('ELEVENLABS_API_KEY')
PREFIX = os.getenv('PREFIX', '!')  # Default prefix is ! but can be changed

# Initialize bot with prefix
intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True
intents.guilds = True
intents.members = True

bot = commands.Bot(command_prefix=PREFIX, intents=intents)

# Initialize ElevenLabs client
eleven_client = None
if ELEVENLABS_API_KEY:
    eleven_client = ElevenLabs(api_key=ELEVENLABS_API_KEY)

# Store connected voice clients
voice_clients = {}
voice_channels = {}

@bot.event
async def on_ready():
    print(f'👉{bot.user} is online and ready!')
    print(f'👉Bot ID: {bot.user.id}')
    print(f'👉Connected to {len(bot.guilds)} guilds')
    print(f'👉Command Prefix: {PREFIX}')
    
    # Set bot status
  #  await bot.change_presence(activity=discord.Activity(
     #   type=discord.ActivityType.listening, 
    #    name=f"{PREFIX}help for commands"
  #  ))

@bot.event
async def on_voice_state_update(member, before, after):
    """Handle voice state updates - greet members when they join VCs"""
    
    # Ignore the bot itself
    if member.bot:
        return
    
    # Check if member joined a voice channel that the bot is in
    if after.channel is not None:
        # Get the bot's voice client in this guild
        guild_id = member.guild.id
        
        if guild_id in voice_clients:
            bot_vc = voice_clients[guild_id]
            
            # Check if the member joined the same channel as the bot
            if after.channel == bot_vc.channel:
                vc_name = after.channel.name
                member_name = member.display_name
                
                # Create greeting message
                greeting_text = f"{member_name} has joined {vc_name} VC"
                print(f"Greeting: {greeting_text}")
                
                # Play greeting using ElevenLabs
                await play_greeting(guild_id, greeting_text)

async def play_greeting(guild_id, text):
    """Generate and play greeting using ElevenLabs API"""
    try:
        if not eleven_client:
            print("❌ ElevenLabs client not initialized")
            return
        
        # Generate audio from text using new SDK
        audio_generator = eleven_client.text_to_speech.convert(
            voice_id="21m00Tcm4TlvDq8ikWAM",  # Default ElevenLabs voice (Rachel)
            output_format="mp3_44100_128",
            text=text,
            model_id="eleven_multilingual_v2",
            voice_settings=VoiceSettings(
                stability=0.5,
                similarity_boost=0.75,
                style=0.0,
                use_speaker_boost=True
            )
        )
        
        # Convert generator to bytes
        audio_bytes = b''.join(audio_generator)
        
        # Save audio to BytesIO
        audio_file = io.BytesIO(audio_bytes)
        audio_file.seek(0)
        
        # Play audio in voice channel
        if guild_id in voice_clients:
            vc = voice_clients[guild_id]
            
            if vc.is_playing():
                vc.stop()
            
            # Save temp file and create audio source
            temp_file = f"temp_audio_{guild_id}.mp3"
            with open(temp_file, "wb") as f:
                f.write(audio_bytes)
            
            # Create audio source from file
            source = discord.FFmpegPCMAudio(temp_file)
            source = discord.PCMVolumeTransformer(source)
            source.volume = 1.0
            
            vc.play(source, after=lambda e: cleanup_temp_file(temp_file))
            
    except Exception as e:
        print(f"❌ Error playing greeting: {e}")

def cleanup_temp_file(file_path):
    """Clean up temporary audio files"""
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
    except:
        pass

@bot.command(name='vc')
async def join_vc(ctx, channel_id: int = None):
    """Join a voice channel by ID"""
    try:
        # Get the voice channel
        if channel_id:
            channel = bot.get_channel(channel_id)
        else:
            # If no channel ID provided, join author's channel
            if ctx.author.voice:
                channel = ctx.author.voice.channel
            else:
                await ctx.send("❌ Please provide a channel ID or join a voice channel first!")
                return
        
        if not channel:
            await ctx.send("❌ Channel not found!")
            return
        
        if not isinstance(channel, discord.VoiceChannel):
            await ctx.send("❌ This is not a voice channel!")
            return
        
        # Disconnect if already connected in this guild
        if ctx.guild.id in voice_clients:
            await voice_clients[ctx.guild.id].disconnect()
        
        # Connect to the voice channel
        vc = await channel.connect()
        voice_clients[ctx.guild.id] = vc
        voice_channels[channel.id] = channel.name
        
        await ctx.send(f"✅ Joined voice channel: **{channel.name}**")
        print(f"🎙️ Bot joined VC: {channel.name} in {ctx.guild.name}")
        
    except Exception as e:
        await ctx.send(f"❌ Error joining VC: {str(e)}")
        print(f"❌ Error: {e}")

@bot.command(name='dvc')
async def leave_vc(ctx):
    """Leave the current voice channel"""
    try:
        if ctx.guild.id in voice_clients:
            vc = voice_clients[ctx.guild.id]
            channel_name = vc.channel.name if vc.channel else "Unknown"
            
            await vc.disconnect()
            del voice_clients[ctx.guild.id]
            
            await ctx.send(f"Left voice channel: **{channel_name}**")
            print(f"Bot left VC: {channel_name} in {ctx.guild.name}")
        else:
            await ctx.send("❌ I'm not in any voice channel!")
    except Exception as e:
        await ctx.send(f"❌ Error leaving VC: {str(e)}")

@bot.command(name='cv')
async def check_voice(ctx):
    """Check if bot voice is working"""
    try:
        if ctx.guild.id not in voice_clients:
            await ctx.send("❌ I'm not in any voice channel! Use {0}vc to join one.".format(PREFIX))
            return
        
        # Get the author's name
        member_name = ctx.author.display_name
        
        # Test message
        test_text = f"Voice check successful! {member_name}, your bot is working perfectly."
        
        await ctx.send(f"Playing voice test in VC...")
        
        # Play test message
        await play_greeting(ctx.guild.id, test_text)
        
    except Exception as e:
        await ctx.send(f"❌ Error checking voice: {str(e)}")

@bot.command(name='api')
async def check_api(ctx):
    """Check ElevenLabs API status"""
    try:
        if not eleven_client:
            await ctx.send("❌ ElevenLabs client is not initialized. Check your API key.")
            return
        
        # Get user info and subscription
        user_info = eleven_client.users.get()
        
        embed = discord.Embed(
            title="ElevenLabs API Status",
            color=discord.Color.green(),
            timestamp=datetime.datetime.now()
        )
        
        embed.add_field(
            name="v4.1",
            value="Fine",
            inline=True
        )
        
        embed.add_field(
            name="User",
            value=f"{user_info.first_name} {user_info.last_name or ''}",
            inline=True
        )
        
        embed.add_field(
            name="Email",
            value=user_info.email or "||Private Cannot Show||",
            inline=True
        )
        
        embed.add_field(
            name="Subscription",
            value=f"Tier: {user_info.subscription.tier}\nStatus: {user_info.subscription.status}",
            inline=True
        )
        
        embed.add_field(
            name="Characters Used",
            value=f"{user_info.subscription.character_count}/{user_info.subscription.character_limit}",
            inline=True
        )
        
        embed.add_field(
            name="Voices Available",
            value=f"{user_info.subscription.voice_limit} voices",
            inline=True
        )
        
        embed.set_footer(text="ElevenLabs API")
        
        await ctx.send(embed=embed)
        
    except Exception as e:
        embed = discord.Embed(
            title="❌ ElevenLabs API Error",
            description=f"```{str(e)}```",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed)

@bot.command(name='help')
async def help_command(ctx):
    """Show all bot commands"""
    embed = discord.Embed(
        title="Voice Bot Commands",
        description=f"Prefix: `{PREFIX}`\nHere are all available commands:",
        color=discord.Color.blue()
    )
    
    commands_list = {
        f"{PREFIX}vc <channel_id>": "Join a voice channel by ID. Bot will stay 24/7",
        f"{PREFIX}dvc": "Leave the current voice channel",
        f"{PREFIX}cv": "Check if bot voice is working (test command)",
        f"{PREFIX}api": "Show ElevenLabs API status and details",
        f"{PREFIX}help": "Show this help message"
    }
    
    for cmd, desc in commands_list.items():
        embed.add_field(
            name=cmd,
            value=desc,
            inline=False
        )
    
    embed.add_field(
        name="Features",
        value="• Automatically greets members when they join VC\n"
              "• 24/7 stay in voice channel\n"
              "• ElevenLabs AI voice integration\n"
              "• Real-time voice state monitoring",
        inline=False
    )
    
    embed.set_footer(text=f"Prefix: {PREFIX} • Use commands in any text channel")
    
    await ctx.send(embed=embed)

@bot.command(name='prefix')
@commands.has_permissions(administrator=True)
async def change_prefix(ctx, new_prefix: str):
    """Change the bot prefix (Admin only)"""
    if len(new_prefix) > 5:
        await ctx.send("❌ Prefix must be 5 characters or less!")
        return
    
    global PREFIX
    old_prefix = PREFIX
    PREFIX = new_prefix
    bot.command_prefix = new_prefix
    
    await ctx.send(f"✅ Prefix changed from `{old_prefix}` to `{new_prefix}`")

# Error handling
@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        await ctx.send(f"❌ Command not found! Use `{PREFIX}help` to see available commands.")
    elif isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ You don't have permission to use this command!")
    else:
        await ctx.send(f"❌ An error occurred: {str(error)}")
        print(f"Error: {error}")

# Run the bot
if __name__ == "__main__":
    if not DISCORD_TOKEN:
        print("❌ Discord token not found! Check your .env file.")
    else:
        print(f"🚀 Starting bot with prefix: {PREFIX}")
        bot.run(DISCORD_TOKEN)
