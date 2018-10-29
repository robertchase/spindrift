# DAO Database Access Object
## A Tutorial

A `DAO` is a simple object for interacting with a MySQL database using `spindrift`.

#### Scope

The `spindrift` database interface has nowhere near the complexity of a project like `sqlalchemy`.
It is primarily meant to facilitate the loading, modifying and saving of database rows,
which is a common use case for `REST` services.

#### Opinion

Most `SQL` stuff is *best expressed* using `SQL`.

Complicated and abstract python object relationships
which attempt to mirror set operations in a relational
database can end up trading explicit statements in one
language for obscure constructs in another. I'm not a
fan. But don't let that stop you if you find these
frameworks useful.

## Schema
Here is a table definition:
```
CREATE TABLE `root` (
    `id` INT NOT NULL AUTO_INCREMENT,
    `name` VARCHAR(100) NOT NULL,
    `color` ENUM('red', 'blue', 'yellow') NULL,
    PRIMARY KEY(`id`)
) ENGINE=InnoDB;
```
Here is a matching `DAO`:
```
from spindrift.database.dao import DAO
from spindrift.database.field import Field

class Root(DAO):

    TABLENAME = 'root'

    id = Field(int, is_primary=True)
    name = Field(str)
    color = Field(('red', 'blue', 'yellow'), is_nullable=True)
```

## Setup
A `cursor` is needed to perform database operations:
```
from spindrift.database.db import DB

db = DB(host='mysql', user='test', db='test', commit=False, sync=True)
cursor = db.cursor
```
*Your database connection
might require different parameters.* The `commit` flag setting prevents changes from
being commited, which is handy for testing or demonstration.
The `sync` flag setting enables synchronous interaction with the database, which
is handy for testing or CLI tools.

**When operating a server, use the default settings for the `commit` and `sync` flags.**

## Saving to and loading from the database

```
>>> # create a new Root
>>> # the database is not changed
>>> root = Root(name='test')
>>> root
<Root>:{'color': None, 'id': None, 'name': 'test'}

>>> # save the Root instance
>>> # 'root' is inserted as a new row
>>> # the primary key is captured in the object
>>> root.save(cursor)
<Root>:{'color': None', id': 1, 'name': 'test'}
```
Peek under the hood:
```
>>> # look at the most recently executed statement
>>> cursor.statement
"INSERT INTO `root`  ( `name` ) VALUES ( 'test' )"
```

Load the most recently saved row:
```
>>> # load a new copy of the row
>>> Root.load(cursor, root.id)
<Root>:{'color': None, 'id': 1, 'name': 'test'}

>>> # there is no object caching
>>> # the load function queries the database and creates a new instance
>>> Root.load(cursor, root.id) == root
False
```

## Working with DAO attributes
The DAO allows `dot notation` access to a row's columns:
```
>>> root
<Root>:{'color': None, 'id': 1, 'name': 'test'}

>>> root.id
1
>>> root.name
'test'
>>> root.color is None
True
```

The DAO also controls access:

```
>>> root.akk
Traceback (most recent call last):
  File "<stdin>", line 1, in <module>
  File "/opt/git/spindrift/spindrift/database/dao.py", line 44, in __getattr__
    self.__class__.__name__, name
AttributeError: 'akk' is not an attribute of 'Root'

>>> # the name attribute has is_nullable=False (the default)
>>> root.name = None
Traceback (most recent call last):
  File "<stdin>", line 1, in <module>
  File "/opt/git/spindrift/spindrift/database/dao.py", line 53, in __setattr__
    raise TypeError("'{}' cannot be None".format(name))
TypeError: 'name' cannot be None

>>> # the name attribute is a 'str'
>>> root.name = 27
>>> root
<Root>:{'color': None, 'id': 1, 'name': '27'}
```

## List, count and delete
A DAO has a few helper methods:
```
>>> # count (returns an integer)
>>> Root.count(cursor)
1
>>> # list (returns a list of DAOs)
>>> Root.list(cursor)
[<Root>:{'color': None, 'id': 1, 'name': 'test'}]

>>> # save another row
>>> Root(name='foo').save()
<Root>:{'color': None, 'id': 2, 'name': 'foo'}]

>>> # count again
>>> Root.count(cursor)
2

>>> # list again
>>> Root.list(cursor)
[<Root>:{'color': None, 'id': 1, 'name': 'test'},<Root>:{'color': None, 'id': 2, 'name': 'foo'}]

>>> # count a subset
>>> Root.count(cursor, where='name=%s', args='foo')
1
>>> # what happened?
>>> cursor.statement
"SELECT COUNT(*) FROM `root` WHERE name='foo'"

>>> # list a subset
>>> Root.list(cursor, where='name=%s', args='foo')
[<Root>:{'color': None, 'id': 2, 'name': 'foo'}]
>>> # and what happened there?
>>> cursor.statement
"SELECT `root`.`color`,`root`.`id`,`root`.`name` FROM `root` WHERE name='foo'"

>>> # delete
>>> root.delete(cursor)
>>> Root.list(cursor)
[<Root>:{'color': None, 'id': 2, 'name': 'foo'}]
```

## Performing a join with DAOs

#### Schema
Here is another table definition:
```
CREATE TABLE `node` (
    `id` INT NOT NULL AUTO_INCREMENT,
    `root_id` INT NOT NULL,
    `name` VARCHAR(100) NOT NULL,
    PRIMARY KEY(`id`),
    FOREIGN KEY(`root_id`) REFERENCES `root`(`id`)
) ENGINE=InnoDB;
```
Here is a matching `DAO`:
```
class Node(DAO):

    TABLENAME = 'node'

    id = Field(int, is_primary=True)
    root_id = Field(int, foreign=Root)
    name = Field(str)
```
