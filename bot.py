import asyncio
from datetime import datetime
import discord
from discord.ext import commands
from flask import Flask
import gspread
from threading import Thread

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# ตั้งค่าเชื่อมต่อ Google Sheets ผ่าน Service Account
gc = gspread.service_account(filename="credentials.json")
sh = gc.open("Attendance Log")
worksheet = sh.sheet1


def save_attendance(username, user_id, action, timestamp):
  date_str = timestamp.strftime("%Y-%m-%d")
  time_str = timestamp.strftime("%H:%M:%S")

  rows = worksheet.get_all_values()

  if action == "เข้าเวร":
    # [ว่าง(Col A), Username(Col B), Date(Col C), Check-In(Col D), Check-Out(Col E), Total Time(Col F)]
    row = ["", str(username), date_str, time_str, "", ""]
    worksheet.append_row(row)
  else:
    # ค้นหาแถวตั้งแต่วันนี้ที่ชื่อตรงกัน และช่องเวลาออก (Column E) ยังว่างอยู่
    updated = False
    for idx in range(len(rows) - 1, 0, -1):
      r = rows[idx]
      # r[1] = Username (Col B), r[2] = Date (Col C), r[4] = Check-Out (Col E)
      if (
          len(r) >= 5
          and r[1] == str(username)
          and r[2] == date_str
          and r[4] == ""
      ):
        row_idx = idx + 1

        # 1. อัปเดตเวลาออกที่ Column E (คอลัมน์ที่ 5)
        worksheet.update_cell(row_idx, 5, time_str)

        # 2. คำนวณสรุปเวลาทำงานเป็น "ตัวเลขชั่วโมงเพียวๆ" เพื่อให้ Google Sheets เอาไปบวกต่อได้ทันที
        check_in_str = r[3]  # Col D
        if check_in_str:
          try:
            fmt = "%H:%M:%S"
            t_in = datetime.strptime(check_in_str, fmt)
            t_out = datetime.strptime(time_str, fmt)

            diff = t_out - t_in
            total_seconds = int(diff.total_seconds())
            if total_seconds < 0:
              total_seconds += 86400  # เผื่อกรณีข้ามวัน

            # คำนวณออกมาเป็นทศนิยมชั่วโมง (เช่น 1 ชั่วโมง 30 นาที จะได้ 1.5)
            total_hours = round(total_seconds / 3600, 2)

            # อัปเดตตัวเลขชั่วโมงลงที่ Column F (คอลัมน์ที่ 6)
            worksheet.update_cell(row_idx, 6, total_hours)
          except Exception as e:
            print(f"Error calculating time: {e}")

        updated = True
        break

    # ถ้ากดออกเวรโดยยังไม่มีประวัติเข้าเวร ให้เพิ่มแถวใหม่บันทึกเวลาออกเลย
    if not updated:
      row = ["", str(username), date_str, "", time_str, ""]
      worksheet.append_row(row)


class AttendanceView(discord.ui.View):

  def __init__(self):
    super().__init__(timeout=None)

  @discord.ui.button(
      label="🟢 เข้าเวร",
      style=discord.ButtonStyle.green,
      custom_id="check_in",
  )
  async def check_in(
      self, interaction: discord.Interaction, button: discord.ui.Button
  ):
    now = datetime.now()
    await interaction.response.send_message(
        f"✅ บันทึกเวลา **เข้าเวร** เรียบร้อยแล้วเมื่อเวลา"
        f" {now.strftime('%H:%M:%S')}",
        ephemeral=True,
    )
    await asyncio.to_thread(
        save_attendance,
        interaction.user.display_name,
        interaction.user.id,
        "เข้าเวร",
        now,
    )

  @discord.ui.button(
      label="🔴 ออกเวร", style=discord.ButtonStyle.red, custom_id="check_out"
  )
  async def check_out(
      self, interaction: discord.Interaction, button: discord.ui.Button
  ):
    now = datetime.now()
    await interaction.response.send_message(
        f"❌ บันทึกเวลา **ออกเวร** เรียบร้อยแล้วเมื่อเวลา"
        f" {now.strftime('%H:%M:%S')}",
        ephemeral=True,
    )
    await asyncio.to_thread(
        save_attendance,
        interaction.user.display_name,
        interaction.user.id,
        "ออกเวร",
        now,
    )


@bot.event
async def on_ready():
  print(f"บอทออนไลน์แล้วในชื่อ: {bot.user}")


@bot.command()
@commands.has_permissions(administrator=True)
async def setup(ctx):
  embed = discord.Embed(
      title="📌 ระบบลงเวลาเข้า-ออกเวร",
      description="กดปุ่มด้านล่างเพื่อบันทึกเวลาทำงานของคุณได้เลยครับ",
      color=discord.Color.blue(),
  )
  await ctx.send(embed=embed, view=AttendanceView())


# --- ระบบเปิดเว็บเซิร์ฟเวอร์พ่วงสำหรับ UptimeRobot คอยปลุก 24/7 ---
app = Flask('')


@app.route('/')
def home():
  return 'I am alive! Bot is running 24/7.'


def run():
  app.run(host='0.0.0.0', port=8080)


def keep_alive():
  t = Thread(target=run)
  t.start()


# รันเว็บเซิร์ฟเวอร์ควบคู่ไปกับบอท
keep_alive()

bot.run(
    "MTU0ODc3NjU5MzgxMDI2ODIzNQ.GveY3B.KJwRGKWMFa8b3MTBGd7cB00rU7-nzq1z3qaltc"
)