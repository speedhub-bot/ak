# Complete Discord.py Bot Code
import discord
from discord.ext import commands

# Define intents
intents = discord.Intents.default()
intents.messages = True
intents.guilds = True

# Create bot instance
bot = commands.Bot(command_prefix='!', intents=intents)

# Queue functionality
class Queue:
    def __init__(self):
        self.items = []

    def enqueue(self, item):
        self.items.append(item)

    def dequeue(self):
        return self.items.pop(0) if self.items else None

    def size(self):
        return len(self.items)

queue = Queue()

# Checker functionality
@bot.command()
async def check(ctx):
    await ctx.send('Checker is active!')

# Admin commands
@bot.command()
@commands.has_permissions(administrator=True)
async def admin_command(ctx):
    await ctx.send('This is an admin command.')

# User management
@bot.command()
async def user_info(ctx, member: discord.Member = None):
    member = member or ctx.author
    await ctx.send(f'User: {member.name}, ID: {member.id}')

# Queue command
@bot.command()
async def queue(ctx, *, item):
    queue.enqueue(item)
    await ctx.send(f'Item added to queue: {item}')

@bot.command()
async def dequeue(ctx):
    item = queue.dequeue()
    if item:
        await ctx.send(f'Item removed from queue: {item}')
    else:
        await ctx.send('Queue is empty.')

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user} (ID: {bot.user.id})')
    print('------')
    await bot.change_presence(activity=discord.Game(name='with the bot!'))

# Run the bot
bot.run('YOUR_TOKEN_HERE')