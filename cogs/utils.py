import re
from discord.ext import commands, tasks
import discord
import traceback, sys
import aiomysql
from aiomysql.cursors import DictCursor
import time

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
                    if result:
                        for each in result:
                            if each['log_channel_id']:
                                self.bot.log_channel_guild[each['guild_id']] = int(each['log_channel_id'])
                            else:
                                self.bot.log_channel_guild[each['guild_id']] = None
                            self.bot.max_ignored_user[each['guild_id']] = each['max_ignored_users']
                            self.bot.max_ignored_role[each['guild_id']] = each['max_ignored_roles']
                            self.bot.maximum_regex[each['guild_id']] = each['maximum_regex']
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
                    return True
        except Exception:
            traceback.print_exc(file=sys.stdout)
        return False

    async def load_reload_bot_data_by_guild_id(self, guild_id: str):
        try:
            await self.open_connection()
            async with self.db_pool.acquire() as conn:
                async with conn.cursor() as cur:
                    # exceptional_roles
                    sql = """ SELECT * FROM `exceptional_roles` WHERE `guild_id`=%s """
                    await cur.execute(sql, guild_id)
                    result = await cur.fetchall()
                    self.bot.exceptional_role_id[each['guild_id']] = []
                    if result:
                        for each in result:
                            self.bot.exceptional_role_id[each['guild_id']].append(int(each['role_id']))
                    # exceptional_users
                    sql = """ SELECT * FROM `exceptional_users` WHERE `guild_id`=%s """
                    await cur.execute(sql, guild_id)
                    result = await cur.fetchall()
                    self.bot.exceptional_user_name_id[each['guild_id']] = []
                    if result:
                        for each in result:
                            self.bot.exceptional_user_name_id[each['guild_id']].append(int(each['user_id']))
                    # guild_list
                    sql = """ SELECT * FROM `guild_list` WHERE `guild_id`=%s LIMIT 1 """
                    await cur.execute(sql, guild_id)
                    result = await cur.fetchone()
                    self.bot.log_channel_guild[guild_id] = None
                    self.bot.max_ignored_user[guild_id] = None
                    self.bot.max_ignored_role[guild_id] = None
                    self.bot.maximum_regex[guild_id] = None
                    if result:
                        if result['log_channel_id']:
                            self.bot.log_channel_guild[guild_id] = int(result['log_channel_id'])
                            self.bot.max_ignored_user[guild_id] = result['max_ignored_users']
                            self.bot.max_ignored_role[guild_id] = result['max_ignored_roles']
                            self.bot.maximum_regex[guild_id] = result['maximum_regex']
                        else:
                            self.bot.log_channel_guild[guild_id] = None
                            self.bot.max_ignored_user[guild_id] = None
                            self.bot.max_ignored_role[guild_id] = None
                            self.bot.maximum_regex[guild_id] = None
                    # name_filters
                    sql = """ SELECT * FROM `name_filters` WHERE `guild_id`=%s """
                    await cur.execute(sql, guild_id)
                    result = await cur.fetchall()
                    self.bot.name_filter_list[each['guild_id']] = []
                    self.bot.name_filter_list_pending[each['guild_id']] = []
                    if result:
                        for each in result:
                            if each['is_active'] == 1:
                                self.bot.name_filter_list[each['guild_id']].append(each['regex'])
                            elif each['is_active'] == 0:
                                self.bot.name_filter_list_pending[each['guild_id']].append(each['regex'])
        except Exception:
            traceback.print_exc(file=sys.stdout)

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
                    sql = """ SELECT * FROM `name_filters` WHERE `guild_id`=%s """
                    await cur.execute(sql, guild_id)
                    result = await cur.fetchall()
                    if result and len(result) > 0 :
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
                    # exceptional_users
                    sql = """ SELECT * FROM `exceptional_users` WHERE `guild_id`=%s """
                    await cur.execute(sql, guild_id)
                    result = await cur.fetchall()
                    if result and len(result) > 0:
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
                    # exceptional_roles
                    sql = """ SELECT * FROM `exceptional_roles` WHERE `guild_id`=%s """
                    await cur.execute(sql, guild_id)
                    result = await cur.fetchall()
                    if result and len(result) > 0:
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

    async def bot_can_kick_ban(self, guild):
        try:
            get_bot_user = guild.get_member(self.bot.user.id)
            return dict(get_bot_user.guild_permissions)
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
        return None

    async def user_can_kick_ban(self, guild, user_id):
        try:
            get_user = guild.get_member(user_id)
            return dict(get_user.guild_permissions)
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
        return None

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