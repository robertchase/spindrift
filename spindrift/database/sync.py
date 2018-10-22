''' The MIT License (MIT)

https://github.com/robertchase/spindrift/blob/master/LICENSE.txt
'''


def _sync(fn, *args, **kwargs):
    cursor = kwargs.get('cursor')
    return cursor._run_sync(fn, *args, **kwargs)


class SYNC:
    """Synchronous DAO methods.

       Mix this in with a DAO to add synchronous database methods. Note that
       the network will still be serviced while waiting for the database,
       but timers will not.

       Avoid this unless you know what you are doing.
    """

    @classmethod
    def load_sync(cls, *args, **kwargs):
        return _sync(cls.load, *args, **kwargs)

    def save_sync(self, *args, **kwargs):
        return _sync(self.save, *args, **kwargs)

    def insert_sync(self, *args, **kwargs):
        return _sync(self.insert, *args, **kwargs)

    def delete_sync(self, *args, **kwargs):
        return _sync(self.delete, *args, **kwargs)

    @classmethod
    def list_sync(cls, *args, **kwargs):
        return _sync(cls.list, *args, **kwargs)

    @classmethod
    def count_sync(cls, *args, **kwargs):
        return _sync(cls.count, *args, **kwargs)
