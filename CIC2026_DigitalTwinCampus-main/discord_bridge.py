"""
Local Discord bridge for the Campus Digital Twin IFC viewer.

Discord commands can control the viewer. Room selections in the viewer
are broadcast to Discord through the configured channel.
"""

import asyncio
import os
from pathlib import Path

from aiohttp import web
from dotenv import load_dotenv

try:
    import discord
    from discord import app_commands
except ImportError:
    discord = None
    app_commands = None


load_dotenv()

PROJECT_DIR = Path(__file__).resolve().parent
WEB_DIR = PROJECT_DIR / "web-ifc"
HOST = os.getenv("HOST", "127.0.0.1")
PORT = int(os.getenv("PORT", "8080"))
BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN", "")
CHANNEL_ID = int(os.getenv("DISCORD_CHANNEL_ID", "0") or "0")
GUILD_ID = int(os.getenv("DISCORD_GUILD_ID", "0") or "0")

websockets = set()
discord_ready = asyncio.Event()


async def broadcast(message):
    disconnected = set()
    payload = None
    for ws in list(websockets):
        if ws.closed:
            disconnected.add(ws)
            continue
        if payload is None:
            import json
            payload = json.dumps(message)
        await ws.send_str(payload)
    websockets.difference_update(disconnected)


async def index(request):
    return web.FileResponse(WEB_DIR / "ifc_viewer_combined.html")


async def websocket_handler(request):
    ws = web.WebSocketResponse()
    await ws.prepare(request)
    websockets.add(ws)
    await ws.send_json({
        "type": "viewer_status",
        "botConnected": discord_ready.is_set(),
    })

    async for message in ws:
        if message.type != web.WSMsgType.TEXT:
            continue
        import json
        try:
            event = json.loads(message.data)
        except json.JSONDecodeError:
            continue

        if event.get("type") == "room_selected":
            await broadcast({
                "type": "discord_message",
                "text": "Room selected: " + event.get("roomId", "Unknown"),
            })
            if discord_ready.is_set() and discord and CHANNEL_ID:
                await post_room_to_discord(event)

    websockets.discard(ws)
    return ws


async def event_handler(request):
    try:
        event = await request.json()
    except Exception:
        return web.json_response({"error": "invalid JSON"}, status=400)
    await broadcast(event)
    return web.json_response({"ok": True})


async def health_handler(request):
    return web.json_response({
        "ok": True,
        "discordConfigured": bool(BOT_TOKEN and CHANNEL_ID),
        "discordConnected": discord_ready.is_set(),
        "viewerConnections": len(websockets),
    })


async def post_room_to_discord(event):
    channel = discord_bot.get_channel(CHANNEL_ID)
    if channel is None:
        channel = await discord_bot.fetch_channel(CHANNEL_ID)

    room = event.get("roomId", "Unknown")
    description = event.get("roomDescription", "")
    fields = []
    for label, key, suffix in (
        ("Temperature", "temperature", " °C"),
        ("CO2", "co2", " ppm"),
        ("Humidity", "humidity", " %RH"),
    ):
        value = event.get(key)
        if value is not None:
            fields.append(f"{label}: {value:.1f}{suffix}")
    if event.get("occupancy") is not None:
        fields.append("Occupancy: " + ("Occupied" if event["occupancy"] else "Vacant"))

    text = f"**3D Twin room selected:** {room}"
    if description:
        text += f"\n{description}"
    if fields:
        text += "\n" + " · ".join(fields)
    await channel.send(text)


class TwinBot(discord.Client if discord else object):
    def __init__(self):
        if discord:
            intents = discord.Intents.default()
            super().__init__(intents=intents)
            self.tree = app_commands.CommandTree(self)

    async def setup_hook(self):
        if not discord:
            return
        guild = discord.Object(id=GUILD_ID) if GUILD_ID else None

        @self.tree.command(name="twin_status", description="Show Campus Digital Twin status")
        async def twin_status(interaction):
            await interaction.response.send_message(
                f"Digital Twin relay online. Connected viewers: {len(websockets)}"
            )

        @self.tree.command(name="twin_fit", description="Fit the 3D campus model to view")
        async def twin_fit(interaction):
            await broadcast({"type": "discord_command", "command": "fit"})
            await interaction.response.send_message("Fit view command sent to the 3D viewer.")

        @self.tree.command(name="twin_panel", description="Open the 3D sensor panel")
        async def twin_panel(interaction):
            await broadcast({"type": "discord_command", "command": "sensor_panel"})
            await interaction.response.send_message("Sensor panel opened in the 3D viewer.")

        if guild:
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
        else:
            await self.tree.sync()

    async def on_ready(self):
        discord_ready.set()
        await broadcast({
            "type": "viewer_status",
            "botConnected": True,
        })
        print(f"Discord bot connected as {self.user}")


discord_bot = TwinBot() if discord else None


async def start_discord():
    if BOT_TOKEN and discord_bot:
        await discord_bot.start(BOT_TOKEN)


async def main():
    app = web.Application()
    app.router.add_get("/", index)
    app.router.add_get("/ws", websocket_handler)
    app.router.add_post("/api/event", event_handler)
    app.router.add_get("/api/health", health_handler)
    app.router.add_static("/assets/", WEB_DIR)
    app.router.add_static("/data/", PROJECT_DIR / "data")

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, HOST, PORT)
    await site.start()
    print(f"Campus Digital Twin bridge: http://localhost:{PORT}")
    print(f"Discord: {'configured' if BOT_TOKEN and CHANNEL_ID else 'not configured'}")

    tasks = []
    if BOT_TOKEN and discord_bot:
        tasks.append(asyncio.create_task(start_discord()))

    try:
        await asyncio.gather(*tasks) if tasks else await asyncio.Event().wait()
    finally:
        await runner.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
