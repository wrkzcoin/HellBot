import sys, traceback

import discord
from discord import app_commands
from discord.ext import commands


class Core(commands.Cog):
    """Houses core commands & listeners for the bot"""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot: commands.Bot = bot

    @app_commands.command(
        name='help',
        description="Show help"
    )
    async def slash_help(
        self, interaction: discord.Interaction
    ) -> None:
        """ /help """
        basic_help_namefilter = """
Manage namefilter list with sub-commands `/namefilter [list|add|del|apply|test]`.
Requires Discord Member with ban/kick permission.
"""
        basic_help_ignore = """
Manage ignore list with sub-commands `/ignore [addrole|delrole|adduser|deluser|list]`.
Requires Discord Member with ban/kick permission.
"""

        basic_help_messagefilter = """
Manage message filter list with sub-commands `/messagefilter [list|add|del|on|off]`.
Requires Discord Member with manage-messages permission.
"""

        basic_help_other = """
Other commands such as `/donate`, `/about` and `/logchan`.
"""

        notes = """
By default, each guild has a limit as below:
* maximum ignored users: 20
* maximum ignore roles: 5
* max added regex: 5
You can request for more, just join our supported guild and request manually.
"""
        await interaction.response.send_message(f"{interaction.user.mention} loading /help...")
        try:
            page = discord.Embed(
                title=f"{self.bot.user.name} Help Menu",
                description="Thank you for using HellBot! Kindly consider donation if you like it with `/donate`",
                color=discord.Color.blue(),
            )

            page.add_field(
                name="/namefilter",
                value=basic_help_namefilter,
                inline=False
            )

            page.add_field(
                name="/ignore",
                value=basic_help_ignore,
                inline=False
            )

            page.add_field(
                name="/messagefilter",
                value=basic_help_messagefilter,
                inline=False
            )

            page.add_field(
                name="Others",
                value=basic_help_other,
                inline=False
            )

            page.add_field(
                name="Notes",
                value=notes,
                inline=False
            )

            page.set_thumbnail(url=self.bot.user.display_avatar)
            page.set_footer(text=f"Requested by {interaction.user.name}#{interaction.user.discriminator}")
            await interaction.edit_original_response(content=None, embed=page)
        except Exception:
            traceback.print_exc(file=sys.stdout)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Core(bot))
