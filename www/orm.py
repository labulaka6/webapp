#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
ORM,即对象关系映射,在这用于建立类与数据库表的映射
特点:把表映射成类，把行（记录）映射为实例，把字段映射为实例的属性
因为数据库中每张表的字段都不一样，所以需要动态的生成类，此时元类排上用场
类是对象的模板，元类是类的模板。User类继承自Model类，而Model则根据ModelMetaClass动态创建
所以User间接的根据ModelMetaClass创建
"""

__author__ = 'labulaka6'

import logging
import asyncio
import aiomysql
import sys

#打印使用过的sql语句
def log(sql, args = ()):
    logging.info("SQL: %s" % sql)

# 创建全局数据库连接池，使每个http请求都能从连接池中直接获取数据库连接
# 使用连接池的好处是不必频繁地打开和关闭数据库连接，而是能复用就尽量复用
async def create_pool(loop, **kw):
    logging.info("create database connection pool...")
    # 声明为全局变量，这样其他函数才可以使用
    global __pool
    # 调用一个子协程来创建全局连接池，create_pool的返回值是一个pool实例对象
    __pool = await aiomysql.create_pool(
        # dict.get(key, default)
        host = kw.get("host", "localhost"),  # 数据库服务器的位置，默认为本地
        port = kw.get("port", 3306),  # mysql的端口，默认为3306
        user = kw["user"],  # 登陆用户名，默认为root
        password = kw["password"],  # 口令密码
        db = kw["db"],  # 当前数据库名
        charset = kw.get("charset", "utf8"),  # 设置连接使用的编码格式
        autocommit = kw.get("autocommit", True),  # 自动提交模式，此处默认是False
        maxsize = kw.get("maxsize", 10),  # 最大连接池大小，默认是10
        minsize = kw.get("minsize", 1),  # 最小连接池大小，默认是1，保证了任何时候都有一个数据库连接
        loop = loop  # 设置消息循环
    )

# 关闭连接池
async def destory_pool():
    global __pool
    if __pool is not None:
        __pool.close()
        await __pool.wait_closed()

# 将数据库的select操作封装在select函数中
# sql形参即为sql语句，args表示填入sql的选项值
# size用于指定最大的查询数量，不指定将返回所有查询结果
async def select(sql, args, size = None):
    log(sql, args)
    global __pool
    # 从连接池中获取一条数据库连接
    with (await __pool) as conn:
        # 打开一个DictCursor，它与普通游标的不同在于，以dict形式返回结果
        cur = await conn.cursor(aiomysql.DictCursor)
        # sql语句的占位符是?，而mysql的占位符是%s，select()函数在内部自动替换
        # 注意要始终坚持使用带参数的SQL，而不是自己拼接SQL字符串，这样可以防止SQL注入攻击
        await cur.execute(sql.replace("?", "%s"), args or ())
        if size:  # 若制定了size，则返回相应数量的查询信息
            rs = await cur.fetchmany(size)
        else:  # 若未指定size，则返回全部的查询信息
            rs = await cur.fetchall()
        await cur.close()  # 关闭游标
        logging.info("rows return %s" % len(rs))
        return rs

# 增删改都是对数据库的修改，可以封装到一个函数中
async def execute(sql, args):
    log(sql)
    with (await __pool) as conn:  # 从连接池中取出一条数据库连接
        # 若数据库的事务为非自动提交的，则调用协程启动连接
        if not conn.get_autocommit():  # 根据aiomysql文档，修改autocommit为obj.get_autocommit()
            await conn.begin()
        try:
            cur = await conn.cursor()  # 此处打开的是一个普通游标
            await cur.execute(sql.replace("?", "%s"), args)  # 执行增删改
            affected = cur.rowcount  # 增删改影响的行数
            await cur.close()  # 执行结束，关闭游标
            if not conn.get_autocommit():  # 同上，事务非自动提交型的,手动调用协程提交增删改事务
                await conn.commit()
        except BaseException as e:
            if not conn.get_autocommit():  # 出错，回滚事务到增删改之前
                await conn.rollback()
            raise
        return affected  # 返回增删改所影响的行数，以便对执行结果的正确与否进行判断

# 构造占位符，作用是创建一定数量的占位符
def create_args_string(num):
    L = []
    for n in range(num):
        L.append("?")
    return ', '.join(L)

# 父域，可被其他域继承
class Field(object):
    # 域的初始化, 包括属性(列)名,属性(列)的类型,是否主键
    # default参数允许orm自己填入缺省值,因此具体的使用请看的具体的类怎么使用
    # 比如User有一个定义在StringField的id,default就用于存储用户的独立id
    # 再比如created_at的default就用于存储创建时间的浮点表示
    def __init__(self, name, column_type, primary_key, default):
        self.name = name
        self.column_type = column_type
        self.primary_key = primary_key
        self.default = default

    # 用于打印信息,依次为类名(域名),属性类型,属性名
    def __str__(self):
        return "<%s, %s:%s>" % (self.__class__.__name__, self.column_type, self.name)

# 下面定义了5个数据类型
# 字符串域
class StringField(Field):
    # ddl("data definition languages"),用于定义数据类型，对应父域的column_type
    # varchar("variable char"), 可变长度的字符串,以下定义中的100表示最长长度,即字符串的可变范围为0~100
    # (char,为不可变长度字符串,会用空格字符补齐)
    def __init__(self, name=None, primary_key=False, default=None, ddl="varchar(100)"):
        super().__init__(name, ddl, primary_key, default)

# 整数域
class IntegerField(Field):
    def __init__(self, name=None, primary_key=False, default=0):
        super().__init__(name, "bigint", primary_key, default)

# 布尔域，注意布尔类型不可以作为主键，所以primary_key一定为False
class BooleanField(Field):
    def __init__(self, name=None, default=False):
        super().__init__(name, "boolean", False, default)

# 浮点数域
class FloatField(Field):
    def __init__(self, name=None, primary_key=False, default=0.0):
        super().__init__(name, "real", primary_key, default)

# 文本域
class TextField(Field):
    def __init__(self, name=None, default=None):
        super().__init__(name, "text", False, default)



# 任何定义了__metacalss__属性或指定了metaclass的都会通过元类定义的构造方法构造类
class ModelMetacalss(type):
    def __new__(cls, name, bases, attrs):
        # cls: 当前准备创建的类对象，相当于self
        # name: 类名，比如User继承自Model，当使用该元类创建User类时，name=User
        # bases: 父类的元组
        # attrs: 属性(方法)的字典，比如User有__table__,id,等,就作为attrs的key
        # 排除Model类本身，因为Model类主要就是用来被继承的，其不存在与数据库表的映射
        if name == "Model":
            return type.__new__(cls, name, bases, attrs)

        # 以下是针对"Model"子类的处理，将被用于子类的创建.metaclass将被隐式的继承

        # 获取表名，若没有定义__table__属性，将类名作为表名.此处注意 or 的用法
        tableName = attrs.get("__table__", None) or name
        logging.info("found model: %s (table: %s)" % (name, tableName))
        # 获取所有的Field和主键名
        mappings = dict()  # 用字典来储存类属性与数据库表的列所属的域的映射关系
        fields = []  # 用与保存初主键外的属性
        primaryKey = None # 用于保存主键

        # 遍历类的属性，找出定义的域(如StringField，字符串域)内的值，建立映射关系
        # k是属性名，v其实是定义域 请看name=StringField(ddl="varchar(50)")
        for k, v in attrs.items():
            if isinstance(v, Field):  # 如果是所定义的域
                logging.info(" found mapping: %s ==> %s" % (k, v))
                mappings[k] = v  # 建立映射关系
                if v.primary_key:  # 找到主键
                    if primaryKey:  # 若主键已存在，又找到一个主键，将报错，每张表有且仅有一个主键
                        raise RuntimeError("Duplicate primary key for field: %s" % k)
                    primaryKey = k
                else:
                    fields.append(k)
        if not primaryKey:  # 没有找到主键也将报错，因为每张表有且仅有一个主键
            raise RuntimeError("Primary key not found")
        # 从类属性中删除已加入映射字典的键，避免后面实例属性重名覆盖掉
        for k in mappings.keys():
            attrs.pop(k)
        # 将非主键的属性加上反引号，放入escaped_fields中，方便增删改查语句的书写
        escaped_fields = list(map(lambda f: "`%s`" % f, fields))
        attrs["__mappings__"] = mappings  # 保存属性和列的映射关系
        attrs["__table__"] = tableName  # 保存表名
        attrs["__primary_key__"] = primaryKey  # 保存主键
        attrs["__fields__"] = fields  # 保存非主键的属性名

        # 构造默认的select, insert, update, delete语句（模板语句）,使用?作为占位符
        attrs["__select__"] = "select `%s`, %s from `%s`" % (primaryKey, ', '.join(escaped_fields), tableName)
        # 此处利用create_args_string生成的若干个?占位
        # 插入数据时,要指定属性名,并对应的填入属性值
        attrs["__insert__"] = "insert into `%s` (%s, `%s`) values (%s)" % (
            tableName, ', '.join(escaped_fields), primaryKey, create_args_string(len(escaped_fields) + 1))
        # 通过主键查找到记录并更新
        attrs["__update__"] = "update `%s` set %s where `%s`=?" % (
            tableName, ', '.join(map(lambda f: "`%s`=?" % (mappings.get(f).name or f), fields)), primaryKey)
        # 通过主键删除
        attrs["__delete__"] = "delete from `%s` where `%s`=?" % (tableName, primaryKey)
        return type.__new__(cls, name, bases, attrs)  # 返回一个定制过的类

# ORM映射基类，继承自dict，通过ModelMetaclass元类来构造类
# ModelMetaclass元类只是定制了相关的属性，而Model类提供了操作数据库要用到的方法
class Model(dict, metaclass = ModelMetacalss):
    # 初始化函数，调用其父类(dict)的方法
    def __init__(self, **kw):
        super(Model, self).__init__(**kw)

    # 增加__getattr__方法，使获得属性更方便，即可通过"a.b"的形式
    def __getattr__(self, key):
        try:
            return self[key]
        except KeyError:
            raise AttributeError(r"'Model' object has no attribute'%s'" % key)

    # 增加__setattr__方法，使设置属性更方便，可通过"a.b=c"的形式
    def __setattr__(self, key, value):
        self[key] = value

    # 上面两个方法是用来获取和设置**kw转换而来的dict的值，而下面的getattr是用来获取当前实例的属性值，不要搞混了
    # 通过键取值，若值不存在，返回None
    def getValue(self, key):
        return getattr(self, key, None)  #getattr是内置函数

    # 通过键取值，若值不存在，返回默认值
    def getValueOrDefault(self, key):
        value = getattr(self, key, None)
        if value is None:
            field = self.__mappings__[key]  # field是一个定义域，比如FloatField
            # default这个属性在此处再次发挥作用
            if field.default is not None:
                # id的StringField.default=next_id,因此调用该函数生成独立id
                # FloatFiled.default=time.time,因此调用time.time函数返回当前时间
                # 如果是方法就直接返回调用后的值，如果是具体的值那就返回这个值
                value = field.default() if callable(field.default) else field.default
                logging.debug("using default value for %s: %s" % (key, str(value)))
                # 通过default取到值之后再将其作为当前值
                setattr(self, key, value)
        return value

    # classmethod装饰器将方法定义为类方法
    # 对于查询相关的操作，我们都定义为类方法，就可以方便查询，而不必先创建实例再查询
    @classmethod
    async def find(cls, pk):
        'find object by primary key'
        # 之前已将将数据库的select操作封装在了select函数中,以下select的参数依次就是sql, args, size
        rs = await select("%s where `%s`=?" % (cls.__select__, cls.__primary_key__), [pk], 1)
        if len(rs) == 0:
            return None
        # 注意,我们在select函数中,打开的是DictCursor,它会以dict的形式返回结果，**是在进行解包
        # 这里返回的是一个类的实例，即一条记录, 又因为user也继承了dict，所以实际上可以直接打印，相当于打印一个字典
        return cls(**rs[0])

    @classmethod
    async def findAll(cls, where = None, args = None, **kw):
        sql = [cls.__select__]
        # 定义的默认的select语句是通过主键查询的,并不包括where子句
        # 因此若指定有where,需要在select语句中追加关键字
        if where:
            sql.append("where")
            sql.append(where)
        if args is None:
            args = []
        # 解释同where，此处order By通过关键字参数kw传入
        orderBy = kw.get("orderby", None)
        if  orderBy:
            sql.append("order by")
            sql.append(orderBy)
        # 解释同where
        limit = kw.get("limit", None)
        if limit is not None:
            sql.append("limit")  # sql中limit有两种用法
            # 如果limit作为一个整数n，那就将查询结果的前n个结果返回
            if isinstance(limit, int):
                sql.append("?")
                args.append(limit)
            # 如果limit作为一个两个值的tuple，则前一个值带面索引，后一个值代表从这个索引开始要取的结果数
            elif isinstance(limit, tuple) and len(limit) == 2:
                sql.append("?, ?")
                args.extend(limit) # 用extend是把tuple的小括号去掉，把它与append区别开
            # 如果不是上面两种情况，那就一定出问题了
            else:
                raise ValueError("Incalid limit value: %s" % str(limit))
        rs = await select(' '.join(sql), args)  # 没有指定size，因此fetchall
        return [cls(**r) for r in rs]  # 返回多条记录

    @classmethod
    async def findNumber(cls, selectField, where = None, args = None):
        sql = ["select %s _num_ from `%s`" % (selectField,cls.__table__)]
        if where:
            sql.append("where")
            sql.append(where)
        rs = await select(' '.join(sql), args, 1)
        if len(rs) == 0:
            return None
        return rs[0]["_num_"]

    async def save(self):
        # 在定义__insert__时,将主键放在了末尾.因为属性与值要一一对应,因此通过append的方式将主键加在最后
        args = list(map(self.getValueOrDefault, self.__fields__))  # 使用getValueOrDefault方法,可以调用time.time这样的函数来获取值
        args.append(self.getValueOrDefault(self.__primary_key__))
        rows = await execute(self.__insert__, args)
        if rows != 1:  # 插入一条记录,结果影响的条数不等于1,肯定出错了
            logging.warn("failed to insert recored: affected rows: %s" % rows)

    async def update(self):
        # 像time.time,next_id之类的函数在插入的时候已经调用过了,没有其他需要实时更新的值,因此调用getValue
        args = list(map(self.getValue, self.__fields__))
        args.append(self.getValue(self.__primary_key__))
        rows = await execute(self.__update__, args)
        if rows != 1:
            logging.warn("failed to update by primary key: affected rows %s" % rows)

    async def remove(self):
        args = [self.getValue(self.__primary_key__)]  # 取得主键作为参数
        rows = await execute(self.__delete__, args)  # 调用默认的delete语句
        if rows != 1:
            logging.warn("failed to remove by primary key: affected rows %s" % rows)

# if __name__ == "__main__":
#     # 定制表
#     class User(Model):
#         __table__ = 'user'
#         id = IntegerField('id', primary_key=True)
#         name = StringField('name')
#         email = StringField('email')
#         password = StringField('password')
#
#
#     # 测试
#     async def check(loop):
#         # 连接数据库
#         await create_pool(loop=loop, host='localhost', port=3306, user='root', password='123a456s789q',
#                           db='word_game')
#         # 创建实例（记录）
#         user = User(id=1, name='hk4fun', email='941222165@qq.com', password='123321')
#         # 保存（插入）--增
#         # await user.save()
#         # 删
#         # await user.remove()
#         # 改
#         # await user.update()
#         # 查找单个--查
#         # r = await User.find('2')
#         # 查找所有
#         # r = await User.findAll()
#         # 使用where查找
#         # r = await User.findAll(where="id='1'")
#         # 使用order by 和 limit
#         # r = await User.findAll(orderby="id desc",limit=3)
#         # print(r)
#         await destroy_pool()
#
#
#     # 创建异步事件的句柄
#     loop = asyncio.get_event_loop()
#     loop.run_until_complete(check(loop))
#     loop.close()