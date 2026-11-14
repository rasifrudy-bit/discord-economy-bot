import os
import random
import sqlite3
import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
DB = "economy.db"

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

def db():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    return con

def init_db():
    con = db()
    con.execute("""CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        balance INTEGER NOT NULL DEFAULT 0,
        xp INTEGER NOT NULL DEFAULT 0,
        last_daily INTEGER NOT NULL DEFAULT 0,
        last_work INTEGER NOT NULL DEFAULT 0
    )""")
    con.commit()
    con.close()

def ensure_user(user_id):
    con = db()
    con.execute("INSERT OR IGNORE INTO users(user_id) VALUES(?)", (user_id,))
    con.commit()
    con.close()

def get_user(user_id):
    ensure_user(user_id)
    con = db()
    row = con.execute("SELECT * FROM users WHERE user_id=?", (user_id,)).fetchone()
    con.close()
    return row

def add_balance(user_id, amount):
    ensure_user(user_id)
    con = db()
    con.execute("UPDATE users SET balance=balance+? WHERE user_id=?", (amount, user_id))
    con.commit()
    con.close()

def add_xp(user_id, amount):
    ensure_user(user_id)
    con = db()
    con.execute("UPDATE users SET xp=xp+? WHERE user_id=?", (amount, user_id))
    con.commit()
    con.close()

def cooldown_text(seconds):
    m, s = divmod(seconds, 60)
    h, m = divmod(m, 60)
    if h:
        return f"{h} jam {m} menit"
    return f"{m} menit {s} detik"

@bot.event
async def on_ready():
    init_db()
    try:
        synced = await bot.tree.sync()
        print(f"Logged in as {bot.user} | synced {len(synced)} commands")
    except Exception as e:
        print("Sync error:", e)

@bot.tree.command(name="balance", description="Cek saldo Coin dan XP")
async def balance(interaction: discord.Interaction):
    row = get_user(interaction.user.id)
    await interaction.response.send_message(
        f"💰 **{interaction.user.display_name}**\n"
        f"🪙 Coin: **{row['balance']:,}**\n"
        f"⭐ XP: **{row['xp']:,}**"
    )

@bot.tree.command(name="daily", description="Ambil hadiah harian")
async def daily(interaction: discord.Interaction):
    import time
    row = get_user(interaction.user.id)
    now = int(time.time())
    remaining = 86400 - (now - row["last_daily"])
    if remaining > 0:
        await interaction.response.send_message(
            f"⏳ Daily belum tersedia. Coba lagi dalam **{cooldown_text(remaining)}**.",
            ephemeral=True
        )
        return
    reward = random.randint(15000)
    con = db()
    con.execute("UPDATE users SET balance=balance+?, last_daily=? WHERE user_id=?",
                (reward, now, interaction.user.id))
    con.commit(); con.close()
    await interaction.response.send_message(f"🎁 Kamu mendapatkan **🪙 {reward:,} Coin** dari daily!")

@bot.tree.command(name="work", description="Bekerja untuk mendapatkan Coin")
async def work(interaction: discord.Interaction):
    import time
    row = get_user(interaction.user.id)
    now = int(time.time())
    remaining = 600 - (now - row["last_work"])
    if remaining > 0:
        await interaction.response.send_message(
            f"⏳ Kamu masih lelah. Coba lagi dalam **{cooldown_text(remaining)}**.",
            ephemeral=True
        )
        return
    jobs = [
        ("developer", 35000, 68900),
        ("designer", 13800, 27000),
        ("builder", 9450, 16800),
        ("merchant", 5390, 24600),
        ("moderator", 11000, 26000),
    ]
    job, lo, hi = random.choice(jobs)
    reward = random.randint(lo, hi)
    con = db()
    con.execute("UPDATE users SET balance=balance+?, xp=xp+?, last_work=? WHERE user_id=?",
                (reward, 25, now, interaction.user.id))
    con.commit(); con.close()
    await interaction.response.send_message(
        f"💼 Kamu bekerja sebagai **{job}** dan mendapatkan **🪙 {reward:,} Coin** + **25 XP**!"
    )

@bot.tree.command(name="give", description="Kirim Coin ke user lain")
@app_commands.describe(member="Penerima", amount="Jumlah Coin")
async def give(interaction: discord.Interaction, member: discord.Member, amount: int):
    if member.id == interaction.user.id:
        await interaction.response.send_message("❌ Tidak bisa mengirim Coin ke diri sendiri.", ephemeral=True); return
    if amount <= 0:
        await interaction.response.send_message("❌ Jumlah harus lebih dari 0.", ephemeral=True); return
    sender = get_user(interaction.user.id)
    if sender["balance"] < amount:
        await interaction.response.send_message("❌ Saldo Coin kamu tidak cukup.", ephemeral=True); return
    add_balance(interaction.user.id, -amount)
    add_balance(member.id, amount)
    await interaction.response.send_message(
        f"💸 {interaction.user.mention} mengirim **🪙 {amount:,} Coin** kepada {member.mention}."
    )

@bot.tree.command(name="leaderboard", description="Lihat 10 pengguna dengan Coin terbanyak")
async def leaderboard(interaction: discord.Interaction):
    con = db()
    rows = con.execute("SELECT user_id,balance,xp FROM users ORDER BY balance DESC LIMIT 10").fetchall()
    con.close()
    if not rows:
        await interaction.response.send_message("Belum ada data."); return
    lines = []
    for i, r in enumerate(rows, 1):
        user = interaction.guild.get_member(r["user_id"]) if interaction.guild else None
        name = user.display_name if user else f"User {r['user_id']}"
        lines.append(f"**{i}.** {name} — 🪙 {r['balance']:,}")
    await interaction.response.send_message("🏆 **COIN LEADERBOARD**\n" + "\n".join(lines))

@bot.tree.command(name="slot", description="Minigame slot gratis untuk mendapatkan XP")
async def slot(interaction: discord.Interaction):
    symbols = ["🍒","🍋","🍊","🔔","⭐","💎"]
    result = [random.choice(symbols) for _ in range(3)]
    if len(set(result)) == 1:
        xp = 100
        msg = "🎉 JACKPOT! +100 XP"
    elif len(set(result)) == 2:
        xp = 35
        msg = "✨ MATCH! +35 XP"
    else:
        xp = 10
        msg = "🎰 Coba lagi! +10 XP"
    add_xp(interaction.user.id, xp)
    await interaction.response.send_message(f"🎰 **{' | '.join(result)}**\n{msg}")

@bot.tree.command(name="coinflip", description="Tebak Heads atau Tails untuk mendapatkan XP")
@app_commands.describe(choice="Pilih heads atau tails")
@app_commands.choices(choice=[
    app_commands.Choice(name="Heads", value="heads"),
    app_commands.Choice(name="Tails", value="tails"),
])
async def coinflip(interaction: discord.Interaction, choice: app_commands.Choice[str]):
    result = random.choice(["heads", "tails"])
    if choice.value == result:
        xp = 30
        msg = f"🪙 Hasil: **{result.title()}** — benar! +{xp} XP"
    else:
        xp = 5
        msg = f"🪙 Hasil: **{result.title()}** — belum tepat. +{xp} XP"
    add_xp(interaction.user.id, xp)
    await interaction.response.send_message(msg)

@bot.tree.command(name="mines", description="Cari bonus XP dalam grid 3x3")
async def mines(interaction: discord.Interaction):
    safe = random.randint(0, 8)
    cells = []
    for i in range(9):
        cells.append("💎" if i == safe else "⬜")
    add_xp(interaction.user.id, 25)
    await interaction.response.send_message(
        "💣 **MINES**\n" + " ".join(cells[:3]) + "\n" +
        " ".join(cells[3:6]) + "\n" + " ".join(cells[6:]) +
        "\n💎 Kamu menemukan bonus! +25 XP"
    )

@bot.tree.command(name="addmoney", description="Admin: tambah Coin ke user")
@app_commands.describe(member="Target", amount="Jumlah Coin")
@app_commands.default_permissions(administrator=True)
async def addmoney(interaction: discord.Interaction, member: discord.Member, amount: int):
    if amount <= 0:
        await interaction.response.send_message("❌ Jumlah harus lebih dari 0.", ephemeral=True); return
    add_balance(member.id, amount)
    await interaction.response.send_message(f"✅ Menambahkan **🪙 {amount:,} Coin** ke {member.mention}.")

@bot.tree.command(name="removemoney", description="Admin: kurangi Coin user")
@app_commands.describe(member="Target", amount="Jumlah Coin")
@app_commands.default_permissions(administrator=True)
async def removemoney(interaction: discord.Interaction, member: discord.Member, amount: int):
    if amount <= 0:
        await interaction.response.send_message("❌ Jumlah harus lebih dari 0.", ephemeral=True); return
    add_balance(member.id, -amount)
    await interaction.response.send_message(f"✅ Mengurangi **🪙 {amount:,} Coin** dari {member.mention}.")

init_db()
if not TOKEN:
    raise RuntimeError("DISCORD_TOKEN belum diisi di file .env")
bot.run(TOKEN)
