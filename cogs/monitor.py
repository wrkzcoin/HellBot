import discord
from discord.ext import commands, tasks
import traceback, sys
import time
import asyncio
import re
from cogs.utils import check_regex
from cogs.utils import Utils

# Cog class
class Events(commands.Cog):

    def __init__(self, bot: commands.Bot) -> None:
        self.bot: commands.Bot = bot
        self.utils = Utils(bot)

    @commands.Cog.listener()
    async def on_guild_join(self, guild):
        await self.utils.log_to_channel(
            self.bot.config['discord']['log_channel'],
            f"Bot joined a new guild `{guild.id} / {guild.name}`"
        )
        try:
            await self.utils.insert_new_guild(str(guild.id), guild.name)
            self.bot.name_filter_list[str(guild.id)] = []
            self.bot.name_filter_list_pending[str(guild.id)] = []
            self.bot.exceptional_role_id[str(guild.id)] = []
            self.bot.exceptional_user_name_id[str(guild.id)] = []
            self.bot.log_channel_guild[str(guild.id)] = None
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
            await self.utils.log_to_channel(
                self.bot.config['discord']['log_channel'],
                f"Failed to insert new guild "\
                f"`{guild.name} / {guild.id}`"
            )

    @commands.Cog.listener()
    async def on_guild_remove(self, guild):
        await self.utils.log_to_channel(
            self.bot.config['discord']['log_channel'],
            f"Bot removed from guild `{guild.id} / {guild.name}`."
        )
        try:
            await self.utils.delete_guild(str(guild.id))
            del self.bot.name_filter_list[str(guild.id)]
            del self.bot.name_filter_list_pending[str(guild.id)]
            del self.bot.exceptional_role_id[str(guild.id)]
            del self.bot.exceptional_user_name_id[str(guild.id)]
            del self.bot.log_channel_guild[str(guild.id)]
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
            await self.utils.log_to_channel(
                self.bot.config['discord']['log_channel'],
                f"Failed to delete guild "\
                f"`{guild.name} / {guild.id}`"
            )

    @commands.Cog.listener()
    async def on_member_join(self, member):
        if str(member.guild.id) in self.bot.log_channel_guild and self.bot.log_channel_guild[str(member.guild.id)]:
            # check permission bot
            check_perm = await self.utils.bot_can_kick_ban(member.guild)
            if check_perm is None:
                await self.utils.log_to_channel(
                    self.bot.config['discord']['log_channel'],
                    f"Bot failed to get permission info in guild `{member.guild.name} / {member.guild.id}`"
                )
                return
            else:
                if check_perm['kick_members'] is False or check_perm['ban_members'] is False:
                    await self.utils.log_to_channel(
                        self.bot.log_channel_guild[str(member.guild.id)],
                        f"New user `{member.name}` | {member.mention} joined but "\
                        "Bot doesn't have permission kick/ban to process next step of checking!"
                    )
            # end of check permission
            ignore = False
            # check if user in ignore list role
            if len(member.roles) > 0:
                got_role = None
                for each in member.roles:
                    try:
                        if each.id in self.bot.exceptional_role_id[str(member.guild.id)]:
                            got_role = each
                            ignore = True
                            break
                    except Exception as e:
                        traceback.print_exc(file=sys.stdout)
                if ignore is True:
                    try:
                        if self.bot.log_channel_guild[str(member.guild.id)]:
                            await self.utils.log_to_channel(
                                self.bot.log_channel_guild[str(member.guild.id)],
                                f"[**ignore user**] User `{member.name}` | {member.mention} | Having role `{got_role.name}`."
                            )
                    except Exception as e:
                        traceback.print_exc(file=sys.stdout)
                    return
            # check if user in ignore list
            try:
                if str(member.guild.id) in self.bot.exceptional_user_name_id and \
                    member.id in self.bot.exceptional_user_name_id[str(member.guild.id)]:
                    try:
                        if self.bot.log_channel_guild[str(member.guild.id)]:
                            await self.utils.log_to_channel(
                                self.bot.log_channel_guild[str(member.guild.id)],
                                f"[**ignore user**] User `{member.name}` | {member.mention} | Ignored User ID `{member.id}`"
                            )
                    except Exception as e:
                        traceback.print_exc(file=sys.stdout)
                    return
            except Exception as e:
                traceback.print_exc(file=sys.stdout)

            try:
                await self.utils.log_to_channel(
                    self.bot.log_channel_guild[str(member.guild.id)],
                    f"[**member_join**] {member.id} / {member.name} | {member.mention}"
                )
            except Exception as e:
                traceback.print_exc(file=sys.stdout)
            # if nick matches, kick / ban?
            try:
                regex_list = self.bot.name_filter_list[str(member.guild.id)]
                if len(regex_list) > 0:
                    for each in regex_list:
                        try:
                            regex_test = r"{}".format(each)
                            r = re.search(regex_test, member.name)
                            if r:
                                if self.bot.config['discord']['is_testing'] == 1:
                                    await self.utils.log_to_channel(
                                        self.bot.log_channel_guild[str(member.guild.id)],
                                        f"[TESTING] [**matches regex**] [**ban**] {member.id} / "\
                                        f"{member.name} / {member.mention} matches with `{each}`."
                                    )
                                else:
                                    # TODO, add ban/kick code
                                    await self.utils.log_to_channel(
                                        self.bot.log_channel_guild[str(member.guild.id)],
                                        f"[**matches regex**] [**ban**] {member.id} / "\
                                        f"{member.name} / {member.mention} matches with `{each}`."
                                    )
                                break
                        except Exception as e:
                            traceback.print_exc(file=sys.stdout)
            except Exception as e:
                traceback.print_exc(file=sys.stdout)

    @commands.Cog.listener()
    async def on_member_update(self, before, after):
        if str(after.guild.id) in self.bot.log_channel_guild and self.bot.log_channel_guild[str(after.guild.id)]:
            # check permission bot
            check_perm = await self.utils.bot_can_kick_ban(after.guild)
            if check_perm is None:
                await self.utils.log_to_channel(
                    self.bot.config['discord']['log_channel'],
                    f"Bot failed to get permission info in guild `{after.guild.name} / {after.guild.id}`"
                )
                return
            else:
                if check_perm['kick_members'] is False or check_perm['ban_members'] is False:
                    await self.utils.log_to_channel(
                        self.bot.log_channel_guild[str(after.guild.id)],
                        f"User `{after.name}` | {after.mention} updated name but "\
                        "Bot doesn't have permission kick/ban to process next step of checking!"
                    )
            # end of check permission
            ignore = False
            # check if user in ignore list role
            if len(after.roles) > 0:
                got_role = None
                for each in after.roles:
                    try:
                        if str(after.guild.id) in self.bot.exceptional_role_id and \
                            each.id in self.bot.exceptional_role_id[str(after.guild.id)]:
                            got_role = each
                            ignore = True
                            break
                    except Exception as e:
                        traceback.print_exc(file=sys.stdout)
                if ignore is True:
                    try:
                        if str(after.guild.id) in self.bot.log_channel_guild and \
                            self.bot.log_channel_guild[str(after.guild.id)]:
                            await self.utils.log_to_channel(
                                self.bot.log_channel_guild[str(after.guild.id)],
                                f"[**ignore user**] `{each}` User `{after.name}` | {after.mention} | Having role `{got_role.name}`."
                            )
                    except Exception as e:
                        traceback.print_exc(file=sys.stdout)
                    return
            # check if user in ignore list
            try:
                if str(after.guild.id) in self.bot.exceptional_user_name_id and \
                    after.id in self.bot.exceptional_user_name_id[str(after.guild.id)]:
                    try:
                        if self.bot.log_channel_guild[str(after.guild.id)]:
                            await self.utils.log_to_channel(
                                self.bot.log_channel_guild[str(after.guild.id)],
                                f"[**ignore user**] `{each}` User `{after.name}` | {after.mention} | Ignored User ID `{after.id}`"
                            )
                    except Exception as e:
                        traceback.print_exc(file=sys.stdout)
                    return
            except Exception as e:
                traceback.print_exc(file=sys.stdout)

            if after.nick is None:
                try:
                    await self.utils.log_to_channel(
                        self.bot.log_channel_guild[str(after.guild.id)],
                        f'[**member_update**] {before.id} / {before.name} changes nick to default nick `{after.name}` | {after.mention}'
                    )
                except Exception as e:
                    traceback.print_exc(file=sys.stdout)
                # if nick matches, kick / ban?
                try:
                    regex_list = self.bot.name_filter_list[str(after.guild.id)]
                    if len(regex_list) > 0:
                        for each in regex_list:
                            try:
                                regex_test = r"{}".format(each)
                                r = re.search(regex_test, after.name)
                                if r:
                                    if self.bot.config['discord']['is_testing'] == 1:
                                        await self.utils.log_to_channel(
                                            self.bot.log_channel_guild[str(after.guild.id)],
                                            f"[TESTING] [**matches regex**] [**ban**] {after.id} / {after.name} / {after.mention}"\
                                            f" matches with `{each}`."
                                        )
                                    else:
                                        # TODO, add ban/kick code
                                        await self.utils.log_to_channel(
                                            self.bot.log_channel_guild[str(after.guild.id)],
                                            f"[**matches regex**] [**ban**] {after.id} / {after.name} / {after.mention} "\
                                            f"matches with `{each}`."
                                        )
                                    break
                            except Exception as e:
                                traceback.print_exc(file=sys.stdout)
                except Exception as e:
                    traceback.print_exc(file=sys.stdout)
            elif before.nick != after.nick and after.bot == False:
                try:
                    await self.utils.log_to_channel(
                        self.bot.log_channel_guild[str(after.guild.id)],
                        f'[**member_update**] {before.id} / {before.name} changes nick to `{after.nick}` | {after.mention}'
                    )
                except Exception as e:
                    traceback.print_exc(file=sys.stdout)
                # if nick matches, kick / ban?
                try:
                    regex_list = self.bot.name_filter_list[str(after.guild.id)]
                    if len(regex_list) > 0:
                        for each in regex_list:
                            try:
                                regex_test = r"{}".format(each)
                                r = re.search(regex_test, after.nick)
                                if r:
                                    if self.bot.config['discord']['is_testing'] == 1:
                                        await self.utils.log_to_channel(
                                            self.bot.log_channel_guild[str(after.guild.id)],
                                            f"[TESTING] [**matches regex**] [**ban**] {after.id} / {after.name} / "\
                                            f"{after.mention} matches with `{each}`."
                                        )
                                    else:
                                        # TODO, add ban/kick code
                                        await self.utils.log_to_channel(
                                            self.bot.log_channel_guild[str(after.guild.id)],
                                            f"[**matches regex**] [**ban**] {after.id} / {after.name} / "\
                                            f"{after.mention} matches with `{each}`."
                                        )
                                    break
                            except Exception as e:
                                traceback.print_exc(file=sys.stdout)
                except Exception as e:
                    traceback.print_exc(file=sys.stdout)

    @commands.Cog.listener()
    async def on_user_update(self, before, after):
        if str(after.guild.id) in self.bot.log_channel_guild and self.bot.log_channel_guild[str(after.guild.id)]:
            if after.bot == False:
                await self.utils.log_to_channel(
                    self.bot.log_channel_guild[str(after.guild.id)],
                    f'[**user_update**] {before.id} / {after.mention} | {after.username}'
                )

    @commands.Cog.listener()
    async def on_ready(self):
        pass

    async def cog_load(self) -> None:
        pass

    async def cog_unload(self) -> None:
        pass


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Events(bot))
