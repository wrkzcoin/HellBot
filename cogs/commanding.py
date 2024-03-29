from code import interact
import discord
from discord.ext import commands, tasks
from discord import app_commands
from discord.app_commands import checks, MissingPermissions
import re
from datetime import datetime
from typing import List

import traceback, sys
import time
import asyncio
import unicodedata
from rapidfuzz import fuzz

from cogs.utils import check_regex
from cogs.utils import Utils


class ConfirmApply(discord.ui.View):
    def __init__(
        self, bot, interaction, timeout: float,
        disable_button: bool, list_users, disable_apply: bool
    ):
        super().__init__(timeout=timeout)
        self.bot = bot
        self.utils = Utils(self.bot)
        self.disable_button = disable_button
        self.disable_apply = disable_apply
        self.interaction = interaction
        self.list_users = list_users
        if self.disable_button is True:
            for child in self.children:
                if isinstance(child, discord.ui.Button):
                    child.disabled = True

        if self.disable_apply is True:
            self.confirm.disabled = True

    async def on_timeout(self):
        for child in self.children:
            if isinstance(child, discord.ui.Button):
                child.disabled = True
        await self.interaction.edit_original_response(view=self)

    @discord.ui.button(label='Delete?', style=discord.ButtonStyle.red)
    async def delete_regex(self, interaction: discord.Interaction, button: discord.ui.Button):
        # We don't need this, just in case we turn on public later on
        if self.interaction.user != interaction.user:
            await interaction.response.send_message("Permission denied.It's not yours", ephemeral=True)
            return

        await interaction.response.send_message('Deleting in progress....', ephemeral=True)
        for child in self.children:
            if isinstance(child, discord.ui.Button):
                child.disabled = True

        try:
            if str(interaction.guild.id) in self.bot.name_filter_list_pending and\
                self.bot.name_filter_list_pending[str(interaction.guild.id)] and\
                    len(self.bot.name_filter_list_pending[str(interaction.guild.id)]) != 1:
                    await interaction.edit_original_response(content="Failed to apply namefilter! Please try again later!")
                    return
            elif str(interaction.guild.id) in self.bot.name_filter_list_pending and\
                self.bot.name_filter_list_pending[str(interaction.guild.id)] and\
                    len(self.bot.name_filter_list_pending[str(interaction.guild.id)]) == 1:
                # remove from DB, 
                regex = self.bot.name_filter_list_pending[str(interaction.guild.id)][0]
                deleting = await self.utils.delete_regex(str(interaction.guild.id), regex, str(interaction.user.id))
                if deleting is True:
                    del self.bot.name_filter_list_pending[str(interaction.guild.id)][0]
                    await interaction.edit_original_response(content=f"Successfully deleted pending regex `{regex}`")
                    await self.utils.log_to_channel(
                        self.bot.config['discord']['log_channel'],
                        f"{interaction.user.name} / `{interaction.user.id}` in guild `{interaction.guild.id}`"\
                        f" delete regex `{regex}` from pending list."
                    )
                    await self.utils.log_to_channel(
                        self.bot.log_channel_guild[str(interaction.guild.id)],
                        f"{interaction.user.name} / `{interaction.user.id}` delete regex `{regex}` from pending list."
                    )
        except Exception:
            traceback.print_exc(file=sys.stdout)
        await self.interaction.edit_original_response(view=self)
        self.stop()

    @discord.ui.button(label='Apply?', style=discord.ButtonStyle.green)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        # We don't need this, just in case we turn on public later on
        if self.interaction.user != interaction.user:
            await interaction.response.send_message("Permission denied.It's not yours", ephemeral=True)
            return

        await interaction.response.send_message('Applying in progress....', ephemeral=True)
        for child in self.children:
            if isinstance(child, discord.ui.Button):
                child.disabled = True
        try:
            if str(interaction.guild.id) in self.bot.name_filter_list_pending and\
                self.bot.name_filter_list_pending[str(interaction.guild.id)] and\
                    len(self.bot.name_filter_list_pending[str(interaction.guild.id)]) != 1:
                    await interaction.edit_original_response(content="Failed to apply namefilter! Please try again later!")
                    return
            elif str(interaction.guild.id) in self.bot.name_filter_list_pending and\
                self.bot.name_filter_list_pending[str(interaction.guild.id)] and\
                    len(self.bot.name_filter_list_pending[str(interaction.guild.id)]) == 1:
                regex = self.bot.name_filter_list_pending[str(interaction.guild.id)][0]

                if len(self.list_users) > len(interaction.guild.members) * self.bot.config['discord']['max_apply_ban_ratio'] or \
                    len(self.list_users) > self.bot.config['discord']['max_apply_ban_users']:
                    await interaction.edit_original_response(content="There are more than 25 percents or 100 users to ban. Rejected!")
                    return

                applying = await self.utils.update_regex_on(str(interaction.guild.id), regex)
                if applying is True:
                    if len(self.list_users) > 0:
                        for each in self.list_users:
                            # Check if user can kick/ban, skip
                            try:
                                check_perm = await self.utils.get_user_perms(interaction.guild, each)
                                if check_perm is not None and \
                                    (check_perm['kick_members'] is True or check_perm['ban_members'] is True):
                                    continue
                            except Exception as e:
                                traceback.print_exc(file=sys.stdout)
                            # End of check user can kick/ban

                            ignore = False
                            # check if user in ignore list role
                            get_user = interaction.guild.get_member(each)
                            if len(get_user.roles) > 0:
                                for r in get_user.roles:
                                    try:
                                        if str(get_user.guild.id) in self.bot.exceptional_role_id and \
                                            r.id in self.bot.exceptional_role_id[str(get_user.guild.id)]:
                                            ignore = True
                                            break
                                    except Exception as e:
                                        traceback.print_exc(file=sys.stdout)
                                if ignore is True:
                                    continue
                            # check if user in ignore list
                            try:
                                if str(get_user.guild.id) in self.bot.exceptional_user_name_id and \
                                    get_user.id in self.bot.exceptional_user_name_id[str(get_user.guild.id)] and get_user.bot is False:
                                    continue
                            except Exception as e:
                                traceback.print_exc(file=sys.stdout)
                            # end of check if user in ignore list
                            try:
                                await interaction.guild.kick(
                                    user=get_user,
                                    reason=f'You are kicked from `{interaction.guild.name}`. Nick name matches `{regex}`'
                                )
                                await self.utils.log_to_channel(
                                    self.bot.log_channel_guild[str(interaction.guild.id)],
                                    f"{interaction.user.name} / `{interaction.user.id}` executed `/namefilter apply` regex {regex}. "\
                                    f"Kicked <@{str(each)}> `{str(each)}`"
                                )
                            except Exception:
                                traceback.print_exc(file=sys.stdout)
                        await interaction.edit_original_response(
                            content=f"Saved `{regex}` to your guild! "\
                            f"Also banned {str(len(self.list_users))}"
                        )
                        await self.utils.log_to_channel(
                            self.bot.config['discord']['log_channel'],
                            f"{interaction.user.name} / `{interaction.user.id}` executed `/namefilter apply` regex {regex}."
                        )
                        await self.utils.log_to_channel(
                            self.bot.log_channel_guild[str(interaction.guild.id)],
                            f"{interaction.user.name} / `{interaction.user.id}` executed `/namefilter apply` regex {regex}."
                        )
                    else:
                        await interaction.edit_original_response(content=f"Saved `{regex}` to your guild!")
                        await self.utils.log_to_channel(
                            self.bot.config['discord']['log_channel'],
                            f"{interaction.user.name} / `{interaction.user.id}` executed `/namefilter apply` regex {regex}."
                        )
                        await self.utils.log_to_channel(
                            self.bot.log_channel_guild[str(interaction.guild.id)],
                            f"{interaction.user.name} / `{interaction.user.id}` executed `/namefilter apply` regex {regex}."
                        )
                    self.bot.name_filter_list_pending[str(interaction.guild.id)] = []
                    # self.bot.name_filter_list[str(interaction.guild.id)].append(regex)
                    await self.utils.load_reload_bot_data()
                else:
                    await interaction.edit_original_response(content="Internal error! Please report!")
        except Exception:
            traceback.print_exc(file=sys.stdout)
        await self.interaction.edit_original_response(view=self)
        self.stop()


# Cog class
class Commanding(commands.Cog):

    def __init__(self, bot: commands.Bot) -> None:
        self.bot: commands.Bot = bot
        self.utils = Utils(bot)

    @app_commands.command(
        name="reload",
        description="Reload data"
    )
    async def command_reload_data(
        self,
        interaction: discord.Interaction,
    ) -> None:
        """ /reload """
        """ This is private """
        if interaction.user.id not in self.bot.config['discord']['admin']:
            await interaction.response.send_message(f"{interaction.user.mention}, permission denied")
            return

        await interaction.response.send_message(f"{interaction.user.mention} reloading...", ephemeral=True)
        try:
            await self.utils.load_reload_bot_data()
            await interaction.edit_original_response(
                content=f"{interaction.user.mention}, data reloaded successfully!"
            )
            await self.utils.log_to_channel(
                self.bot.config['discord']['log_channel'],
                f"{interaction.user.name} / `{interaction.user.id}` execute command /reload data"
            )
        except Exception as e:
            traceback.print_exc(file=sys.stdout)

    @checks.has_permissions(ban_members=True)
    @app_commands.guild_only()
    @app_commands.command(
        name="clearmsg",
        description="Clear a spammer or a user's last messages"
    )
    async def command_clear_user_msg(
        self,
        interaction: discord.Interaction,
        user_id: str
    ) -> None:
        """ /clearmsg <user id> """
        await interaction.response.send_message(f"{interaction.user.mention} checking...", ephemeral=True)
        # re-check perm
        try:
            is_mod = await self.utils.is_managed_message(interaction.guild, interaction.user.id)
            if is_mod is False:
                await interaction.edit_original_response(
                    content=f"{interaction.user.mention}, permission denied."
                )
                return
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
        # end of re-check perm

        try:
            # Check permission
            check_perm = await self.utils.get_bot_perm(interaction.guild)
            if check_perm is None:
                await interaction.edit_original_response(
                    content=f"{interaction.user.mention}, internal error. Check again later!"
                )
                await self.utils.log_to_channel(
                    self.bot.config['discord']['log_channel'],
                    f"{interaction.user.name} / `{interaction.user.id}` execute command in guild `{interaction.guild.id}`"\
                    f" but failed to check bot's permission in their guild."
                )
                return
            else:
                if check_perm['manage_messages'] is False:
                    await interaction.edit_original_response(
                        content=f"{interaction.user.mention}, bot has no permission manage_messages!"\
                            " Please adjust permission and re-try."
                    )
                    await self.utils.log_to_channel(
                        self.bot.log_channel_guild[str(interaction.guild.id)],
                        f"{interaction.user.mention} / `{interaction.user.id}`, please check if Bot has permission manage_messages."
                    )
                    return
            # End of check permission

            delete_counter = 0
            invalid_permission = 0
            for channel in interaction.guild.channels:
                if not type(channel) is discord.TextChannel:
                    continue
                try:
                    async for message in channel.history(limit=100):
                        if str(message.author.id) == user_id:
                            try:
                                await message.delete()
                                delete_counter += 1
                            except Exception as e:
                                invalid_permission += 1
                except Exception as e:
                    invalid_permission += 1
            invalid_msg = ""
            if invalid_permission > 0:
                invalid_msg = f" Failed {str(invalid_permission)} checks."
            await interaction.edit_original_response(
                content=f"{interaction.user.mention}, deleted {str(delete_counter)} message(s) from {str(user_id)}!{invalid_msg}"
            )
            await self.utils.log_to_channel(
                self.bot.log_channel_guild[str(interaction.guild.id)],
                f"{interaction.user.mention} / `{interaction.user.id}`, deleted {str(delete_counter)} message(s) from {str(user_id)}!."
            )
        except Exception as e:
            traceback.print_exc(file=sys.stdout)


    ignore_group = app_commands.Group(name="ignore", guild_only=True, description="Ignore role or name.")

    @checks.has_permissions(ban_members=True)
    @ignore_group.command(
        name="list",
        description="List ignored users and roles from namefilter."
    )
    async def command_ignore_list(
        self,
        interaction: discord.Interaction,
    ) -> None:
        """ /ignore list """
        """ This is private """
        try:
            await interaction.response.send_message(f"{interaction.user.mention} ignore loading...", ephemeral=True)
            # re-check perm
            try:
                is_mod = await self.utils.is_moderator(interaction.guild, interaction.user.id)
                if is_mod is False:
                    await interaction.edit_original_response(
                        content=f"{interaction.user.mention}, permission denied."
                    )
                    return
            except Exception as e:
                traceback.print_exc(file=sys.stdout)
            # end of re-check perm

            if str(interaction.guild.id) not in self.bot.log_channel_guild or \
                self.bot.log_channel_guild[str(interaction.guild.id)] is None:
                await interaction.edit_original_response(
                    content=f"{interaction.user.mention}, please set log channel first with `/logchan #channel`."
                )
            else:
                # Check permission
                check_perm = await self.utils.get_bot_perm(interaction.guild)
                if check_perm is None:
                    await interaction.edit_original_response(
                        content=f"{interaction.user.mention}, internal error. Check again later!"
                    )
                    await self.utils.log_to_channel(
                        self.bot.config['discord']['log_channel'],
                        f"{interaction.user.name} / `{interaction.user.id}` execute command in guild `{interaction.guild.id}`"\
                        f" but failed to check bot's permission in their guild."
                    )
                    return
                else:
                    if check_perm['kick_members'] is False or check_perm['ban_members'] is False:
                        await interaction.edit_original_response(
                            content=f"{interaction.user.mention}, bot has no permission to ban/kick member!"\
                                " Please adjust permission and re-try."
                        )
                        await self.utils.log_to_channel(
                            self.bot.log_channel_guild[str(interaction.guild.id)],
                            f"{interaction.user.mention} / `{interaction.user.id}`, please check if Bot has permission kick/ban."
                        )
                        return
                # End of check permission

                get_exceptional_users = await self.utils.get_exceptional_users_list(str(interaction.guild.id))
                get_exceptional_roles = await self.utils.get_exceptional_roles_list(str(interaction.guild.id))
                if len(get_exceptional_users) + len(get_exceptional_roles) == 0:
                    await interaction.edit_original_response(
                        content=f"{interaction.user.mention}, there is not any user or role in ignore list right now."
                    )
                else:
                    ignored_list = []
                    if len(get_exceptional_users) > 0:
                        for each in get_exceptional_users:
                            added_time = discord.utils.format_dt(
                                datetime.fromtimestamp(each['added_date']), style='R'
                            )
                            ignored_list.append("User: <@{}>, added by <@{}> {}".format(each['user_id'], each['added_by'], added_time))
                    if len(get_exceptional_roles) > 0:
                        for each in get_exceptional_roles:
                            added_time = discord.utils.format_dt(
                                datetime.fromtimestamp(each['added_date']), style='R'
                            )
                            ignored_list.append("Role: <@&{}>, added by <@{}> {}".format(each['role_id'], each['added_by'], added_time))
                    ignored_list_str = "\n".join(ignored_list)
                    await interaction.edit_original_response(
                        content=f"{interaction.user.mention}, ignore list:\n{ignored_list_str}"
                    )
        except Exception as e:
            traceback.print_exc(file=sys.stdout)


    @checks.has_permissions(ban_members=True)
    @ignore_group.command(
        name="adduser",
        description="Add a user to ignore list of namefilter."
    )
    async def command_ignore_adduser(
        self,
        interaction: discord.Interaction,
        member: discord.Member
    ) -> None:
        """ /ignore adduser <Member> """
        """ This is private """
        try:
            await interaction.response.send_message(f"{interaction.user.mention} ignore loading...", ephemeral=True)
            # re-check perm
            try:
                is_mod = await self.utils.is_moderator(interaction.guild, interaction.user.id)
                if is_mod is False:
                    await interaction.edit_original_response(
                        content=f"{interaction.user.mention}, permission denied."
                    )
                    return
            except Exception as e:
                traceback.print_exc(file=sys.stdout)
            # end of re-check perm

            if str(interaction.guild.id) not in self.bot.log_channel_guild or \
                self.bot.log_channel_guild[str(interaction.guild.id)] is None:
                await interaction.edit_original_response(
                    content=f"{interaction.user.mention}, please set log channel first with `/logchan #channel`."
                )
            else:
                # Check permission
                check_perm = await self.utils.get_bot_perm(interaction.guild)
                if check_perm is None:
                    await interaction.edit_original_response(
                        content=f"{interaction.user.mention}, internal error. Check again later!"
                    )
                    await self.utils.log_to_channel(
                        self.bot.config['discord']['log_channel'],
                        f"{interaction.user.name} / `{interaction.user.id}` execute command in guild `{interaction.guild.id}`"\
                        f" but failed to check bot's permission in their guild."
                    )
                    return
                else:
                    if check_perm['kick_members'] is False or check_perm['ban_members'] is False:
                        await interaction.edit_original_response(
                            content=f"{interaction.user.mention}, bot has no permission to ban/kick member!"\
                                " Please adjust permission and re-try."
                        )
                        await self.utils.log_to_channel(
                            self.bot.log_channel_guild[str(interaction.guild.id)],
                            f"{interaction.user.mention} / `{interaction.user.id}`, please check if Bot has permission kick/ban."
                        )
                        return
                # End of check permission
                get_exceptional_users = await self.utils.get_exceptional_users_list(str(interaction.guild.id))
                if len(get_exceptional_users) >= self.bot.max_ignored_user[str(interaction.guild.id)]:
                    await interaction.edit_original_response(content=f"{interaction.user.mention}, your guild reaches "\
                        f"maximum list of exclusion users `{str(self.bot.max_ignored_user[str(interaction.guild.id)])}`.")
                    await self.utils.log_to_channel(
                        self.bot.config['discord']['log_channel'],
                        f"{interaction.user.name} / `{interaction.user.id}` in guild `{interaction.guild.id}`"\
                        f" try to add user to ignore list but reach limit `{str(self.bot.max_ignored_user[str(interaction.guild.id)])}`."
                    )
                    await self.utils.log_to_channel(
                        self.bot.log_channel_guild[str(interaction.guild.id)],
                        f"{interaction.user.name} / `{interaction.user.id}` executed `/ignore adduser {member.name}` "\
                        f"but exceeded limit `{str(self.bot.max_ignored_user[str(interaction.guild.id)])}`."
                    )
                    return
                else:
                    existing_user_ids = [int(each['user_id']) for each in get_exceptional_users]
                    if len(existing_user_ids) > 0 and member.id in existing_user_ids:
                        await interaction.edit_original_response(
                            content=f"{interaction.user.mention}, member `{member.name} / {member.id}`"\
                            "is already in the list."
                        )
                        return

                    adding = await self.utils.insert_new_exceptional_user(str(interaction.guild.id), str(member.id), str(interaction.user.id))
                    if adding is True:
                        if str(interaction.guild.id) not in self.bot.exceptional_user_name_id:
                            self.bot.exceptional_user_name_id[str(interaction.guild.id)] = []
                        self.bot.exceptional_user_name_id[str(interaction.guild.id)].append(member.id) # integer

                        await interaction.edit_original_response(
                            content=f"{interaction.user.mention}, added ignore role `{member.name}` / `{member.id}` successfully!"
                        )

                        await self.utils.log_to_channel(
                            self.bot.config['discord']['log_channel'],
                            f"{interaction.user.name} / `{interaction.user.id}` in guild `{interaction.guild.id}`"\
                            f" add a member `{member.name} / {member.id}` to ignore list."
                        )
                        await self.utils.log_to_channel(
                            self.bot.log_channel_guild[str(interaction.guild.id)],
                            f"{interaction.user.name} / `{interaction.user.id}` executed `/ignore adduser `{member.name} / {member.id}`."
                        )
                    else:
                        await interaction.edit_original_response(
                            content=f"{interaction.user.mention}, internal error when adding user. Please report!"
                        )
                        await self.utils.log_to_channel(
                            self.bot.config['discord']['log_channel'],
                            f"{interaction.user.name} / `{interaction.user.id}` in guild `{interaction.guild.id}`"\
                            f" failed to add a user `{member.name} / {member.id}` to ignore list."
                        )
                        await self.utils.log_to_channel(
                            self.bot.log_channel_guild[str(interaction.guild.id)],
                            f"{interaction.user.name} / `{interaction.user.id}` failed to execute `/ignore adduser `{member.name}`."
                        )
        except Exception as e:
            traceback.print_exc(file=sys.stdout)

    @checks.has_permissions(ban_members=True)
    @ignore_group.command(
        name="deluser",
        description="Delete a user from ignore list of namefilter."
    )
    async def command_ignore_delete_user(
        self,
        interaction: discord.Interaction,
        member: discord.Member
    ) -> None:
        """ /ignore deluser <Member> """
        """ This is private """
        try:
            await interaction.response.send_message(f"{interaction.user.mention} ignore loading...", ephemeral=True)
            # re-check perm
            try:
                is_mod = await self.utils.is_moderator(interaction.guild, interaction.user.id)
                if is_mod is False:
                    await interaction.edit_original_response(
                        content=f"{interaction.user.mention}, permission denied."
                    )
                    return
            except Exception as e:
                traceback.print_exc(file=sys.stdout)
            # end of re-check perm

            if str(interaction.guild.id) not in self.bot.log_channel_guild or \
                self.bot.log_channel_guild[str(interaction.guild.id)] is None:
                await interaction.edit_original_response(
                    content=f"{interaction.user.mention}, please set log channel first with `/logchan #channel`."
                )
            else:
                # Check permission
                check_perm = await self.utils.get_bot_perm(interaction.guild)
                if check_perm is None:
                    await interaction.edit_original_response(
                        content=f"{interaction.user.mention}, internal error. Check again later!"
                    )
                    await self.utils.log_to_channel(
                        self.bot.config['discord']['log_channel'],
                        f"{interaction.user.name} / `{interaction.user.id}` execute command in guild `{interaction.guild.id}`"\
                        f" but failed to check bot's permission in their guild."
                    )
                    return
                else:
                    if check_perm['kick_members'] is False or check_perm['ban_members'] is False:
                        await interaction.edit_original_response(
                            content=f"{interaction.user.mention}, bot has no permission to ban/kick member!"\
                                " Please adjust permission and re-try."
                        )
                        await self.utils.log_to_channel(
                            self.bot.log_channel_guild[str(interaction.guild.id)],
                            f"{interaction.user.mention} / `{interaction.user.id}`, please check if Bot has permission kick/ban."
                        )
                        return
                # End of check permission
                get_exceptional_users = await self.utils.get_exceptional_users_list(str(interaction.guild.id))
                if len(get_exceptional_users) == 0:
                    await interaction.edit_original_response(
                        content=f"{interaction.user.mention}, there is nothing to delete."
                    )
                else:
                    existing_user_ids = [int(each['user_id']) for each in get_exceptional_users]
                    if member.id not in existing_user_ids:
                        await interaction.edit_original_response(
                            content=f"{interaction.user.mention}, member `{member.name} / {member.id}`."\
                                "is not in ignore list!"
                        )
                    else:
                        deleting = await self.utils.delete_exceptional_user(
                            str(interaction.guild.id), str(member.id), str(interaction.user.id)
                        )
                        if deleting is True:
                            try:
                                self.bot.exceptional_user_name_id[str(interaction.guild.id)].remove(member.id)
                            except Exception as e:
                                traceback.print_exc(file=sys.stdout)

                            await interaction.edit_original_response(
                                content=f"{interaction.user.mention}, successfully removed ignore member `{member.name} / {member.id}`."
                            )
                            await self.utils.log_to_channel(
                                self.bot.config['discord']['log_channel'],
                                f"{interaction.user.name} / `{interaction.user.id}` in guild `{interaction.guild.id}`"\
                                f" deleted a member `{member.name} / {member.id}` from ignore list."
                            )
                            await self.utils.log_to_channel(
                                self.bot.log_channel_guild[str(interaction.guild.id)],
                                f"{interaction.user.name} / `{interaction.user.id}` executed `/ignore deluser `{member.name} / {member.id}`."
                            )
                        else:
                            await interaction.edit_original_response(
                                content=f"{interaction.user.mention}, failed to remove ignore member `{member.name} / {member.id}`."\
                                    " Please report!"
                            )
                            await self.utils.log_to_channel(
                                self.bot.config['discord']['log_channel'],
                                f"{interaction.user.name} / `{interaction.user.id}` in guild `{interaction.guild.id}`"\
                                f" faied to delete a member `{member.name} / {member.id}` from ignore list."
                            )
                            await self.utils.log_to_channel(
                                self.bot.log_channel_guild[str(interaction.guild.id)],
                                f"{interaction.user.name} / `{interaction.user.id}` failed to execute `/ignore deluser `{member.name}`."
                            )
        except Exception as e:
            traceback.print_exc(file=sys.stdout)

    @checks.has_permissions(ban_members=True)
    @ignore_group.command(
        name="addrole",
        description="Add a role to ignore list of namefilter."
    )
    async def command_ignore_addrole(
        self,
        interaction: discord.Interaction,
        role: discord.Role
    ) -> None:
        """ /ignore addrole <Role Name> """
        """ This is private """
        try:
            await interaction.response.send_message(f"{interaction.user.mention} ignore loading...", ephemeral=True)
            # re-check perm
            try:
                is_mod = await self.utils.is_moderator(interaction.guild, interaction.user.id)
                if is_mod is False:
                    await interaction.edit_original_response(
                        content=f"{interaction.user.mention}, permission denied."
                    )
                    return
            except Exception as e:
                traceback.print_exc(file=sys.stdout)
            # end of re-check perm

            if str(interaction.guild.id) not in self.bot.log_channel_guild or \
                self.bot.log_channel_guild[str(interaction.guild.id)] is None:
                await interaction.edit_original_response(
                    content=f"{interaction.user.mention}, please set log channel first with `/logchan #channel`."
                )
                return
            else:
                # Check permission
                check_perm = await self.utils.get_bot_perm(interaction.guild)
                if check_perm is None:
                    await interaction.edit_original_response(
                        content=f"{interaction.user.mention}, internal error. Check again later!"
                    )
                    await self.utils.log_to_channel(
                        self.bot.config['discord']['log_channel'],
                        f"{interaction.user.name} / `{interaction.user.id}` execute command in guild `{interaction.guild.id}`"\
                        f" but failed to check bot's permission in their guild."
                    )
                    return
                else:
                    if check_perm['kick_members'] is False or check_perm['ban_members'] is False:
                        await interaction.edit_original_response(
                            content=f"{interaction.user.mention}, bot has no permission to ban/kick member!"\
                                " Please adjust permission and re-try."
                        )
                        await self.utils.log_to_channel(
                            self.bot.log_channel_guild[str(interaction.guild.id)],
                            f"{interaction.user.mention} / `{interaction.user.id}`, please check if Bot has permission kick/ban."
                        )
                        return
                # End of check permission
                get_exceptional_roles = await self.utils.get_exceptional_roles_list(str(interaction.guild.id))
                if len(get_exceptional_roles) >= self.bot.max_ignored_role[str(interaction.guild.id)]:
                    await interaction.edit_original_response(content=f"{interaction.user.mention}, your guild reaches "\
                        f"maximum list of exclusion roles `{str(self.bot.max_ignored_role[str(interaction.guild.id)])}`.")
                    await self.utils.log_to_channel(
                        self.bot.config['discord']['log_channel'],
                        f"{interaction.user.name} / `{interaction.user.id}` in guild `{interaction.guild.id}`"\
                        f" try to add role to ignore list but reach limit `{str(self.bot.max_ignored_role[str(interaction.guild.id)])}`."
                    )
                    await self.utils.log_to_channel(
                        self.bot.log_channel_guild[str(interaction.guild.id)],
                        f"{interaction.user.name} / `{interaction.user.id}` executed `/ignore addrole {role}` "\
                        f"but exceeded limit `{str(self.bot.max_ignored_role[str(interaction.guild.id)])}`."
                    )
                    return
                else:
                    existing_role_ids = [int(each['role_id']) for each in get_exceptional_roles]
                    if len(existing_role_ids) > 0 and role.id in existing_role_ids:
                        await interaction.edit_original_response(
                            content=f"{interaction.user.mention}, role `{role.name} / {role.id}`"\
                            "is already in the list."
                        )
                        return

                    adding = await self.utils.insert_new_exceptional_role(str(interaction.guild.id), str(role.id), str(interaction.user.id))
                    if adding is True:
                        if str(interaction.guild.id) not in self.bot.exceptional_role_id:
                            self.bot.exceptional_role_id[str(interaction.guild.id)] = []
                        self.bot.exceptional_role_id[str(interaction.guild.id)].append(role.id) # integer

                        await interaction.edit_original_response(
                            content=f"{interaction.user.mention}, added ignore role `{role.name}` successfully!"
                        )
                        await self.utils.log_to_channel(
                            self.bot.config['discord']['log_channel'],
                            f"{interaction.user.name} / `{interaction.user.id}` in guild `{interaction.guild.id}`"\
                            f" added a role `{role.name} / {role.id}` to ignore list."
                        )
                        await self.utils.log_to_channel(
                            self.bot.log_channel_guild[str(interaction.guild.id)],
                            f"{interaction.user.name} / `{interaction.user.id}` executed `/ignore addrole `{role.name} / {role.id}`."
                        )
                    else:
                        await interaction.edit_original_response(
                            content=f"{interaction.user.mention}, internal error when adding role. Please report!"
                        )
                        await self.utils.log_to_channel(
                            self.bot.config['discord']['log_channel'],
                            f"{interaction.user.name} / `{interaction.user.id}` in guild `{interaction.guild.id}`"\
                            f" faied to add a role `{role.name} / {role.id}` to ignore list."
                        )
                        await self.utils.log_to_channel(
                            self.bot.log_channel_guild[str(interaction.guild.id)],
                            f"{interaction.user.name} / `{interaction.user.id}` failed to execute `/ignore addrole `{role.name}`."
                        )
        except Exception as e:
            traceback.print_exc(file=sys.stdout)

    @checks.has_permissions(ban_members=True)
    @ignore_group.command(
        name="delrole",
        description="Delete a role from ignore list of namefilter."
    )
    async def command_ignore_delete_role(
        self,
        interaction: discord.Interaction,
        role: discord.Role
    ) -> None:
        """ /ignore delrole <Role Name> """
        """ This is private """
        try:
            await interaction.response.send_message(f"{interaction.user.mention} ignore loading...", ephemeral=True)
            # re-check perm
            try:
                is_mod = await self.utils.is_moderator(interaction.guild, interaction.user.id)
                if is_mod is False:
                    await interaction.edit_original_response(
                        content=f"{interaction.user.mention}, permission denied."
                    )
                    return
            except Exception as e:
                traceback.print_exc(file=sys.stdout)
            # end of re-check perm

            if str(interaction.guild.id) not in self.bot.log_channel_guild or \
                self.bot.log_channel_guild[str(interaction.guild.id)] is None:
                await interaction.edit_original_response(
                    content=f"{interaction.user.mention}, please set log channel first with `/logchan #channel`."
                )
                return
            else:
                # Check permission
                check_perm = await self.utils.get_bot_perm(interaction.guild)
                if check_perm is None:
                    await interaction.edit_original_response(
                        content=f"{interaction.user.mention}, internal error. Check again later!"
                    )
                    await self.utils.log_to_channel(
                        self.bot.config['discord']['log_channel'],
                        f"{interaction.user.name} / `{interaction.user.id}` execute command in guild `{interaction.guild.id}`"\
                        f" but failed to check bot's permission in their guild."
                    )
                    return
                else:
                    if check_perm['kick_members'] is False or check_perm['ban_members'] is False:
                        await interaction.edit_original_response(
                            content=f"{interaction.user.mention}, bot has no permission to ban/kick member!"\
                                " Please adjust permission and re-try."
                        )
                        await self.utils.log_to_channel(
                            self.bot.log_channel_guild[str(interaction.guild.id)],
                            f"{interaction.user.mention} / `{interaction.user.id}`, please check if Bot has permission kick/ban."
                        )
                        return
                # End of check permission
                get_exceptional_roles = await self.utils.get_exceptional_roles_list(str(interaction.guild.id))
                if len(get_exceptional_roles) == 0:
                    await interaction.edit_original_response(
                        content=f"{interaction.user.mention}, there is nothing to delete."
                    )
                else:
                    existing_role_ids = [int(each['role_id']) for each in get_exceptional_roles]
                    if role.id not in existing_role_ids:
                        await interaction.edit_original_response(
                            content=f"{interaction.user.mention}, role `{role.name} / {role.id}`"\
                                "is not in ignore list!"
                        )
                    else:
                        deleting = await self.utils.delete_exceptional_role(
                            str(interaction.guild.id), str(role.id), str(interaction.user.id)
                        )
                        if deleting is True:
                            try:
                                self.bot.exceptional_role_id[str(interaction.guild.id)].remove(role.id)
                            except Exception as e:
                                traceback.print_exc(file=sys.stdout)

                            await interaction.edit_original_response(
                                content=f"{interaction.user.mention}, successfully removed ignore role `{role.name} / {role.id}`."
                            )
                            await self.utils.log_to_channel(
                                self.bot.config['discord']['log_channel'],
                                f"{interaction.user.name} / `{interaction.user.id}` in guild `{interaction.guild.id}`"\
                                f" deleted a role `{role.name} / {role.id}` from ignore list."
                            )
                            await self.utils.log_to_channel(
                                self.bot.log_channel_guild[str(interaction.guild.id)],
                                f"{interaction.user.name} / `{interaction.user.id}` executed `/ignore delrole `{role.name} / {role.id}`."
                            )
                        else:
                            await interaction.edit_original_response(
                                content=f"{interaction.user.mention}, failed to remove ignore role `{role.name} / {role.id}`."\
                                    " Please report!"
                            )
                            await self.utils.log_to_channel(
                                self.bot.config['discord']['log_channel'],
                                f"{interaction.user.name} / `{interaction.user.id}` in guild `{interaction.guild.id}`"\
                                f" faied to delete a role `{role.name} / {role.id}` from ignore list."
                            )
                            await self.utils.log_to_channel(
                                self.bot.log_channel_guild[str(interaction.guild.id)],
                                f"{interaction.user.name} / `{interaction.user.id}` failed to execute `/ignore delrole `{role.name}`."
                            )
        except Exception as e:
            traceback.print_exc(file=sys.stdout)

    namefilter_group = app_commands.Group(name="namefilter", guild_only=True, description="name filter management.")

    @checks.has_permissions(ban_members=True)
    @namefilter_group.command(
        name="apply",
        description="Apply pending regex."
    )
    async def command_namefilter_apply(
        self,
        interaction: discord.Interaction
    ) -> None:
        """ /namefilter apply """
        """ This is private """
        await interaction.response.send_message(f"{interaction.user.mention} namefilter loading...", ephemeral=True)
        # re-check perm
        try:
            is_mod = await self.utils.is_moderator(interaction.guild, interaction.user.id)
            if is_mod is False:
                await interaction.edit_original_response(
                    content=f"{interaction.user.mention}, permission denied."
                )
                return
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
        # end of re-check perm

        if str(interaction.guild.id) not in self.bot.log_channel_guild or \
            self.bot.log_channel_guild[str(interaction.guild.id)] is None:
            await interaction.edit_original_response(
                content=f"{interaction.user.mention}, please set log channel first with `/logchan #channel`."
            )
            return
        else:
            # Check permission
            check_perm = await self.utils.get_bot_perm(interaction.guild)
            if check_perm is None:
                await interaction.edit_original_response(
                    content=f"{interaction.user.mention}, internal error. Check again later!"
                )
                await self.utils.log_to_channel(
                    self.bot.config['discord']['log_channel'],
                    f"{interaction.user.name} / `{interaction.user.id}` execute command in guild `{interaction.guild.id}`"\
                    f" but failed to check bot's permission in their guild."
                )
                return
            else:
                if check_perm['kick_members'] is False or check_perm['ban_members'] is False:
                    await interaction.edit_original_response(
                        content=f"{interaction.user.mention}, bot has no permission to ban/kick member!"\
                            " Please adjust permission and re-try."
                    )
                    await self.utils.log_to_channel(
                        self.bot.log_channel_guild[str(interaction.guild.id)],
                        f"{interaction.user.mention} / `{interaction.user.id}`, please check if Bot has permission kick/ban."
                    )
                    return
            # End of check permission
            try:
                if str(interaction.guild.id) in self.bot.name_filter_list_pending and\
                    len(self.bot.name_filter_list_pending[str(interaction.guild.id)]) == 0:
                    await interaction.edit_original_response(content=f"{interaction.user.mention}, "\
                        f"There is no pending namefilter to apply."
                    )
                    return
                elif str(interaction.guild.id) in self.bot.name_filter_list_pending and\
                    self.bot.name_filter_list_pending[str(interaction.guild.id)] and\
                        len(self.bot.name_filter_list_pending[str(interaction.guild.id)]) == 1:
                    # Check number of affect if reach maximum
                    regex = self.bot.name_filter_list_pending[str(interaction.guild.id)][0]
                    regex_test = r"{}".format(regex)
                    found_user_id = []
                    found_username = []
                    found_mention = []
                    get_members = interaction.guild.members

                    embed = discord.Embed(
                        title='Applying Namefilter',
                        description="Bot will scan all nick if matches after this!",
                        timestamp=datetime.now())
                    embed.add_field(
                        name="New filter",
                        value=f"`{regex}`",
                        inline=False
                    )

                    for each in get_members:
                        ignore = False
                        # check if user in ignore list role
                        if len(each.roles) > 0:
                            for r in each.roles:
                                try:
                                    if str(interaction.guild.id) in self.bot.exceptional_role_id and \
                                        r.id in self.bot.exceptional_role_id[str(interaction.guild.id)]:
                                        ignore = True
                                        break
                                except Exception as e:
                                    traceback.print_exc(file=sys.stdout)
                            if ignore is True:
                                continue
                        # check if user in ignore list
                        try:
                            if str(interaction.guild.id) in self.bot.exceptional_user_name_id and \
                                each.id in self.bot.exceptional_user_name_id[str(interaction.guild.id)] and each.bot is False:
                                continue
                        except Exception as e:
                            traceback.print_exc(file=sys.stdout)
                        # end of check if user in ignore list

                        if (self.bot.config['discord']['regex_including_bot'] == 1 and each.bot is True) or\
                            each.bot is False:
                            name = unicodedata.normalize( 'NFKC', each.display_name)
                            r = re.search(regex_test, name)
                            if r:
                                found_user_id.append(each.id)
                                found_username.append(each.display_name)
                                found_mention.append(each.mention)
                    if len(found_user_id) > 30:
                        all_user = ", ".join(found_mention[0:29])
                        embed.add_field(
                            name=f"Found {str(len(found_user_id))} user(s)",
                            value=f"user with `{regex}`.\n{all_user} and other {str(len(found_user_id)-30)} people.",
                            inline=False
                        )
                    elif len(found_user_id) > 0:
                        all_user = ", ".join(found_mention)
                        embed.add_field(
                            name=f"Found {str(len(found_user_id))} user(s)",
                            value=f"user with `{regex}`.\n{all_user}",
                            inline=False
                        )
                    else:
                        embed.add_field(
                            name=f"Currenly, found 0 user",
                            value="N/A",
                            inline=False
                        )

                    disable_apply = False
                    if len(found_user_id) > len(interaction.guild.members) * self.bot.config['discord']['max_apply_ban_ratio'] or \
                        len(found_user_id) > self.bot.config['discord']['max_apply_ban_users']:
                        disable_apply = True
                        embed.set_footer(
                            text="Apply / Confirmation disable! Too many members affected!",
                            icon_url=interaction.user.display_avatar
                        )
                        try:
                            await self.utils.log_to_channel(
                                self.bot.config['discord']['log_channel'],
                                f"{interaction.user.name} / `{interaction.user.id}` in guild `{interaction.guild.id}` "\
                                f"executed `/namefilter apply` regex `{regex}` but disable confirmation! Too many members "\
                                f"affected `{str(len(found_user_id))}` of total `{str(len(interaction.guild.members))}`."
                            )
                        except Exception as e:
                            traceback.print_exc(file=sys.stdout)
                    view = ConfirmApply(
                        self.bot, interaction, timeout=30, 
                        disable_button=False, list_users=found_user_id, 
                        disable_apply=disable_apply
                    )
                    await interaction.edit_original_response(content=None, embed=embed, view=view)
                    await view.wait()
                else:
                    await interaction.edit_original_response(content=f"{interaction.user.mention}, "\
                        f"Internal error, please report."
                    )
            except Exception as e:
                traceback.print_exc(file=sys.stdout)

    @checks.has_permissions(ban_members=True)
    @namefilter_group.command(
        name="test",
        description="Test if a given name matches."
    )
    async def command_namefilter_test(
        self,
        interaction: discord.Interaction,
        name: str
    ) -> None:
        """ /namefilter test <name> """
        """ This is public """
        name = name.strip()
        await interaction.response.send_message(f"{interaction.user.mention} namefilter loading...")

        if str(interaction.guild.id) not in self.bot.log_channel_guild or \
            self.bot.log_channel_guild[str(interaction.guild.id)] is None:
            await interaction.edit_original_response(
                content=f"{interaction.user.mention}, please set log channel first with `/logchan #channel`."
            )
            return
        else:
            # Check permission
            check_perm = await self.utils.get_bot_perm(interaction.guild)
            if check_perm is None:
                await interaction.edit_original_response(
                    content=f"{interaction.user.mention}, internal error. Check again later!"
                )
                await self.utils.log_to_channel(
                    self.bot.config['discord']['log_channel'],
                    f"{interaction.user.name} / `{interaction.user.id}` execute command in guild `{interaction.guild.id}`"\
                    f" but failed to check bot's permission in their guild."
                )
                return
            else:
                if check_perm['kick_members'] is False or check_perm['ban_members'] is False:
                    await interaction.edit_original_response(
                        content=f"{interaction.user.mention}, bot has no permission to ban/kick member!"\
                            " Please adjust permission and re-try."
                    )
                    await self.utils.log_to_channel(
                        self.bot.log_channel_guild[str(interaction.guild.id)],
                        f"{interaction.user.mention} / `{interaction.user.id}`, please check if Bot has permission kick/ban."
                    )
                    return
            # End of check permission
            try:
                regex_list = self.bot.name_filter_list[str(interaction.guild.id)]
                if len(regex_list) > 0:
                    match_list = []
                    for each in regex_list:
                        try:
                            regex_test = r"{}".format(each)
                            check_name = unicodedata.normalize( 'NFKC', name)
                            r = re.search(regex_test, check_name)
                            if r:
                                match_list.append(f"✅ regex `{each}` macth: `{name}`")
                            else:
                                match_list.append(f"❌ regex `{each}` not match: `{name}`")
                        except Exception as e:
                            traceback.print_exc(file=sys.stdout)
                    embed = discord.Embed(
                        title='Testing Namefilter',
                        description=f"Given `{name}` against `{str(len(regex_list))}` filter(s)",
                        timestamp=datetime.now())
                    embed.add_field(
                        name="Result",
                        value="\n".join(match_list),
                        inline=False
                    )
                    await interaction.edit_original_response(content=None, embed=embed)
                else:
                    await interaction.edit_original_response(
                        content=f"{interaction.user.mention}, your guild has no name filter yet."
                    )
            except Exception as e:
                traceback.print_exc(file=sys.stdout)

    @checks.has_permissions(ban_members=True)
    @namefilter_group.command(
        name="del",
        description="Delete a filter from watching."
    )
    async def command_namefilter_delete(
        self,
        interaction: discord.Interaction,
        regex: str
    ) -> None:
        """ /namefilter del <regex> """
        """ This is private """
        regex = regex.strip()
        await interaction.response.send_message(f"{interaction.user.mention} namefilter loading...", ephemeral=True)

        # re-check perm
        try:
            is_mod = await self.utils.is_moderator(interaction.guild, interaction.user.id)
            if is_mod is False:
                await interaction.edit_original_response(
                    content=f"{interaction.user.mention}, permission denied."
                )
                return
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
        # end of re-check perm

        if str(interaction.guild.id) not in self.bot.log_channel_guild or \
            self.bot.log_channel_guild[str(interaction.guild.id)] is None:
            await interaction.edit_original_response(
                content=f"{interaction.user.mention}, please set log channel first with `/logchan #channel`."
            )
            return
        else:
            # Check permission
            check_perm = await self.utils.get_bot_perm(interaction.guild)
            if check_perm is None:
                await interaction.edit_original_response(
                    content=f"{interaction.user.mention}, internal error. Check again later!"
                )
                await self.utils.log_to_channel(
                    self.bot.config['discord']['log_channel'],
                    f"{interaction.user.name} / `{interaction.user.id}` execute command in guild `{interaction.guild.id}`"\
                    f" but failed to check bot's permission in their guild."
                )
                return
            else:
                if check_perm['kick_members'] is False or check_perm['ban_members'] is False:
                    await interaction.edit_original_response(
                        content=f"{interaction.user.mention}, bot has no permission to ban/kick member!"\
                            " Please adjust permission and re-try."
                    )
                    await self.utils.log_to_channel(
                        self.bot.log_channel_guild[str(interaction.guild.id)],
                        f"{interaction.user.mention} / `{interaction.user.id}`, please check if Bot has permission kick/ban."
                    )
                    return
            # End of check permission
            try:
                get_list_regex = await self.utils.get_namefilter_list(str(interaction.guild.id))
                if len(get_list_regex) == 0:
                    await interaction.edit_original_response(content=f"{interaction.user.mention}, there is nothing to delete.")
                else:
                    regex_list = [each['regex'] for each in get_list_regex]
                    if regex not in regex_list:
                        await interaction.edit_original_response(content=f"{interaction.user.mention}, regex `{regex}` not in your exist in your Guild.")
                    else:
                        deleting = await self.utils.delete_regex(str(interaction.guild.id), regex, str(interaction.user.id))
                        if deleting is True:
                            if len(self.bot.name_filter_list_pending[str(interaction.guild.id)]) == 1 and\
                                regex == self.bot.name_filter_list_pending[str(interaction.guild.id)][0]:
                                del self.bot.name_filter_list_pending[str(interaction.guild.id)][0]
                            elif regex in self.bot.name_filter_list[str(interaction.guild.id)]:
                                self.bot.name_filter_list[str(interaction.guild.id)].remove(regex)
                            await interaction.edit_original_response(content=f"Successfully deleted regex `{regex}`")
                            await self.utils.log_to_channel(
                                self.bot.config['discord']['log_channel'],
                                f"{interaction.user.name} / `{interaction.user.id}` in guild `{interaction.guild.id}`"\
                                f" delete regex `{regex}` from pending list."
                            )
                            await self.utils.log_to_channel(
                                self.bot.log_channel_guild[str(interaction.guild.id)],
                                f"{interaction.user.name} / `{interaction.user.id}` delete regex `{regex}` from pending list."
                            )
            except Exception as e:
                traceback.print_exc(file=sys.stdout)

    @command_namefilter_delete.autocomplete('regex')
    async def regex_item_autocomplete(
        self,
        interaction: discord.Interaction,
        current: str
    ) -> List[app_commands.Choice[str]]:
        # Do stuff with the "current" parameter, e.g. querying it search results...
        list_namefilters = await self.utils.get_namefilter_list_search(str(interaction.guild.id), current, 20)
        if len(list_namefilters) > 0:
            list_namefilters = [each['regex'] for each in list_namefilters]
            return [
                app_commands.Choice(name=item, value=item)
                for item in list_namefilters if current.lower() in item.lower()
            ]
        else:
            list_namefilters = ["N/A"]
            return [
                app_commands.Choice(name=item, value=item)
                for item in list_namefilters if current.lower() in item.lower()
            ]

    @checks.has_permissions(ban_members=True)
    @namefilter_group.command(
        name="add",
        description="Add name filter to watch."
    )
    async def command_namefilter_add(
        self,
        interaction: discord.Interaction,
        regex: str
    ) -> None:
        """ /namefilter add <regex> """
        """ This is private """
        regex = regex.strip()
        await interaction.response.send_message(f"{interaction.user.mention} namefilter loading...", ephemeral=True)

        # re-check perm
        try:
            is_mod = await self.utils.is_moderator(interaction.guild, interaction.user.id)
            if is_mod is False:
                await interaction.edit_original_response(
                    content=f"{interaction.user.mention}, permission denied."
                )
                return
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
        # end of re-check perm

        try:
            if str(interaction.guild.id) not in self.bot.log_channel_guild or \
                self.bot.log_channel_guild[str(interaction.guild.id)] is None:
                await interaction.edit_original_response(
                    content=f"{interaction.user.mention}, please set log channel first with `/logchan #channel`."
                )
                return
            else:
                # Check permission
                check_perm = await self.utils.get_bot_perm(interaction.guild)
                if check_perm is None:
                    await interaction.edit_original_response(
                        content=f"{interaction.user.mention}, internal error. Check again later!"
                    )
                    await self.utils.log_to_channel(
                        self.bot.config['discord']['log_channel'],
                        f"{interaction.user.name} / `{interaction.user.id}` execute command in guild `{interaction.guild.id}`"\
                        f" but failed to check bot's permission in their guild."
                    )
                    return
                else:
                    if check_perm['kick_members'] is False or check_perm['ban_members'] is False:
                        await interaction.edit_original_response(
                            content=f"{interaction.user.mention}, bot has no permission to ban/kick member!"\
                                " Please adjust permission and re-try."
                        )
                        await self.utils.log_to_channel(
                            self.bot.log_channel_guild[str(interaction.guild.id)],
                            f"{interaction.user.mention} / `{interaction.user.id}`, please check if Bot has permission kick/ban."
                        )
                        return
                # End of check permission
                if len(regex) < self.bot.config['discord']['minimum_regex_length']:
                    await interaction.edit_original_response(
                        content=f"{interaction.user.mention}, given regex `{regex}` is too short. "\
                            f"It should not be shorter than `{self.bot.config['discord']['minimum_regex_length']}` chars "\
                            f"or longer than `{self.bot.config['discord']['maximum_regex_length']}`."
                    )
                    await self.utils.log_to_channel(
                        self.bot.log_channel_guild[str(interaction.guild.id)],
                        f"{interaction.user.name} / `{interaction.user.id}` executed `/namefilter add {regex}` "\
                        f"but it's too short (requires between `{self.bot.config['discord']['minimum_regex_length']}` to "\
                        f"`{self.bot.config['discord']['maximum_regex_length']}`)."
                    )
                    return
                elif len(regex) > self.bot.config['discord']['maximum_regex_length']:
                    await interaction.edit_original_response(
                        content=f"{interaction.user.mention}, given regex `{regex}` is too long. "\
                            f"It should not be shorter than `{self.bot.config['discord']['minimum_regex_length']}` "\
                            f"or longer than `{self.bot.config['discord']['maximum_regex_length']}` chars."
                        )
                    await self.utils.log_to_channel(
                        self.bot.log_channel_guild[str(interaction.guild.id)],
                        f"{interaction.user.name} / `{interaction.user.id}` executed `/namefilter add {regex}` "\
                        f"but it's too long (requires between `{self.bot.config['discord']['minimum_regex_length']}` to "\
                        f"`{self.bot.config['discord']['maximum_regex_length']}`)."
                    )
                    return

                try:
                    if str(interaction.guild.id) in self.bot.name_filter_list and\
                        len(self.bot.name_filter_list[str(interaction.guild.id)]) >= self.bot.maximum_regex[str(interaction.guild.id)]:
                        await interaction.edit_original_response(content=f"{interaction.user.mention}, "\
                            f"Your guild `{interaction.guild.name}` has maximum of name filter already "\
                            f"`{str(self.bot.maximum_regex[str(interaction.guild.id)])}`."
                        )
                        await self.utils.log_to_channel(
                            self.bot.config['discord']['log_channel'],
                            f"Guild `{interaction.guild.name}` has maximum of name filter already "\
                            f"`{str(self.bot.maximum_regex[str(interaction.guild.id)])}`."
                        )
                        await self.utils.log_to_channel(
                            self.bot.log_channel_guild[str(interaction.guild.id)],
                            f"{interaction.user.name} / `{interaction.user.id}` executed `/namefilter add {regex}` "\
                            f"but it reaches maximum regex already `{str(self.bot.maximum_regex[str(interaction.guild.id)])}`."
                        )
                        return
                except Exception as e:
                    traceback.print_exc(file=sys.stdout)

                try:
                    if str(interaction.guild.id) in self.bot.name_filter_list_pending and\
                        self.bot.name_filter_list_pending[str(interaction.guild.id)] and\
                            len(self.bot.name_filter_list_pending[str(interaction.guild.id)]) > 0:
                        old_regex = self.bot.name_filter_list_pending[str(interaction.guild.id)][0]
                        await interaction.edit_original_response(content=f"{interaction.user.mention}, "\
                            f"There is still pending `{old_regex}` to apply. Please apply with `/namefilter apply` first."
                        )
                        return
                except Exception as e:
                    traceback.print_exc(file=sys.stdout)
                try:
                    if check_regex(regex) is False:
                        try:
                            await self.utils.log_to_channel(
                                self.bot.log_channel_guild[str(interaction.guild.id)],
                                f"{interaction.user.name} / `{interaction.user.id}` executed `/namefilter {regex}`. "\
                                f"Given regex `{regex}` is invalid. Please test with <https://regex101.com/>."
                            )
                        except Exception as e:
                            traceback.print_exc(file=sys.stdout)
                        await interaction.edit_original_response(
                            content=f"{interaction.user.mention}, given regex `{regex}` is invalid. "\
                                "Please test with <https://regex101.com/>."
                        )
                        return
                    else:
                        # add this guild key if not exist
                        if str(interaction.guild.id) not in self.bot.name_filter_list_pending:
                            self.bot.name_filter_list_pending[str(interaction.guild.id)] = []

                        if str(interaction.guild.id) in self.bot.name_filter_list and\
                            self.bot.name_filter_list[str(interaction.guild.id)] and\
                                regex in self.bot.name_filter_list[str(interaction.guild.id)]:
                                await interaction.edit_original_response(
                                    content=f"{interaction.user.mention}, given regex `{regex}` is already exist!"
                                )
                                return
                        else:
                            adding = await self.utils.insert_new_regex(str(interaction.guild.id), regex, str(interaction.user.id))
                            if adding is True:
                                self.bot.name_filter_list_pending[str(interaction.guild.id)].append(regex)
                                await interaction.edit_original_response(
                                    content=f"{interaction.user.mention}, added `{regex}` to pending list."\
                                        " Please use `/namefilter apply` to save."
                                )
                                await self.utils.log_to_channel(
                                    self.bot.log_channel_guild[str(interaction.guild.id)],
                                    f"{interaction.user.name} / `{interaction.user.id}` executed `/namefilter add {regex}`."
                                )
                            else:
                                await interaction.edit_original_response(
                                    content=f"{interaction.user.mention}, internal error during adding `{regex}`. Please report!"
                                )
                except Exception as e:
                    traceback.print_exc(file=sys.stdout)
        except Exception as e:
            traceback.print_exc(file=sys.stdout)

    @checks.has_permissions(ban_members=True)
    @namefilter_group.command(
        name="list",
        description="Get name filter list."
    )
    async def command_namefilter_list(
        self,
        interaction: discord.Interaction,
    ) -> None:
        """ /namefilter list """
        """ This is private """
        await interaction.response.send_message(f"{interaction.user.mention} namefilter loading...", ephemeral=True)
        # re-check perm
        try:
            is_mod = await self.utils.is_moderator(interaction.guild, interaction.user.id)
            if is_mod is False:
                await interaction.edit_original_response(
                    content=f"{interaction.user.mention}, permission denied."
                )
                return
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
        # end of re-check perm

        if str(interaction.guild.id) not in self.bot.log_channel_guild or \
            self.bot.log_channel_guild[str(interaction.guild.id)] is None:
            await interaction.edit_original_response(content=f"{interaction.user.mention}, please set log channel first with `/logchan #channel`.")
            return

        # Check permission
        check_perm = await self.utils.get_bot_perm(interaction.guild)
        if check_perm is None:
            await interaction.edit_original_response(
                content=f"{interaction.user.mention}, internal error. Check again later!"
            )
            await self.utils.log_to_channel(
                self.bot.config['discord']['log_channel'],
                f"{interaction.user.name} / `{interaction.user.id}` execute command in guild `{interaction.guild.id}`"\
                f" but failed to check bot's permission in their guild."
            )
            return
        else:
            if check_perm['kick_members'] is False or check_perm['ban_members'] is False:
                await interaction.edit_original_response(
                    content=f"{interaction.user.mention}, bot has no permission to ban/kick member!"\
                        " Please adjust permission and re-try."
                )
                await self.utils.log_to_channel(
                    self.bot.log_channel_guild[str(interaction.guild.id)],
                    f"{interaction.user.mention} / `{interaction.user.id}`, please check if Bot has permission kick/ban."
                )
                return
        # End of check permission

        regex_list = await self.utils.get_namefilter_list(str(interaction.guild.id))
        if len(regex_list) > 0:
            re_list = []
            for each in regex_list:
                added_time = discord.utils.format_dt(
                    datetime.fromtimestamp(each['added_date']), style='R'
                )
                status = "`pending`"
                if each['is_active'] == 1:
                    status = "`active`"
                re_list.append("`{}`, added by <@{}> on {} status: {}".format(
                    each['regex'],
                    each['added_by'],
                    added_time,
                    status
                ))
            re_list_str = "\n".join(re_list) if len(re_list) > 0 else "N/A"
            await interaction.edit_original_response(
                content=f"{interaction.user.mention},\n {re_list_str}\n"\
                    f"Used: `{str(len(re_list))}`\nRemaining namefilter: `{str(self.bot.maximum_regex[str(interaction.guild.id)]-len(re_list))}`"
            )  
            await self.utils.log_to_channel(
                self.bot.log_channel_guild[str(interaction.guild.id)],
                f"{interaction.user.name} / `{interaction.user.id}` requested `/namefilter list`"
            )
        else:
            await interaction.edit_original_response(content=f"{interaction.user.mention}, there is not any regex in this guild yet.")    

    @checks.has_permissions(ban_members=True)
    @app_commands.command(
        name="logchan",
        description="Set log channel."
    )
    async def command_logchan(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel
    ) -> None:
        """ /logchan <#channel> """
        """ This is private """
        await interaction.response.send_message(f"{interaction.user.mention} setting log channel...", ephemeral=True)
        if type(channel) is not discord.TextChannel:
            await interaction.edit_original_response(content=f"{interaction.user.mention}, that's not text channel.")
            return

        # re-check perm
        try:
            is_mod = await self.utils.is_moderator(interaction.guild, interaction.user.id)
            if is_mod is False:
                await interaction.edit_original_response(
                    content=f"{interaction.user.mention}, permission denied."
                )
                return
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
        # end of re-check perm

        if str(interaction.guild.id) not in self.bot.log_channel_guild:
            # doesn't have data, insert guild to it
            try:
                await self.utils.insert_new_guild(str(interaction.guild.id), interaction.guild.name)
                self.bot.log_channel_guild[str(interaction.guild.id)] = channel.id
                # reload data
                await self.utils.load_reload_bot_data()
            except Exception as e:
                traceback.print_exc(file=sys.stdout)
                await interaction.edit_original_response(content=f"{interaction.user.mention}, internal error, please report.")
                await self.utils.log_to_channel(
                    self.bot.config['discord']['log_channel'],
                    f"{interaction.user.name} / `{interaction.user.id}` in guild "\
                    f"`{interaction.guild.name} / {interaction.guild.id}` executed "\
                    f"`/logchan {channel.name}` and failed to insert to DB."
                )

        if str(interaction.guild.id) in self.bot.log_channel_guild:
            if self.bot.log_channel_guild[str(interaction.guild.id)] and \
                self.bot.log_channel_guild[str(interaction.guild.id)] == channel.id:
                await interaction.edit_original_response(content=f"{interaction.user.mention}, that was already set before to {channel.mention}. Nothing changes.")
                return
            try:
                await channel.send(
                    f"I will put all log to this channel {channel.mention}, set by {interaction.user.mention}."
                )
                await self.utils.set_log_channel(str(interaction.guild.id), str(channel.id), str(interaction.user.id))
                self.bot.log_channel_guild[str(interaction.guild.id)] = channel.id
                await self.utils.log_to_channel(
                    self.bot.log_channel_guild[str(interaction.guild.id)],
                    f"{interaction.user.name} / `{interaction.user.id}` update logchan to "\
                    f"{channel.name}."
                )
                await self.utils.log_to_channel(
                    self.bot.config['discord']['log_channel'],
                    f"{interaction.user.name} / `{interaction.user.id}` update logchan in guild "\
                    f"`{interaction.guild.name} / {interaction.guild.id}` to "\
                    f"{channel.name}."
                )
                await interaction.edit_original_response(content=f"{interaction.user.mention}, log channel set to {channel.mention}.")
                await self.utils.load_reload_bot_data()
            except discord.errors.Forbidden:
                await interaction.edit_original_response(content=f"{interaction.user.mention}, error. Maybe I don't have access to that channel.")
                await self.utils.log_to_channel(
                    self.bot.config['discord']['log_channel'],
                    f"{interaction.user.name} / `{interaction.user.id}` in guild "\
                    f"`{interaction.guild.name} / {interaction.guild.id}` executed "\
                    f"`/logchan {channel.name}` and failed with permission."
                )
                return
            except Exception as e:
                traceback.print_exc(file=sys.stdout)
                await interaction.edit_original_response(content=f"{interaction.user.mention}, internal error, please report.")
                await self.utils.log_to_channel(
                    self.bot.config['discord']['log_channel'],
                    f"{interaction.user.name} / `{interaction.user.id}` in guild "\
                    f"`{interaction.guild.name} / {interaction.guild.id}` executed "\
                    f"`/logchan {channel.name}` and failed to update to DB."
                )

    @checks.has_permissions(ban_members=True)
    @app_commands.command(
        name="scannick",
        description="Scan all users in the guild with regex matches."
    )
    async def command_scannick(
        self,
        interaction: discord.Interaction,
        regex: str
    ) -> None:
        """ /scannick <regex> """
        """ This is private """
        regex = regex.strip()
        await interaction.response.send_message(f"{interaction.user.mention} scanning nicks...", ephemeral=True)

        # re-check perm
        try:
            is_mod = await self.utils.is_moderator(interaction.guild, interaction.user.id)
            if is_mod is False:
                await interaction.edit_original_response(
                    content=f"{interaction.user.mention}, permission denied."
                )
                return
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
        # end of re-check perm

        if str(interaction.guild.id) not in self.bot.log_channel_guild or \
            self.bot.log_channel_guild[str(interaction.guild.id)] is None:
            await interaction.edit_original_response(content=f"{interaction.user.mention}, please set log channel first with `/logchan #channel`.")
            return
        else:
            if len(regex) < self.bot.config['discord']['minimum_regex_length']:
                await interaction.edit_original_response(content=f"{interaction.user.mention}, given regex `{regex}` is too short.")
                return
            elif len(regex) > self.bot.config['discord']['maximum_regex_length']:
                await interaction.edit_original_response(content=f"{interaction.user.mention}, given regex `{regex}` is too long.")
                return

            if check_regex(regex) is False:
                try:
                    await self.utils.log_to_channel(
                        self.bot.log_channel_guild[str(interaction.guild.id)],
                        f"{interaction.user.name} / `{interaction.user.id}` executed `/scannick {regex}`. "\
                        f"Given regex `{regex}` is invalid. Please test with <https://regex101.com/>."
                    )
                except Exception as e:
                    traceback.print_exc(file=sys.stdout)
                await interaction.edit_original_response(
                    content=f"{interaction.user.mention}, "\
                    f"given regex `{regex}` is invalid. Please test with <https://regex101.com/>."
                )
                return
            else:
                try:
                    regex_test = r"{}".format(regex)
                    found_user_id = []
                    found_username = []
                    found_mention = []
                    get_members = interaction.guild.members
                    for each in get_members:
                        if (self.bot.config['discord']['regex_including_bot'] == 1 and each.bot is True) or\
                            each.bot is False:
                            r = re.search(regex_test, str(each))
                            if r:
                                found_user_id.append(each.id)
                                found_username.append(str(each))
                                found_mention.append(each.mention)
                    if len(found_user_id) > 50:
                        all_user = ", ".join(found_mention[0:49])
                        await interaction.edit_original_response(
                            content=f"{interaction.user.mention}, found {str(len(found_user_id))} "\
                                f"user with `{regex}`.\n{all_user} and other {str(len(found_user_id)-50)}"
                            )
                    elif len(found_user_id) > 0:
                        all_user = ", ".join(found_mention)
                        await interaction.edit_original_response(
                            content=f"{interaction.user.mention}, found {str(len(found_user_id))} "\
                                f"user with `{regex}`.\n{all_user}"
                            )
                    else:
                        await interaction.edit_original_response(content=f"{interaction.user.mention}, found 0 user with `{regex}`.")
                except Exception as e:
                    traceback.print_exc(file=sys.stdout)

    messagefilter_group = app_commands.Group(name="messagefilter", guild_only=True, description="message filter management.")

    @checks.has_permissions(manage_messages=True)
    @messagefilter_group.command(
        name="add",
        description="Add new message filter."
    )
    async def command_messagefilter_add(
        self,
        interaction: discord.Interaction,
        content: str
    ) -> None:
        """ /messagefilter add """
        """ This is private """
        content = content.strip()
        await interaction.response.send_message(f"{interaction.user.mention} messagefilter loading...", ephemeral=True)
        # re-check perm
        try:
            is_mod = await self.utils.is_managed_message(interaction.guild, interaction.user.id)
            if is_mod is False:
                await interaction.edit_original_response(
                    content=f"{interaction.user.mention}, permission denied."
                )
                return
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
        # end of re-check perm
        if str(interaction.guild.id) not in self.bot.log_channel_guild or \
            self.bot.log_channel_guild[str(interaction.guild.id)] is None:
            await interaction.edit_original_response(
                content=f"{interaction.user.mention}, please set log channel first with `/logchan #channel`."
            )
            return
        try:
            if interaction.guild.id not in self.bot.enable_message_filter:
                await interaction.edit_original_response(
                    content=f"{interaction.user.mention}, your guild didn't enable `messagefilter`. Do it with `/messagefilter on`."
                )
                return
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
        try:
            if len(content) < 10 or len(content) > 1000:
                await interaction.edit_original_response(
                    content=f"{interaction.user.mention}, the message content is too short or too long. "\
                        "It should not be shorter than 10 chars or longer than 1000 chars."
                )
                return
            else:
                if str(interaction.guild.id) in self.bot.message_filters and \
                    len(self.bot.message_filters[str(interaction.guild.id)]) > 0:
                    # Check if similiar to any added
                    matches = False
                    matched_text = None
                    for each in self.bot.message_filters[str(interaction.guild.id)]:
                        compare = fuzz.ratio(content, each)
                        if (len(content) > 40 and compare >= 80) or \
                            (len(content) <= 40 and compare >= 90):
                            matches = True
                            matched_text = each
                            break
                    if matches is True:
                        await interaction.edit_original_response(
                            content=f"{interaction.user.mention}, you new content filter is similiar to below:```{matched_text}```"
                        )
                        return
                    else:
                        if len(self.bot.message_filters[str(interaction.guild.id)]) >= 30:
                            await interaction.edit_original_response(
                                content=f"{interaction.user.mention}, your guild already reached max message filter."
                            )
                            return
                        else:
                            adding = await self.utils.insert_new_msg_filter(
                                str(interaction.guild.id), content, str(interaction.user.id)
                            )
                            if adding is True:
                                await interaction.edit_original_response(
                                    content=f"{interaction.user.mention}, successfully added a new message filter."
                                )
                                try:
                                    await self.utils.log_to_channel(
                                        self.bot.log_channel_guild[str(interaction.guild.id)],
                                        f"{interaction.user.name} / `{interaction.user.id}` added a new message filter:"\
                                        f"```{content}```"
                                    )
                                except Exception as e:
                                    traceback.print_exc(file=sys.stdout)
                else:
                    adding = await self.utils.insert_new_msg_filter(
                        str(interaction.guild.id), content, str(interaction.user.id)
                    )
                    if adding is True:
                        await interaction.edit_original_response(
                            content=f"{interaction.user.mention}, successfully added a new message filter."
                        )
                        try:
                            await self.utils.log_to_channel(
                                self.bot.log_channel_guild[str(interaction.guild.id)],
                                f"{interaction.user.name} / `{interaction.user.id}` added a new message filter:"\
                                f"```{content}```"
                            )
                        except Exception as e:
                            traceback.print_exc(file=sys.stdout)
                        # reload data
                await self.utils.load_reload_bot_data()
        except Exception as e:
            traceback.print_exc(file=sys.stdout)

    @checks.has_permissions(manage_messages=True)
    @messagefilter_group.command(
        name="list",
        description="List active message filter."
    )
    async def command_messagefilter_list(
        self,
        interaction: discord.Interaction
    ) -> None:
        """ /messagefilter list """
        """ This is private """
        await interaction.response.send_message(f"{interaction.user.mention} messagefilter loading...", ephemeral=True)
        # re-check perm
        try:
            is_mod = await self.utils.is_managed_message(interaction.guild, interaction.user.id)
            if is_mod is False:
                await interaction.edit_original_response(
                    content=f"{interaction.user.mention}, permission denied."
                )
                return
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
        # end of re-check perm

        if str(interaction.guild.id) not in self.bot.log_channel_guild or \
            self.bot.log_channel_guild[str(interaction.guild.id)] is None:
            await interaction.edit_original_response(
                content=f"{interaction.user.mention}, please set log channel first with `/logchan #channel`."
            )
            return
        try:
            if interaction.guild.id not in self.bot.enable_message_filter:
                await interaction.edit_original_response(
                    content=f"{interaction.user.mention}, your guild didn't enable `messagefilter`. Do it with `/messagefilter on`."
                )
                return
            else:
                if str(interaction.guild.id) not in self.bot.message_filters or \
                    len(self.bot.message_filters[str(interaction.guild.id)]) == 0:
                    await interaction.edit_original_response(
                        content=f"{interaction.user.mention}, your guild doesn't have any message contents to filter yet."\
                            " You can add by `/messagefilter add`"
                    )
                    return
                else:
                    get_msg_filter = await self.utils.get_msg_filter_list(str(interaction.guild.id))
                    if len(get_msg_filter) > 0:
                        list_msg_filters = []
                        i = 1
                        for each in get_msg_filter:
                            content = each['content'][0:30] + "..." if len(each['content']) > 31 else each['content']
                            list_msg_filters.append("{})=> {}".format(i, content))
                            i += 1
                        list_msg_filters_str = "\n".join(list_msg_filters)
                        await interaction.edit_original_response(
                            content=f"{interaction.user.mention}, filter list:"\
                                f"```{list_msg_filters_str}```"
                        )
                    else:
                        await interaction.edit_original_response(
                            content=f"{interaction.user.mention}, your guild doesn't have any message contents to filter yet."\
                                " You can add by `/messagefilter add`"
                        )
                    return
        except Exception as e:
            traceback.print_exc(file=sys.stdout)

    @checks.has_permissions(manage_messages=True)
    @messagefilter_group.command(
        name="on",
        description="Turn message filter on."
    )
    async def command_messagefilter_turn_on(
        self,
        interaction: discord.Interaction
    ) -> None:
        """ /messagefilter on """
        """ This is private """
        await interaction.response.send_message(f"{interaction.user.mention} messagefilter loading...", ephemeral=True)
        # re-check perm
        try:
            is_mod = await self.utils.is_managed_message(interaction.guild, interaction.user.id)
            if is_mod is False:
                await interaction.edit_original_response(
                    content=f"{interaction.user.mention}, permission denied."
                )
                return
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
        # end of re-check perm
        if str(interaction.guild.id) not in self.bot.log_channel_guild or \
            self.bot.log_channel_guild[str(interaction.guild.id)] is None:
            await interaction.edit_original_response(
                content=f"{interaction.user.mention}, please set log channel first with `/logchan #channel`."
            )
            return
        try:
            if interaction.guild.id in self.bot.enable_message_filter:
                await interaction.edit_original_response(
                    content=f"{interaction.user.mention}, your guild already have `messagefilter` ON."
                )
                return
            else:
                updating = await self.utils.update_guild_msg_filter_on_off(
                    str(interaction.guild.id), 1
                )
                if updating:
                    await interaction.edit_original_response(
                        content=f"{interaction.user.mention}, successfully set `messagefilter` ON."
                    )
                    self.bot.enable_message_filter.append(interaction.guild.id)
                    try:
                        await self.utils.log_to_channel(
                            self.bot.log_channel_guild[str(interaction.guild.id)],
                            f"{interaction.user.name} / `{interaction.user.id}` turn message filter ON."
                        )
                    except Exception as e:
                        traceback.print_exc(file=sys.stdout)
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
    
    @checks.has_permissions(manage_messages=True)
    @messagefilter_group.command(
        name="off",
        description="Turn message filter on."
    )
    async def command_messagefilter_turn_off(
        self,
        interaction: discord.Interaction
    ) -> None:
        """ /messagefilter off """
        """ This is private """
        await interaction.response.send_message(f"{interaction.user.mention} messagefilter loading...", ephemeral=True)
        # re-check perm
        try:
            is_mod = await self.utils.is_managed_message(interaction.guild, interaction.user.id)
            if is_mod is False:
                await interaction.edit_original_response(
                    content=f"{interaction.user.mention}, permission denied."
                )
                return
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
        # end of re-check perm
        if str(interaction.guild.id) not in self.bot.log_channel_guild or \
            self.bot.log_channel_guild[str(interaction.guild.id)] is None:
            await interaction.edit_original_response(
                content=f"{interaction.user.mention}, please set log channel first with `/logchan #channel`."
            )
            return
        try:
            if interaction.guild.id not in self.bot.enable_message_filter:
                await interaction.edit_original_response(
                    content=f"{interaction.user.mention}, your guild `messagefilter` is currently OFF."
                )
                return
            else:
                updating = await self.utils.update_guild_msg_filter_on_off(
                    str(interaction.guild.id), 0
                )
                if updating:
                    await interaction.edit_original_response(
                        content=f"{interaction.user.mention}, successfully set `messagefilter` OFF."
                    )
                    if interaction.guild.id in self.bot.enable_message_filter:
                        self.bot.enable_message_filter.remove(interaction.guild.id)
                    try:
                        await self.utils.log_to_channel(
                            self.bot.log_channel_guild[str(interaction.guild.id)],
                            f"{interaction.user.name} / `{interaction.user.id}` turn message filter OFF."
                        )
                    except Exception as e:
                        traceback.print_exc(file=sys.stdout)
        except Exception as e:
            traceback.print_exc(file=sys.stdout)

    @checks.has_permissions(manage_messages=True)
    @messagefilter_group.command(
        name="del",
        description="Delete a message filter."
    )
    async def command_messagefilter_delete_message_filter(
        self,
        interaction: discord.Interaction,
        content_id: str
    ) -> None:
        """ /messagefilter del <regex> """
        """ This is private """
        await interaction.response.send_message(f"{interaction.user.mention} messagefilter loading...", ephemeral=True)
        # re-check perm
        try:
            is_mod = await self.utils.is_managed_message(interaction.guild, interaction.user.id)
            if is_mod is False:
                await interaction.edit_original_response(
                    content=f"{interaction.user.mention}, permission denied."
                )
                return
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
        # end of re-check perm
        if str(interaction.guild.id) not in self.bot.log_channel_guild or \
            self.bot.log_channel_guild[str(interaction.guild.id)] is None:
            await interaction.edit_original_response(
                content=f"{interaction.user.mention}, please set log channel first with `/logchan #channel`."
            )
            return
        try:
            if interaction.guild.id not in self.bot.enable_message_filter:
                await interaction.edit_original_response(
                    content=f"{interaction.user.mention}, your guild didn't enable `messagefilter`. Do it with `/messagefilter on`."
                )
                return
            else:
                if len(self.bot.message_filters[str(interaction.guild.id)]) == 0:
                    await interaction.edit_original_response(
                        content=f"{interaction.user.mention}, your guild doesn't have any message contents to filter yet."\
                            " You can add by `/messagefilter add`"
                    )
                    return
                else:
                    get_msg_filter = await self.utils.get_msg_filter_list(str(interaction.guild.id))
                    if len(get_msg_filter) > 0:
                        content_id = int(content_id)
                        list_existing_ids = [each['message_filters_id'] for each in get_msg_filter]
                        if content_id not in list_existing_ids:
                            await interaction.edit_original_response(
                                content=f"{interaction.user.mention}, that ID doesn't belong to your guild."
                            )
                        else:
                            content = None
                            for each in get_msg_filter:
                                if each['message_filters_id'] == content_id:
                                    content = each['content']
                                    break
                            deleting = await self.utils.delete_msg_filter(
                                str(interaction.guild.id), content_id, str(interaction.user.id)
                            )
                            if deleting is True:
                                await interaction.edit_original_response(
                                    content=f"{interaction.user.mention}, successfully deleted filter:```{content}```"
                                )
                                await self.utils.log_to_channel(
                                    self.bot.log_channel_guild[str(interaction.guild.id)],
                                    f"{interaction.user.name} / `{interaction.user.id}` removed message filter content:```{content}```"
                                )
                                self.bot.message_filters[str(interaction.guild.id)].remove(content)
                    else:
                        await interaction.edit_original_response(
                            content=f"{interaction.user.mention}, your guild doesn't have any message contents to filter yet."\
                                " You can add by `/messagefilter add`"
                        )
                    return
        except Exception as e:
            traceback.print_exc(file=sys.stdout)

    @command_messagefilter_delete_message_filter.autocomplete('content_id')
    async def content_id_autocomplete(
        self,
        interaction: discord.Interaction,
        current: str
    ) -> List[app_commands.Choice[str]]:
        # Do stuff with the "current" parameter, e.g. querying it search results...
        list_auto_filters = await self.utils.get_msg_filter_list_search(str(interaction.guild.id), current, 8)
        content_list = []
        item_list_ids = []
        if len(list_auto_filters) > 0:
            for each in list_auto_filters:
                if each['message_filters_id'] not in item_list_ids:
                    content = each['content'][0:30] + "..." if len(each['content']) > 31 else each['content']
                    content_list.append(content)
                    item_list_ids.append(str(each['message_filters_id']))
            return [
                app_commands.Choice(name=item, value=item_list_ids[content_list.index(item)])
                for item in content_list if current.lower() in item.lower()
            ]
        else:
            list_filters = ["N/A"]
            return [
                app_commands.Choice(name=item, value=item)
                for item in list_filters if current.lower() in item.lower()
            ]

    @commands.Cog.listener()
    async def on_ready(self):
        pass

    async def cog_load(self) -> None:
        pass

    async def cog_unload(self) -> None:
        pass


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Commanding(bot))
