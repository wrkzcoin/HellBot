import re
from discord.ext import commands, tasks
import discord
import traceback, sys
import aiomysql
from aiomysql.cursors import DictCursor
import time
import hashlib

def check_regex(given: str):
    try:
        re.compile(given)
        is_valid = True
    except re.error:
        is_valid = False
    return is_valid


# Cog class
class Utils(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot: commands.Bot = bot
        self.db_pool = None

    async def open_connection(self):
        try:
            if self.db_pool is None:
                self.db_pool = await aiomysql.create_pool(
                    host=self.bot.config['mysql']['host'], port=3306, minsize=1, maxsize=2,
                    user=self.bot.config['mysql']['user'], password=self.bot.config['mysql']['password'],
                    db=self.bot.config['mysql']['db'], cursorclass=DictCursor, autocommit=True
                )
        except Exception:
            traceback.print_exc(file=sys.stdout)

    async def load_reload_bot_data(self):
        try:
            await self.open_connection()
            async with self.db_pool.acquire() as conn:
                async with conn.cursor() as cur:
                    # exceptional_roles
                    sql = """ SELECT * FROM `exceptional_roles` """
                    await cur.execute(sql, )
                    result = await cur.fetchall()
                    if result:
                        self.bot.exceptional_role_id = {}
                        for each in result:
                            if each['guild_id'] not in self.bot.exceptional_role_id:
                                self.bot.exceptional_role_id[each['guild_id']] = []
                            self.bot.exceptional_role_id[each['guild_id']].append(int(each['role_id']))
                    # exceptional_users
                    sql = """ SELECT * FROM `exceptional_users` """
                    await cur.execute(sql, )
                    result = await cur.fetchall()
                    self.bot.exceptional_user_name_id = {}
                    if result:
                        for each in result:
                            if each['guild_id'] not in self.bot.exceptional_user_name_id:
                                self.bot.exceptional_user_name_id[each['guild_id']] = []
                            self.bot.exceptional_user_name_id[each['guild_id']].append(int(each['user_id']))
                    # guild_list
                    sql = """ SELECT * FROM `guild_list` """
                    await cur.execute(sql, )
                    result = await cur.fetchall()
                    self.bot.log_channel_guild = {}
                    self.bot.max_ignored_user = {}
                    self.bot.max_ignored_role = {}
                    self.bot.maximum_regex = {}
                    self.bot.enable_message_filter = []
                    if result:
                        for each in result:
                            if each['log_channel_id']:
                                self.bot.log_channel_guild[each['guild_id']] = int(each['log_channel_id'])
                            else:
                                self.bot.log_channel_guild[each['guild_id']] = None
                            self.bot.max_ignored_user[each['guild_id']] = each['max_ignored_users']
                            self.bot.max_ignored_role[each['guild_id']] = each['max_ignored_roles']
                            self.bot.maximum_regex[each['guild_id']] = each['maximum_regex']
                            if each['enable_message_filter'] == 1:
                                self.bot.enable_message_filter.append(int(each['guild_id']))
                    else:
                        self.bot.log_channel_guild[each['guild_id']] = None
                    # name_filters
                    sql = """ SELECT * FROM `name_filters` """
                    await cur.execute(sql, )
                    result = await cur.fetchall()
                    self.bot.name_filter_list = {}
                    self.bot.name_filter_list_pending = {}
                    if result:
                        for each in result:
                            if each['guild_id'] not in self.bot.name_filter_list:
                                self.bot.name_filter_list[each['guild_id']] = []
                            if each['guild_id'] not in self.bot.name_filter_list_pending:
                                self.bot.name_filter_list_pending[each['guild_id']] = []

                            if each['is_active'] == 1:
                                self.bot.name_filter_list[each['guild_id']].append(each['regex'])
                            elif each['is_active'] == 0:
                                self.bot.name_filter_list_pending[each['guild_id']].append(each['regex'])
                    # message filter
                    sql = """ SELECT * FROM `message_filters` """
                    await cur.execute(sql, )
                    result = await cur.fetchall()
                    self.bot.message_filters = {}
                    if result:
                        for each in result:
                            if each['guild_id'] not in self.bot.message_filters:
                                self.bot.message_filters[each['guild_id']] = []
                            self.bot.message_filters[each['guild_id']].append(each['content'])
                    # message filter template
                    sql = """ SELECT sha1(`content`) AS hashtext, `message_filters_template`.* 
                    FROM `message_filters_template` """
                    await cur.execute(sql, )
                    result = await cur.fetchall()
                    self.bot.message_filter_templates = []
                    self.bot.message_filter_templates_kv = {}
                    if result:
                        for each in result:
                            if each['is_active'] == 1:
                                self.bot.message_filter_templates.append(each['content'])
                                self.bot.message_filter_templates_kv[each['hashtext']] = each
                    return True
        except Exception:
            traceback.print_exc(file=sys.stdout)
        return False

    async def set_log_channel(self, guild_id: str, channel_id: str, set_by: str):
        try:
            await self.open_connection()
            async with self.db_pool.acquire() as conn:
                async with conn.cursor() as cur:
                    # exceptional_roles
                    sql = """ UPDATE `guild_list` 
                    SET `log_channel_id`=%s, `set_by`=%s, `set_date`=%s 
                    WHERE `guild_id`=%s LIMIT 1"""
                    await cur.execute(sql, (channel_id, set_by, int(time.time()), guild_id))
                    await conn.commit()
                    return True
        except Exception:
            traceback.print_exc(file=sys.stdout)
        return False

    async def insert_new_guild(self, guild_id: str, guild_name: str):
        try:
            await self.open_connection()
            async with self.db_pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ INSERT INTO `guild_list` (`guild_id`, `guild_name`, `guild_joined_date`)
                    VALUES (%s, %s, %s)
                    ON DUPLICATE KEY UPDATE 
                    `guild_joined_date`=VALUES(`guild_joined_date`)
                    """
                    await cur.execute(sql, (guild_id, guild_name, int(time.time())))
                    await conn.commit()
                    return True
        except Exception:
            traceback.print_exc(file=sys.stdout)
        return False

    async def get_namefilter_list(self, guild_id: str):
        try:
            await self.open_connection()
            async with self.db_pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ SELECT * FROM `name_filters` 
                    WHERE `guild_id`=%s
                    """
                    await cur.execute(sql, guild_id)
                    result = await cur.fetchall()
                    if result:
                        return result
        except Exception:
            traceback.print_exc(file=sys.stdout)
        return []

    async def get_namefilter_list_search(self, guild_id: str, like: str, limit: int=20):
        try:
            await self.open_connection()
            async with self.db_pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ SELECT * FROM `name_filters` 
                    WHERE `guild_id`=%s AND `regex` LIKE %s LIMIT """+str(limit)
                    await cur.execute(sql, (guild_id, "%" + like + "%"))
                    result = await cur.fetchall()
                    if result:
                        return result
        except Exception:
            traceback.print_exc(file=sys.stdout)
        return []

    async def get_exceptional_roles_list(self, guild_id: str):
        try:
            await self.open_connection()
            async with self.db_pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ SELECT * FROM `exceptional_roles` 
                    WHERE `guild_id`=%s
                    """
                    await cur.execute(sql, guild_id)
                    result = await cur.fetchall()
                    if result:
                        return result
        except Exception:
            traceback.print_exc(file=sys.stdout)
        return []

    async def insert_new_exceptional_role(self, guild_id: str, role_id: str, added_by: str):
        try:
            await self.open_connection()
            async with self.db_pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ INSERT INTO `exceptional_roles` 
                    (`guild_id`, `role_id`, `added_by`, `added_date`)
                    VALUES (%s, %s, %s, %s)
                    """
                    await cur.execute(sql, (guild_id, role_id, added_by, int(time.time())))
                    await conn.commit()
                    return True
        except Exception:
            traceback.print_exc(file=sys.stdout)
        return False

    async def delete_exceptional_role(self, guild_id: str, role_id: str, deleted_by: str):
        try:
            await self.open_connection()
            async with self.db_pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """
                    SELECT * FROM `exceptional_roles`
                    WHERE `guild_id`=%s AND `role_id`=%s
                    LIMIT 1
                    """
                    await cur.execute(sql, (guild_id, role_id))
                    result = await cur.fetchone()
                    if result:
                        sql = """ INSERT INTO `exceptional_roles_deleted` 
                        (`guild_id`, `role_id`, `added_by`, `added_date`, `deleted_by`, `deleted_date`)
                        VALUES (%s, %s, %s, %s, %s, %s);
                        DELETE FROM `exceptional_roles`
                        WHERE `guild_id`=%s AND `role_id`=%s;
                        """
                        await cur.execute(sql, (
                            guild_id, role_id, result['added_by'], 
                            result['added_date'], deleted_by, int(time.time()),
                            guild_id, role_id
                        ))
                        await conn.commit()
                        return True
        except Exception:
            traceback.print_exc(file=sys.stdout)
        return False

    async def get_exceptional_users_list(self, guild_id: str):
        try:
            await self.open_connection()
            async with self.db_pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ SELECT * FROM `exceptional_users` 
                    WHERE `guild_id`=%s
                    """
                    await cur.execute(sql, guild_id)
                    result = await cur.fetchall()
                    if result:
                        return result
        except Exception:
            traceback.print_exc(file=sys.stdout)
        return []

    async def insert_new_exceptional_user(self, guild_id: str, user_id: str, added_by: str):
        try:
            await self.open_connection()
            async with self.db_pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ INSERT INTO `exceptional_users` 
                    (`guild_id`, `user_id`, `added_by`, `added_date`)
                    VALUES (%s, %s, %s, %s)
                    """
                    await cur.execute(sql, (guild_id, user_id, added_by, int(time.time())))
                    await conn.commit()
                    return True
        except Exception:
            traceback.print_exc(file=sys.stdout)
        return False

    async def delete_exceptional_user(self, guild_id: str, member_id: str, deleted_by: str):
        try:
            await self.open_connection()
            async with self.db_pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """
                    SELECT * FROM `exceptional_users`
                    WHERE `guild_id`=%s AND `user_id`=%s
                    LIMIT 1
                    """
                    await cur.execute(sql, (guild_id, member_id))
                    result = await cur.fetchone()
                    if result:
                        sql = """ INSERT INTO `exceptional_users_deleted` 
                        (`guild_id`, `user_id`, `added_by`, `added_date`, `deleted_by`, `deleted_date`)
                        VALUES (%s, %s, %s, %s, %s, %s);
                        DELETE FROM `exceptional_users`
                        WHERE `guild_id`=%s AND `user_id`=%s;
                        """
                        await cur.execute(sql, (
                            guild_id, member_id, result['added_by'], 
                            result['added_date'], deleted_by, int(time.time()),
                            guild_id, member_id
                        ))
                        await conn.commit()
                        return True
        except Exception:
            traceback.print_exc(file=sys.stdout)
        return False

    async def delete_guild(self, guild_id: str):
        try:
            await self.open_connection()
            async with self.db_pool.acquire() as conn:
                async with conn.cursor() as cur:
                    has_data_purge = False
                    sql = """
                    SELECT * FROM `guild_list` WHERE `guild_id`=%s LIMIT 1
                    """
                    await cur.execute(sql, guild_id)
                    result = await cur.fetchone()
                    if result:
                        sql = """ INSERT INTO `guild_list_deleted` 
                        (`guild_id`, `guild_name`, `guild_joined_date`, `log_channel_id`, `left_date`)
                        VALUES (%s, %s, %s, %s, %s)

                        """
                        await cur.execute(sql, (
                            guild_id, result['guild_name'], result['guild_joined_date'], result['log_channel_id'], int(time.time())
                        ))
                        await conn.commit()
                    # name_filter_list
                    has_namefilter = False
                    sql = """ SELECT * FROM `name_filters` WHERE `guild_id`=%s """
                    await cur.execute(sql, guild_id)
                    result = await cur.fetchall()
                    if result and len(result) > 0 :
                        has_namefilter = True
                        has_data_purge = True
                        sql = """ INSERT INTO `name_filters_deleted` 
                        (`guild_id`, `regex`, `added_by`, `added_date`, `is_active`, `deleted_by`, `deleted_date`)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                        """
                        data_rows = []
                        for each in result:
                            data_rows.append((
                                each['guild_id'], each['regex'], each['added_by'], each['added_date'], 
                                each['is_active'], "LEFT", int(time.time())
                            ))
                        if len(data_rows) > 0:
                            await cur.executemany(sql, data_rows)
                            await conn.commit()
                    # exceptional_users
                    has_ignore_users = False
                    sql = """ SELECT * FROM `exceptional_users` WHERE `guild_id`=%s """
                    await cur.execute(sql, guild_id)
                    result = await cur.fetchall()
                    if result and len(result) > 0:
                        has_ignore_users = True
                        has_data_purge = True
                        sql = """ INSERT INTO `exceptional_users_deleted` 
                        (`guild_id`, `user_id`, `added_by`, `added_date`, `deleted_by`, `deleted_date`)
                        VALUES (%s, %s, %s, %s, %s, %s)
                        """
                        data_rows = []
                        for each in result:
                            data_rows.append((
                                each['guild_id'], each['user_id'], each['added_by'], each['added_date'], 
                                "LEFT", int(time.time())
                            ))
                        if len(data_rows) > 0:
                            await cur.executemany(sql, data_rows)
                            await conn.commit()
                    # exceptional_roles
                    has_ignore_roles = False
                    sql = """ SELECT * FROM `exceptional_roles` WHERE `guild_id`=%s """
                    await cur.execute(sql, guild_id)
                    result = await cur.fetchall()
                    if result and len(result) > 0:
                        has_ignore_roles = True
                        has_data_purge = True
                        sql = """ INSERT INTO `exceptional_roles_deleted` 
                        (`guild_id`, `role_id`, `added_by`, `added_date`, `deleted_by`, `deleted_date`)
                        VALUES (%s, %s, %s, %s, %s, %s)
                        """
                        data_rows = []
                        for each in result:
                            data_rows.append((
                                each['guild_id'], each['role_id'], each['added_by'], each['added_date'], 
                                "LEFT", int(time.time())
                            ))
                        if len(data_rows) > 0:
                            await cur.executemany(sql, data_rows)
                            await conn.commit()

                    # message_filters
                    has_messagefilter = False
                    sql = """ SELECT * FROM `message_filters` WHERE `guild_id`=%s """
                    await cur.execute(sql, guild_id)
                    result = await cur.fetchall()
                    if result and len(result) > 0 :
                        has_messagefilter = True
                        has_data_purge = True
                        sql = """ INSERT INTO `message_filters_deleted` 
                        (`guild_id`, `content`, `added_by`, `added_date`, `deleted_by`, `deleted_date`)
                        VALUES (%s, %s, %s, %s, %s, %s)
                        """
                        data_rows = []
                        for each in result:
                            data_rows.append((
                                each['guild_id'], each['content'], each['added_by'], each['added_date'], 
                                "LEFT", int(time.time())
                            ))
                        if len(data_rows) > 0:
                            await cur.executemany(sql, data_rows)
                            await conn.commit()

                    params = []
                    sql = """ DELETE FROM `guild_list` WHERE `guild_id`=%s;
                    """
                    params.append(guild_id)
                    if has_data_purge is True:
                        # delete name_filters
                        if has_namefilter is True:
                            sql += """ DELETE FROM `name_filters` WHERE `guild_id`=%s;
                                """
                            params.append(guild_id)

                        # delete exceptional_users
                        if has_ignore_users is True:
                            sql += """ DELETE FROM `exceptional_users` WHERE `guild_id`=%s;
                                """
                            params.append(guild_id)

                        # delete exceptional_roles
                        if has_ignore_roles is True:
                            sql += """ DELETE FROM `exceptional_roles` WHERE `guild_id`=%s;
                                """
                            params.append(guild_id)

                        # delete message_filters
                        if has_messagefilter is True:
                            sql += """ DELETE FROM `message_filters` WHERE `guild_id`=%s;
                                """
                            params.append(guild_id)
                        # all now
                    await cur.execute(sql, tuple(params))
                    await conn.commit()
                    return True
        except Exception:
            traceback.print_exc(file=sys.stdout)
        return False

    async def insert_new_regex(self, guild_id: str, regex: str, added_by: str):
        try:
            await self.open_connection()
            async with self.db_pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ INSERT INTO `name_filters` (`guild_id`, `regex`, `added_by`, `added_date`)
                    VALUES (%s, %s, %s, %s)
                    """
                    await cur.execute(sql, (guild_id, regex, added_by, int(time.time())))
                    await conn.commit()
                    return True
        except Exception:
            traceback.print_exc(file=sys.stdout)
        return False

    async def delete_regex(self, guild_id: str, regex: str, deleted_by: str):
        try:
            await self.open_connection()
            async with self.db_pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ SELECT * FROM `name_filters` 
                    WHERE `guild_id`=%s and `regex`=%s
                    LIMIT 1
                    """
                    await cur.execute(sql, (guild_id, regex))
                    result = await cur.fetchone()
                    if result:
                        sql = """ INSERT INTO `name_filters_deleted` 
                        (`guild_id`, `regex`, `is_active`, `added_by`, `added_date`, `deleted_by`, `deleted_date`)
                        VALUES (%s, %s, %s, %s, %s, %s, %s);

                        DELETE FROM `name_filters`
                        WHERE `guild_id`=%s and `regex`=%s;
                        """
                        await cur.execute(sql, (
                            guild_id, regex, result['is_active'], result['added_by'],
                            result['added_date'], deleted_by, int(time.time()),
                            guild_id, regex
                        ))
                        await conn.commit()
                        return True
        except Exception:
            traceback.print_exc(file=sys.stdout)
        return False

    async def update_regex_on(self, guild_id: str, regex: str):
        try:
            await self.open_connection()
            async with self.db_pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ UPDATE `name_filters` 
                    SET `is_active`=1 WHERE `guild_id`=%s AND `regex`=%s
                    LIMIT 1
                    """
                    await cur.execute(sql, (guild_id, regex))
                    await conn.commit()
                    return True
        except Exception:
            traceback.print_exc(file=sys.stdout)
        return False

    async def update_message_filters_template_trigger(self, msg_tpl_id: int):
        try:
            await self.open_connection()
            async with self.db_pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ UPDATE `message_filters_template` 
                    SET `triggered`=`triggered`+1 WHERE `msg_tpl_id`=%s
                    LIMIT 1
                    """
                    await cur.execute(sql, msg_tpl_id)
                    await conn.commit()
                    return True
        except Exception:
            traceback.print_exc(file=sys.stdout)
        return False

    async def insert_new_msg_filter(self, guild_id: str, content: str, added_by: str):
        try:
            await self.open_connection()
            async with self.db_pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ INSERT INTO `message_filters` (`guild_id`, `content`, `added_by`, `added_date`)
                    VALUES (%s, %s, %s, %s)
                    """
                    await cur.execute(sql, (guild_id, content, added_by, int(time.time())))
                    await conn.commit()
                    return True
        except Exception:
            traceback.print_exc(file=sys.stdout)
        return False

    async def update_guild_msg_filter_on_off(self, guild_id: int, value: int):
        try:
            await self.open_connection()
            async with self.db_pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ UPDATE `guild_list` 
                    SET `enable_message_filter`=%s
                    WHERE `guild_id`=%s
                    LIMIT 1
                    """
                    await cur.execute(sql, (value, guild_id))
                    await conn.commit()
                    return True
        except Exception:
            traceback.print_exc(file=sys.stdout)
        return False

    async def get_msg_filter_list(self, guild_id: str):
        try:
            await self.open_connection()
            async with self.db_pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ SELECT * FROM `message_filters` 
                    WHERE `guild_id`=%s
                    """
                    await cur.execute(sql, guild_id)
                    result = await cur.fetchall()
                    if result:
                        return result
        except Exception:
            traceback.print_exc(file=sys.stdout)
        return []

    async def get_msg_filter_list_search(
        self, guild_id: str, like: str, limit: int = 8
    ):
        try:
            await self.open_connection()
            async with self.db_pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ SELECT * FROM `message_filters` 
                    WHERE `guild_id`=%s AND `content` LIKE %s LIMIT """+str(limit)
                    await cur.execute(sql, (guild_id, "%" + like + "%"))
                    result = await cur.fetchall()
                    if result:
                        return result
        except Exception:
            traceback.print_exc(file=sys.stdout)
        return []

    async def delete_msg_filter(
        self, guild_id: str, message_filters_id: int, deleted_by: str
    ):
        try:
            await self.open_connection()
            async with self.db_pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ SELECT * FROM `message_filters` 
                    WHERE `guild_id`=%s AND `message_filters_id`=%s
                    LIMIT 1
                    """
                    await cur.execute(sql, (guild_id, message_filters_id))
                    result = await cur.fetchone()
                    if result:
                        sql = """ INSERT INTO `message_filters_deleted` 
                        (`guild_id`, `content`, `added_by`, `added_date`, `deleted_by`, `deleted_date`)
                        VALUES (%s, %s, %s, %s, %s, %s);

                        DELETE FROM `message_filters`
                        WHERE `guild_id`=%s AND `message_filters_id`=%s;
                        """
                        await cur.execute(sql, (
                            guild_id, result['content'], result['added_by'],
                            result['added_date'], deleted_by, int(time.time()),
                            guild_id, message_filters_id
                        ))
                        await conn.commit()
                        return True
        except Exception:
            traceback.print_exc(file=sys.stdout)
        return False
    
    async def add_deleted_message_log(
        self, message_content: str, matched_content: str, ratio: float, guild_id: str, user_id: str
    ):
        try:
            await self.open_connection()
            async with self.db_pool.acquire() as conn:
                async with conn.cursor() as cur:
                    sql = """ INSERT INTO `log_deleted_message` 
                    (`message_content`, `matched_content`, `ratio`, `guild_id`, `author_id`, `inserted_time`)
                    VALUES (%s, %s, %s, %s, %s, %s);
                    """
                    await cur.execute(sql, (
                        message_content, matched_content, ratio, guild_id, user_id, int(time.time())
                    ))
                    await conn.commit()
                    return True
        except Exception:
            traceback.print_exc(file=sys.stdout)
        return False

    async def log_to_channel(self, channel_id: int, content: str) -> None:
        try:
            channel = self.bot.get_channel(channel_id)
            if channel:
                try:
                    await channel.send(content)
                except Exception as e:
                    traceback.print_exc(file=sys.stdout)
        except Exception as e:
            traceback.print_exc(file=sys.stdout)

    async def get_bot_perm(self, guild):
        try:
            get_bot_user = guild.get_member(self.bot.user.id)
            return dict(get_bot_user.guild_permissions)
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
        return None

    async def get_user_perms(self, guild, user_id):
        try:
            get_user = guild.get_member(user_id)
            return dict(get_user.guild_permissions)
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
        return None

    async def is_managed_message(self, guild, user_id):
        try:
            get_user = guild.get_member(user_id)
            check_perm = dict(get_user.guild_permissions)
            if check_perm and (check_perm['manage_channels'] is True) or \
                (check_perm['manage_messages'] is True):
                return True
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
        return False

    async def is_moderator(self, guild, user_id):
        """
        Sample permission dict
        {
            'create_instant_invite': True,
            'kick_members': False,
            'ban_members': False,
            'administrator': True,
            'manage_channels': True,
            'manage_guild': True,
            'add_reactions': True,
            'view_audit_log': True,
            'priority_speaker': False,
            'stream': True,
            'view_channel': True,
            'send_messages': True,
            'send_tts_messages': True,
            'manage_messages': False,
            'embed_links': True,
            'attach_files': True,
            'read_message_history': True,
            'mention_everyone': True,
            'external_emojis': True,
            'view_guild_insights': False,
            'connect': True,
            'speak': True,
            'mute_members': False,
            'deafen_members': False,
            'move_members': False,
            'use_voice_activation': True,
            'change_nickname': True,
            'manage_nicknames': False,
            'manage_roles': True,
            'manage_webhooks': False,
            'manage_emojis': False,
            'use_slash_commands': True,
            'request_to_speak': True,
            'manage_events': False,
            'manage_threads': False,
            'create_public_threads': False,
            'create_private_threads': False,
            'external_stickers': False,
            'send_messages_in_threads': False,
            'start_embedded_activities': False,
            'moderate_members': False}
        """
        try:
            get_user = guild.get_member(user_id)
            check_perm = dict(get_user.guild_permissions)
            if check_perm and (check_perm['manage_channels'] is True) or \
                (check_perm['ban_members'] is True):
                return True
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
        return False

    @commands.Cog.listener()
    async def on_ready(self):
        # load guild and data
        load_data = await self.load_reload_bot_data()
        if load_data is True:
            await self.log_to_channel(
                self.bot.config['discord']['log_channel'],
                "Database is loaded..."
            )

    async def cog_load(self) -> None:
        pass

    async def cog_unload(self) -> None:
        pass

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Utils(bot))