import discord
from discord.ext import commands, tasks
from discord import app_commands
from discord.app_commands import checks, MissingPermissions, Choice
import time

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
        name="myinvitelist",
        description="List your active invited links."
    )
    async def command_invites_myinvitelist(
        self,
        interaction: discord.Interaction,
    ) -> None:
        await interaction.response.send_message(f"{interaction.user.mention} checking your invited code list ...", ephemeral=True)
        try:
            if not interaction.guild.me.guild_permissions.manage_guild:
                await interaction.edit_original_response(
                    content=f"{interaction.user.mention}, sorry! Bot doesn't have permission manage_guild and can't check that!"
                )
                return
            else:
                guild_invites = await interaction.guild.invites()
                list_invites = []
                for invite in guild_invites:
                    if invite.inviter.id == interaction.user.id:
                        list_invites.append("[{}]({}) - uses {}, max uses {}, created <t:{}:f>".format(invite.code, invite.url, invite.uses, "N/A" if invite.max_uses == 0 else invite.max_uses, int(invite.created_at.timestamp())))
                if len(list_invites) > 0:
                    list_inv = "\n".join(list_invites)
                    await interaction.edit_original_response(
                        content=f"{interaction.user.mention}, your invite links ({str(len(list_invites))}):\n{list_inv}"
                    )
                else:
                    await interaction.edit_original_response(
                        content=f"{interaction.user.mention}, you don't have any invited link!"
                    )
        except Exception:
            traceback.print_exc(file=sys.stdout)


    @invites_group.command(
        name="leaderboard",
        description="Check invite leaderboard."
    )
    @app_commands.describe(duration='Select duration')
    @app_commands.choices(duration=[
        Choice(name='1d', value=86400),
        Choice(name='7d', value=604800),
        Choice(name='14d', value=1209600),
        Choice(name='30d', value=2592000),
        Choice(name='all', value=-1),
    ])
    async def command_invites_leaderboard(
        self,
        interaction: discord.Interaction,
        duration: Choice[int]
    ) -> None:
        try:
            await interaction.response.send_message(f"{interaction.user.mention} invite leaderboard checking...")
            get_list = await self.utils.invite_top_list(str(interaction.guild.id), duration.value)
            if len(get_list) == 0:
                await interaction.edit_original_response(
                    content=f"{interaction.user.mention}, there's no record yet for this Guild "\
                        f"**{interaction.guild.name}** within that duration or the recorded guest(s) left."
                )
            else:
                since_time = ""
                if duration.value > 0:
                    since_time = " since <t:{}:f>".format(int(time.time()) - duration.value)
                embed = discord.Embed(
                    title="Invite Leaderboard",
                    description="Top inviter(s) for {}{}!".format(interaction.guild.name, since_time),
                    timestamp=datetime.now()
                )
                list_comers = []
                max_list = 50
                for c, i in enumerate(get_list, start=1):
                    list_comers.append("<@{}> - {}".format(i['invited_by_user_id'], i['num_invites']))
                    if c >= max_list:
                        break
                if len(get_list) > max_list:
                    list_comers.append("and {} other(s)...".format(len(get_list) - max_list))
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
                if interaction.guild.icon:
                    embed.set_thumbnail(url=str(interaction.guild.icon))
                await interaction.edit_original_response(
                    content=None, embed=embed
                )
        except Exception:
            traceback.print_exc(file=sys.stdout)

    @commands.Cog.listener()
    async def on_invite_create(self, invite):
        guild = invite.guild
        if not invite.guild.me.guild_permissions.manage_guild:
            await self.utils.log_to_channel(
                self.bot.config['discord']['log_channel'],
                f"Bot doesn't have permission `manage_guild` in {guild.id} / {guild.name}."
            )
            if str(guild.id) in self.bot.log_channel_guild:
                await self.utils.log_to_channel(
                    self.bot.log_channel_guild[str(guild.id)],
                    f"Bot doesn't have permission `manage_guild` in {guild.id} / {guild.name}. Bot can't check the invited codes and list."
                )
        else:
            await self.set_invites(invite.guild)
            await self.utils.log_to_channel(
                self.bot.config['discord']['log_channel'],
                f"New invite created for Guild **{invite.guild.name}** by {invite.inviter.mention}. Code: `{invite.code}`."
            )
            await self.utils.create_invite(
                str(invite.inviter.id), str(invite.guild.id), invite.code, invite.url,
                invite.max_uses, int(invite.expires_at.timestamp()), int(invite.created_at.timestamp())
            )
            if str(invite.guild.id) in self.bot.log_channel_guild:
                await self.utils.log_to_channel(
                    self.bot.log_channel_guild[str(invite.guild.id)],
                    f"{invite.inviter.mention} / `{invite.inviter.id}` created a new invite code `{invite.code}`."
                )

    @commands.Cog.listener()
    async def on_invite_delete(self, invite):
        guild = invite.guild
        if not invite.guild.me.guild_permissions.manage_guild:
            await self.utils.log_to_channel(
                self.bot.config['discord']['log_channel'],
                f"Bot doesn't have permission `manage_guild` in {guild.id} / {guild.name}."
            )
            if str(guild.id) in self.bot.log_channel_guild:
                await self.utils.log_to_channel(
                    self.bot.log_channel_guild[str(guild.id)],
                    f"Bot doesn't have permission `manage_guild` in {guild.id} / {guild.name}. Bot can't check the invited codes and list."
                )
        else:
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
            try:
                invs_after = await guild.invites()
                self.invites_dict[guild.id] = [tuple((invite.code, invite.uses)) for invite in invs_after]
            except Exception:
                traceback.print_exc(file=sys.stdout)
            msg = f"{member.mention} / {member.name} left guild **{guild.name}**."
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
            # after
            invs_before = self.invites_dict.get(guild.id)
            invs_after = await guild.invites()
            self.invites_dict[guild.id] = [tuple((invite.code, invite.uses)) for invite in invs_after]
            done = False
            for invite in invs_after:
                try:
                    for invite_dict in invs_before:
                        if invite_dict[0] == invite.code and int(invite.uses) > invite_dict[1]:
                            done = True
                            # channel = guild.system_channel
                            account_created =  int(member.created_at.timestamp())
                            msg = f"{member.mention} / {member.name} account created <t:{str(account_created)}:R> has joined. Invited link by {invite.inviter.mention}."
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
                if done is True:
                    break
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
