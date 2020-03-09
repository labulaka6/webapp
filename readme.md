一个简单基于asyncio的Blog网站

后端：异步框架aiohttp   MySQL的Python异步驱动程序aiomysql
前端：模板引擎jinja2   uikit CSS框架
其中还用到了Vue这个简单易用的MVVM框架

来自于廖雪峰Python教程实战，参考了Hk4Fun[1]的源码，注释非常详实，对于新手十分友好。
廖大大的这个web实战很是经典，借鉴了不少的框架设计思想：`orm（modle）、router（urls）、mvc（mvt）、handlers（views）`等

## 主要模块

底层(相对)：

**`orm.py`**：建立类与数据库表的映射，对数据库进行封装。把表映射成类，把行（记录）映射为实例，把字段映射为实例的属性，而每个字段实际上是每个`Field`的实例，这也就定义了字段的类型。因为数据库中每张表的字段都不一样，所以我们需要动态的生成类，此时元类派上用场，这里推荐[StackOverflow上的一个高票回答][1]帮助理解元类。为什么要辛辛苦苦地建立orm而不直接连接数据库操作呢？我的理解有以下几点：

 1. 安全：避免SQL语句的拼接，参数化的SQL语句可以有效防止SQL注入
 2. 封装：对不懂SQL语句的程序员可直接使用orm提供的函数操作数据库，而不用专门去学习SQL语句，可应对多种数据库，无非就是`migrate`一下，无需关心底层的SQL语句是如何生成的
 3. 插件化：从django的setting可以看出，更换数据库只需更换orm引擎，而不用更改任何的代码
 4. 分层：从2、3可以看出，所以还是那句话：计算机领域没有什么问题是不能靠分层解决的

**`models.py`**：建立数据模型。与django的`models.py`功能一样，实现数据库的建模，也就是定义表的内容和结构。由于上面的orm实现的不是很完善，我们还是需要自己收到那个在数据库中建立这张表的（借助`schema.sql`实现），而在django中只需migrate（迁移）一下就可以了。这里我们定义了三张表：`User`、`Blog`、`Comment`，具体都有哪些字段及其类型看代码就清楚了

**`webframe.py`**：框架的核心模块。在web开发中想要让时间和精力更多放在业务逻辑函数的设计上，编写更少的代码从而提高开发效率，就只能在底层框架上封装一个更高级的框架。Django干的就是这件事，而本框架主要基于`aiohttp`异步web框架进行再次封装，主要是从URL函数中解析需要接收的参数，进而从request中获取必要的参数构造成字典以`**kw`传给该URL函数并调用，这也`RequestHandler`函数的主要功能，然后对url和静态资源进行了映射（借鉴了flask的router装饰器，即注册url函数，关于装饰器的理解，还是[一个StackOverflow的高票回答][2]），在app.py的初始化函数init()中被调用

中间层(业务逻辑)：

**`handlers.py`**：编写业务逻辑函数的模块。所有处理业务逻辑的函数都在这里编写，也就是说需求改动时只需改动该模块即可（当然，要修改数据模型还得到`modles.py`中）。但该模块还是有不足之处：参考django的设计，应该把该模块按照功能进行分割，一个功能一个app，便于维护和复用，因为到后面需求越来越复杂，全部堆在一个模块肯定乱手脚（我在代码中用注释分隔开了。。。）

**`app.py`**：整个web app的起点和终点。实现的各个中间件（`middlewares`,也加拦截器）在请求到来时进行拦截，主要是打印相关日志信息和身份验证，而在应答数据返回时进行拦截，主要是进行模板的渲染和其他数据流类型的相关处理，将`request handler`的返回值根据返回的类型转换为`web.Response`对象，吻合aiohttp框架的需求。

从上面介绍的各个功能模块来看，该web框架借鉴了django和flask等知名web开发框架的设计思想，MVC的实现无处不在，对理解web开发框架的实现有参考价值

其他模块非主要模块，主要是进行设置的读取和markdown语法的转换以及各种异常请求的处理，这里不再详细介绍。想了解以上各个模块更多的实现细节请直接阅读代码，几乎对每一行都有注释以及相关知识的介绍，非常适合小白（or 大白）学习


## 数据流向
当收到一个http请求时，首先会被`logger_factory`（输出请求的信息）、`data_factory`（打印post提交的数据）、`auth_factory`（cookie解析）这三个中间件拦截。然后才根据请求的url被映射到到`handlers.py`中的各个相应的url函数进行处理。而在执行这些url函数之前，会被`RequestHandle`先处理（hook），主要是从url函数中解析需要接收的参数，进而从request中获取必要的参数构造成字典以`**kw`传给该url函数并调用。最后在应答返回数据前会被response_factory所拦截，进行模板的渲染，将`request handler`的返回值根据返回的类型转换为`web.Response`对象，吻合aiohttp框架的需求


注：
[1]: https://github.com/Hk4Fun
[2]: https://stackoverflow.com/questions/100003/what-is-a-metaclass-in-python
[3]: https://stackoverflow.com/questions/739654/how-to-make-a-chain-of-function-decorators/1594484#1594484
