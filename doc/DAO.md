# DAO Database Access Object
## A Reference Guide

A `DAO` is a simple object for interacting with a MySQL database using `spindrift`.

#### Scope

The `DAO` is nowhere near the complexity of `sqlalchemy`, or similar projects.
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
Start with the following `DAO` which defines a few fields that are tied
to columns in a database table named `root`.

```
from spindrift.database.dao import DAO

class Root(DAO):

    TABLENAME = 'root'

    id = Field(int, is_primary=True)
    name = Field(str)
```
The primary key is `id`, and `name` is a character field.

#### creation
```
my_root = Root(name='test')
```

Since `spindrift` database access is async, each database interaction
must be supplied with a callback, which is a callable accepting (`rc`, `result`).
We'll assume we have a `spindrift.mysql.cursor.Cursor` is already defined.
```
# define a new root object, not yet in the database
>>> root = Root(name='akk')

# define a useless callback
>>> def on_callabck(rc, result):
        if rc != 0:
            raise Exception(result)
        print(result.__dict__)

# add our object to the database
>>> root.save(on_callback, cursor=cursor)

```
