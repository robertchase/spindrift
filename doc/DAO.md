# DAO Database Access Object
## A Reference Guide

A `DAO` is a simple object for interacting with a MySQL database using `spindrift`.

#### Scope

The `DAO` has nowhere near the complexity of `sqlalchemy`, or similar projects.
It is primarily meant to facilitate the simple loading, modifying and saving of database rows,
which is a common use case for `REST` services.

#### opinion

Most `SQL` stuff is *best expressed* using `SQL`.

Complicated and abstract python object relationships
which attempt to mirror set operations in a relational
database can end up trading explicit statements in one
language for obscure constructs in another. I'm not a
fan. But don't let that stop you if you find these
frameworks useful.

## Example
Here is a table definition:
```
CREATE TABLE `root` (
    `id` INT NOT NULL AUTO_INCREMENT,
    `name` VARCHAR(100) NOT NULL,
    PRIMARY KEY(`id`)
) ENGINE=InnoDB;
```
Here is a matching `DAO`:
```
from spindrift.database.dao import DAO

class Root(DAO):

    TABLENAME = 'root'

    id = Field(int, is_primary=True)
    name = Field(str)
```

#### sync and async
The database interface is asynchronous, but allows for synchronous
use in special cases, like tests or `CLI` tools,
by accepting a `spindrift.database.sync.SYNC` mixin at class definition:
```
from spindrift.database.sync import SYNC

class Root(DAO, SYNC):
    ...
```
We'll use `sync` methods in this example, denoted by the postfix `_sync`.

#### database setup
A `cursor` is needed to perform database operations. *Your database connection
might require different parameters.* The `commit` flag prevents changes from
being commited, which is handy for testing or demonstration.
```
from spindrift.database.db import DB

cursor = DB(user='test', database='spindrift', commit=False).cursor
```

#### interacting with the database

```
# create a new row, the primary key is not yet assigned
>>> root = Root(name='test')
>>> print(root)
<Root>:{'id': None, 'name': 'test'}

# save (using sync) and notice the AUTO_INCREMENT primary key
root.save_sync(cursor=cursor)
<Root>:{'id': 10, 'name': 'test'}

# load a new copy of the row
new_root = Root.load_sync(root.id, cursor=cursor)
print(new_root)
<Root>:{'id': 10, 'name': 'test'}
