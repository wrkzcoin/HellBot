import discord
from discord.ext import commands, tasks
import traceback, sys
import time
import asyncio
import re
import unicodedata
from rapidfuzz import fuzz
import hashlib

from cogs.utils import check_regex
from cogs.utils import Utils

# Cog class
class Events(commands.Cog):

    def __init__(self, bot: commands.Bot) -> None:
        self.bot: commands.Bot = bot
        self.utils = Utils(bot)

    @commands.Cog.listener()
    async def on_message(self, message):
        # should ignore webhook message
        if message is None:
            return

        if hasattr(message, "channel") and hasattr(message.channel, "id") and message.webhook_id:
            return

        if len(message.content) < 10:
            return

        if hasattr(message, "channel") and hasattr(message.channel, "id") and \
            message.author.bot is False:
            # Check if message filter enable
            if message.guild.id not in self.bot.enable_message_filter:
                return
            else:
                # Check if there is a log channel
                if str(message.guild.id) not in self.bot.log_channel_guild or \
                    self.bot.log_channel_guild[str(message.guild.id)] is None:
                    return
                else:
                    # Check if bot has permission to manage message
                    check_perm = await self.utils.get_bot_perm(message.guild)
                    if check_perm and check_perm['manage_messages'] is False:
                        # log channel
                        await self.utils.log_to_channel(
                            self.bot.config['discord']['log_channel'],
                            f"Guild `{message.guild.name} / {message.guild.id}` Bot not having manage message permission."
                        )
                        await self.utils.log_to_channel(
                            self.bot.log_channel_guild[str(message.guild.id)],
                            f"I can't filter message since I don't have manage message permission."\
                            f" You can turn it off by `/messagefilter off`"
                        )
                        return

                    try:
                        # Check with templates
                        matches = False
                        matched_key = None
                        matched_content = ""
                        ratio = 0.0
                        if len(self.bot.message_filter_templates) > 0:
                            for each in self.bot.message_filter_templates:
                                compare = fuzz.partial_ratio(message.content, each)
                                if (len(message.content) > 12 and compare >= 80) or\
                                    (len(message.content) <=12 and compare > 90):
                                    matches = True
                                    sha1 = hashlib.sha1()
                                    sha1.update(each.encode())
                                    matched_key = sha1.hexdigest()
                                    matched_content = each
                                    ratio = compare
                                    # update trigger
                                    try:
                                        await self.utils.update_message_filters_template_trigger(
                                            self.bot.message_filter_templates_kv[matched_key]['msg_tpl_id']
                                        )
                                    except Exception as e:
                                        traceback.print_exc(file=sys.stdout)
                                    break
                        if matches is False and str(message.guild.id) in self.bot.message_filters and \
                            len(self.bot.message_filters[str(message.guild.id)]) > 0:
                            for each in self.bot.message_filters[str(message.guild.id)]:
                                compare = fuzz.partial_ratio(message.content, each)
                                if (len(message.content) > 12 and compare >= 80) or\
                                    (len(message.content) <=12 and compare > 90):
                                    matches = True
                                    sha1 = hashlib.sha1()
                                    sha1.update(each.encode())
                                    matched_key = sha1.hexdigest()
                                    matched_content = each
                                    ratio = compare
                                    break
                        if matches is True:
                            # log channel
                            await self.utils.log_to_channel(
                                self.bot.config['discord']['log_channel'],
                                f"Guild `{message.guild.name}` filtered message:\n```{message.content}``` from "\
                                f"author {message.author.name} / `{message.author.id}`"
                            )
                            await self.utils.log_to_channel(
                                self.bot.log_channel_guild[str(message.guild.id)],
                                f"User {message.author.name} / `{message.author.id}` posted a filtered content in {message.channel.mention}:\n"\
                                f"```{message.content}```"
                            )
                            await message.delete()
                            await self.utils.add_deleted_message_log(
                                message.content, matched_content, ratio, str(message.guild.id), str(message.author.id)
                            )
                    except Exception as e:
                        traceback.print_exc(file=sys.stdout)

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
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
            await self.utils.log_to_channel(
                self.bot.config['discord']['log_channel'],
                f"Failed to delete guild "\
                f"`{guild.name} / {guild.id}`"
            )
        # reload data
        await self.utils.load_reload_bot_data()

    @commands.Cog.listener()
    async def on_member_remove(self, member):
        if str(member.guild.id) in self.bot.log_channel_guild and self.bot.log_channel_guild[str(member.guild.id)] \
            and member != self.bot.user:
            await self.utils.log_to_channel(
                self.bot.log_channel_guild[str(member.guild.id)],
                f"User `{member.name}` | {member.mention} left guild!"
            )

    @commands.Cog.listener()
    async def on_member_join(self, member):
        if str(member.guild.id) in self.bot.log_channel_guild and self.bot.log_channel_guild[str(member.guild.id)]:
            # check permission bot
            check_perm = await self.utils.get_bot_perm(member.guild)
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
                        if str(member.guild.id) in self.bot.exceptional_role_id and \
                            each.id in self.bot.exceptional_role_id[str(member.guild.id)]:
                            got_role = each
                            ignore = True
                            break
                    except Exception as e:
                        traceback.print_exc(file=sys.stdout)
                if ignore is True:
                    try:
                        if member.bot is False and self.bot.log_channel_guild[str(member.guild.id)]:
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
                        if member.bot is False and self.bot.log_channel_guild[str(member.guild.id)]:
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
                            # https://stackoverflow.com/questions/62803325/how-to-convert-fancy-artistic-unicode-text-to-ascii
                            name = unicodedata.normalize( 'NFKC', member.name)
                            r = re.search(regex_test, name)
                            if r:
                                if self.bot.config['discord']['is_testing'] == 1:
                                    await self.utils.log_to_channel(
                                        self.bot.log_channel_guild[str(member.guild.id)],
                                        f"[TESTING] [**matches regex**] [**ban**] {member.id} / "\
                                        f"{member.name} / {member.mention} matches with `{each}`."
                                    )
                                else:
                                    try:
                                        await member.guild.kick(
                                            user=member,
                                            reason=f"You are kicked from `{member.guild.name}`. "\
                                                f"Name matches `{each}`"
                                        )
                                        await self.utils.log_to_channel(
                                            self.bot.log_channel_guild[str(member.guild.id)],
                                            f"[**matches regex**] [**kick**] {member.id} / "\
                                            f"{member.name} / {member.mention} matches with `{each}`."
                                        )
                                    except Exception as e:
                                        traceback.print_exc(file=sys.stdout)
                                break
                        except Exception as e:
                            traceback.print_exc(file=sys.stdout)
            except Exception as e:
                traceback.print_exc(file=sys.stdout)

    @commands.Cog.listener()
    async def on_member_update(self, before, after):
        if str(after.guild.id) in self.bot.log_channel_guild and self.bot.log_channel_guild[str(after.guild.id)]:
            # check permission bot
            check_perm = await self.utils.get_bot_perm(after.guild)
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

            if after.nick is None:
                # if nick matches, kick / ban?
                try:
                    regex_list = self.bot.name_filter_list[str(after.guild.id)]
                    if len(regex_list) > 0:
                        for each in regex_list:
                            try:
                                regex_test = r"{}".format(each)
                                name = unicodedata.normalize( 'NFKC', after.name)
                                r = re.search(regex_test, name)
                                if r:
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
                                                    self.bot.log_channel_guild[str(after.guild.id)] and after.bot is False:
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
                                            after.id in self.bot.exceptional_user_name_id[str(after.guild.id)] and after.bot is False:
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
                                    # end of check if user in ignore list

                                    # Check if user can kick/ban, skip
                                    try:
                                        check_perm = await self.utils.get_user_perms(after.guild, after.id)
                                        if check_perm is not None and \
                                            (check_perm['kick_members'] is True or check_perm['ban_members'] is True):
                                            await self.utils.log_to_channel(
                                                self.bot.log_channel_guild[str(after.guild.id)],
                                                f"User `{after.name}` | {after.mention} updated name matches `{each}` but "\
                                                "He/she has permission to kick/ban (Excluded)!"
                                            )
                                            return
                                    except Exception as e:
                                        traceback.print_exc(file=sys.stdout)
                                    # End of check user can kick/ban

                                    if self.bot.config['discord']['is_testing'] == 1:
                                        await self.utils.log_to_channel(
                                            self.bot.log_channel_guild[str(after.guild.id)],
                                            f"[TESTING] [**matches regex**] [**ban**] {after.id} / {after.name} / {after.mention}"\
                                            f" matches with `{each}`."
                                        )
                                    else:
                                        try:
                                            await after.guild.kick(
                                                user=after, reason=f"You are kicked from `{after.guild.name}`. Name matches `{each}`."
                                            )
                                            await self.utils.log_to_channel(
                                                self.bot.log_channel_guild[str(after.guild.id)],
                                                f"[**matches regex**] [**kick**] {after.id} / {after.name} / {after.mention} "\
                                                f"matches with `{each}`."
                                            )
                                        except Exception as e:
                                            traceback.print_exc(file=sys.stdout)
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
                                name = unicodedata.normalize( 'NFKC', after.nick)
                                r = re.search(regex_test, name)
                                if r:
                                    # Check if user can kick/ban, skip
                                    try:
                                        check_perm = await self.utils.get_user_perms(after.guild, after.id)
                                        if check_perm is not None and \
                                            (check_perm['kick_members'] is True or check_perm['ban_members'] is True):
                                            await self.utils.log_to_channel(
                                                self.bot.log_channel_guild[str(after.guild.id)],
                                                f"User `{after.name}` | {after.mention} updated name matches `{each}` but "\
                                                "He/she has permission to kick/ban (Excluded)!"
                                            )
                                            return
                                    except Exception as e:
                                        traceback.print_exc(file=sys.stdout)
                                    # End of check user can kick/ban

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
                                                    self.bot.log_channel_guild[str(after.guild.id)] and after.bot is False:
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
                                            after.id in self.bot.exceptional_user_name_id[str(after.guild.id)] and after.bot is False:
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
                                    # end of check if user in ignore list

                                    if self.bot.config['discord']['is_testing'] == 1:
                                        await self.utils.log_to_channel(
                                            self.bot.log_channel_guild[str(after.guild.id)],
                                            f"[TESTING] [**matches regex**] [**ban**] {after.id} / {after.name} / "\
                                            f"{after.mention} matches with `{each}`."
                                        )
                                    else:
                                        try:
                                            await after.guild.kick(
                                                user=after,
                                                reason=f"You are kicked from `{after.guild.name}`. Name matches `{each}`"
                                            )
                                            await self.utils.log_to_channel(
                                                self.bot.log_channel_guild[str(after.guild.id)],
                                                f"[**matches regex**] [**kick**] {after.id} / {after.name} / "\
                                                f"{after.mention} matches with `{each}`."
                                            )
                                            await asyncio.sleep(0.1)
                                        except Exception as e:
                                            traceback.print_exc(file=sys.stdout)
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
