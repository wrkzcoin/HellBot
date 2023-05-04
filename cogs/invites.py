import discord
from discord.ext import commands, tasks
from discord import app_commands
from discord.app_commands import checks, MissingPermissions

import traceback, sys
from datetime import datetime
from cogs.utils import check_regex
from cogs.utils import Utils, chunks

# Portional stolen from: https://github.com/llenax/discordpy-invite-tracker/blob/main/client.py

# Cog class
class Invites(commands.Cog):

    def __init__(self, bot: commands.Bot) -> None:
        self.bot: commands.Bot = bot
        self.utils = Utils(bot)
        self.invites_dict = {} # Store

    async def set_invites(self, guild):
        if guild.me.guild_permissions.manage_guild:
            guild_invites = await guild.invites()
            self.invites_dict[guild.id] = [tuple((invite.code, invite.uses)) for invite in guild_invites]
        else:
            await self.utils.log_to_channel(
                self.bot.config['discord']['log_channel'],
                f"Bot doesn't have permission `manage_guild` in {guild.id} / {guild.name}."
            )
            if str(guild.id) in self.bot.log_channel_guild:
                await self.utils.log_to_channel(
                    self.bot.log_channel_guild[str(guild.id)],
                    f"Bot doesn't have permission `manage_guild` in {guild.id} / {guild.name}. Bot can't check the invited codes and list."
                )

    invites_group = app_commands.Group(name="invites", guild_only=True, description="Invite's command list.")

    @invites_group.command(
        name="leaderboard",
        description="Check invite leaderboard."
    )
    async def command_invites_leaderboard(
        self,
        interaction: discord.Interaction,
    ) -> None:
        try:
            await interaction.response.send_message(f"{interaction.user.mention} invite leaderboard checking...")
            get_list = await self.utils.invite_top_list(str(interaction.guild.id))
            if len(get_list) == 0:
                await interaction.edit_original_response(
                    content=f"{interaction.user.mention}, there's no record yet for this Guild **{interaction.guild.name}**."
                )
            else:
                embed = discord.Embed(
                    title="Invite Leaderboard",
                    description="Top inviter for {}!".format(interaction.guild.name),
                    timestamp=datetime.now()
                )
                list_comers = []
                for i in get_list:
                    list_comers.append("<@{}> - {}".format(i['invited_by_user_id'], i['num_invites']))
                embed.add_field(
                    name="TOP INVITER(s)",
                    value="{}".format("\n".join(list_comers)),
                    inline=False
                )
                embed.set_footer(
                    text="Rquested by {}".format(interaction.user.name),
                    icon_url=interaction.user.display_avatar
                )
                embed.set_author(name=self.bot.user.name, icon_url=self.bot.user.display_avatar)
                await interaction.edit_original_response(
                    content=None, embed=embed
                )
        except Exception:
            traceback.print_exc(file=sys.stdout)

    @commands.Cog.listener()
    async def on_invite_create(self, invite):
        await self.set_invites(invite.guild)
        await self.utils.log_to_channel(
            self.bot.config['discord']['log_channel'],
            f"New invite created for Guild **{invite.guild.name}** by {invite.inviter.mention}. Code: `{invite.code}`."
        )
        if str(invite.guild.id) in self.bot.log_channel_guild:
            await self.utils.log_to_channel(
                self.bot.log_channel_guild[str(invite.guild.id)],
                f"{invite.inviter.mention} / `{invite.inviter.id}` created a new invite code `{invite.code}`."
            )

    @commands.Cog.listener()
    async def on_invite_delete(self, invite):
        await self.set_invites(invite.guild)
        await self.utils.log_to_channel(
            self.bot.config['discord']['log_channel'],
            f"Delete an invite from Guild **{invite.guild.name}** by {invite.inviter.mention}. Code: `{invite.code}`."
        )
        if str(invite.guild.id) in self.bot.log_channel_guild:
            await self.utils.log_to_channel(
                self.bot.log_channel_guild[str(invite.guild.id)],
                f"Invite link removed. Code: `{invite.code}`."
            )

    @commands.Cog.listener()
    async def on_member_remove(self, member):
        if not member.bot:
            guild = member.guild
            msg = f"{member.mention} left guild **{guild.name}**."
            if hasattr(guild, "system_channel") and guild.system_channel:
                try:
                    channel = guild.system_channel
                    await channel.send(msg)
                except Exception:
                    traceback.print_exc(file=sys.stdout)
            # delete from DB
            await self.utils.delete_member_left(str(guild.id), str(member.id))

    @commands.Cog.listener()
    async def on_member_join(self, member):
        guild = member.guild
        if not guild.me.guild_permissions.manage_guild:
            await self.utils.log_to_channel(
                self.bot.config['discord']['log_channel'],
                f"{member.name} / `{member.id}` join {member.guild.id} / {member.guild.name} but I have no permission for manage_guild to check invite."
            )
            return
        if not member.bot:
            guild_invites = await guild.invites()
            for invite in guild_invites:
                try:
                    for invite_dict in self.invites_dict.get(guild.id):
                        if invite_dict[0] == invite.code:
                            # channel = guild.system_channel
                            account_created =  int(member.created_at.timestamp())
                            msg = f"{member.mention} account created <t:{str(account_created)}:R> has joined. Invited link by {invite.inviter.mention}."
                            if int(invite.uses) > invite_dict[1]:
                                print(f"{member} joined. Invited with: {invite.code} | by {invite.inviter}")
                                await self.utils.insert_new_invite(
                                    str(guild.id), guild.name, len(guild.members), str(guild.owner.id),
                                    str(invite.inviter.id), invite.code, str(member.id), account_created
                                )
                                if hasattr(guild, "system_channel") and guild.system_channel:
                                    try:
                                        channel = guild.system_channel
                                        await channel.send(msg)
                                    except Exception:
                                        traceback.print_exc(file=sys.stdout)
                                break
                except Exception:
                    traceback.print_exc(file=sys.stdout)
        else:
            await self.utils.log_to_channel(
                self.bot.config['discord']['log_channel'],
                f"{member.name} / `{member.id}` join {member.guild.id} / {member.guild.name}. It could be a Bot."
            )

    @commands.Cog.listener()
    async def on_ready(self):
        for guild in self.bot.guilds:
            await self.set_invites(guild)

    async def cog_load(self) -> None:
        if self.bot.is_ready():
            for guild in self.bot.guilds:
                await self.set_invites(guild)

    async def cog_unload(self) -> None:
        pass

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Invites(bot))
