from __future__ import annotations

from discord.ext import commands, tasks

from discord_bot_curaga.context import AppContext


class HeartbeatCog(commands.Cog):
    def __init__(self, ctx: AppContext):
        self.ctx = ctx

    async def cog_unload(self):
        if self._task_heartbeat.is_running():
            self._task_heartbeat.stop()

    @commands.Cog.listener()
    async def on_ready(self):
        if not self._task_heartbeat.is_running():
            self._task_heartbeat.start()

    @tasks.loop(minutes=10)
    async def _task_heartbeat(self):
        try:
            self.ctx.logger.info("💓 heartbeat")
        except Exception as e:
            self.ctx.logger.error(f"Heartbeat task failed: {e}")


async def setup(bot: commands.Bot, ctx: AppContext):
    await bot.add_cog(HeartbeatCog(ctx))
