class EppObjectHelper:
    """ Used to simplify dealing with Epp objects. 
    Is not a model, just used as a helper function."""
    def __init__(
        self,
        auth_info=...,
        _contacts=...,
        cr_date=...,
        ex_date=...,
        _hosts=...,
        name=...,
        registrant=...,
        statuses=...,
        tr_date=...,
        up_date=...,
        **kwargs
    ):
        self.auth_info = auth_info
        self._contacts = _contacts
        self.cr_date = cr_date
        self.ex_date = ex_date
        self._hosts = _hosts
        self.name = name
        self.registrant = registrant
        self.statuses = statuses
        self.tr_date = tr_date
        self.up_date = up_date
        self.fields = kwargs

    # Probably don't need these, 
    # but these are here for custom behavior
    # especially during testing
    @property
    def auth_info(self):
        return self._auth_info

    @auth_info.setter
    def auth_info(self, value):
        self._auth_info = value

    @property
    def contacts(self):
        return self._contacts

    @contacts.setter
    def contacts(self, value):
        self._contacts = value

    @property
    def cr_date(self):
        return self._cr_date

    @cr_date.setter
    def cr_date(self, value):
        self._cr_date = value

    @property
    def ex_date(self):
        return self._ex_date

    @ex_date.setter
    def ex_date(self, value):
        self._ex_date = value

    @property
    def hosts(self):
        return self._hosts

    @hosts.setter
    def hosts(self, value):
        self._hosts = value

    @property
    def name(self):
        return self._name

    @name.setter
    def name(self, value):
        self._name = value

    @property
    def registrant(self):
        return self._registrant

    @registrant.setter
    def registrant(self, value):
        self._registrant = value

    @property
    def statuses(self):
        return self._statuses

    @statuses.setter
    def statuses(self, value):
        self._statuses = value

    @property
    def tr_date(self):
        return self._tr_date

    @tr_date.setter
    def tr_date(self, value):
        self._tr_date = value

    @property
    def up_date(self):
        return self._up_date

    @up_date.setter
    def up_date(self, value):
        self._up_date = value
