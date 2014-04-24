from string import capwords

from webob.multidict import MultiDict


class AllowableMgr(object):
    __allowed_attrs = {}

    @classmethod
    def _attr_type_to_str(cls, attr_type):
        return attr_type.__name__

    @classmethod
    def attr_type_to_str(cls, attr_type):
        if type(attr_type) is list:
            return map(cls._attr_type_to_str, attr_type)
        return cls._attr_type_to_str(attr_type)

    @classmethod
    def _allowed_attrs_dict(cls):
        """Return the allowed attrs dict for this current class."""
        try:
            return cls.__allowed_attrs[cls]
        except KeyError:
            cls.__allowed_attrs[cls] = MultiDict()
        return cls.__allowed_attrs[cls]

    @classmethod
    def _allowed_attrs(cls):
        """Return the allowed attrs for this class based on polymorphism."""
        allowed_attrs = cls._allowed_attrs_dict()
        for c in cls.__bases__:
            if issubclass(c, AllowableMgr):
                allowed_attrs.update(c._allowed_attrs())
        return allowed_attrs

    @classmethod
    def _update_allowed_attrs_caches(cls):
        """Update the attr caches.

        These include allowed_attrs, allowed_attrs_list, and
        allowed_attrs_human_names. These are convenience attributes that should
        be replaced with function calls.

        TODO replace allowed_attrs, allowed_attrs_list, and
        allowed_attrs_human_names with functions.

        """
        attrs = cls._allowed_attrs()

        d = MultiDict()
        for key, attr in attrs.items():
            str_type = cls.attr_type_to_str(attr['type'])
            if type(str_type) is list and len(str_type) > 0:
                str_type = str_type[0]
            try:
                d[str_type].append(key)
            except KeyError:
                d[str_type] = [key]
        cls.allowed_attrs = d
        cls.allowed_attrs_list = attrs.keys()

        d = {}
        for key, attr in attrs.items():
            d[key] = attr['name']
        cls.allowed_attrs_human_names = d
        
    @classmethod
    def allow_attr(cls, key, attr_type, name=None, batch=False):
        """Add an _Attr definition to the list of allowed keys.

        Arguments:
        key -- (str)
        type -- (sqlalchemy type) the type of data that can be stored for key
        name -- (str) name of this key for humans (default: capitalized words
            with underscores converted to spaces)

        """
        attrs = cls._allowed_attrs_dict()

        if not name:
            name = capwords(key.replace('_', ' '))
        d = {'type': attr_type, 'name': name}
        try:
            if d != attrs[key]:
                raise TypeError(u'{0} already allowed for {1} as {2}. '
                    'Clobbering with {3} will cause unexpected behavior.'.format(
                    key, cls, attrs[key], d))
        except KeyError:
            pass
        attrs[key] = d
        if not batch:
            cls._update_allowed_attrs_caches()

    @classmethod
    def allow_attrs(cls, list):
        """Add _Attr definitions to the list of allowed keys."""
        for definition in list:
            cls.allow_attr(*definition, batch=True)
        cls._update_allowed_attrs_caches()

    @classmethod
    def attr_type(cls, key):
        """Return the type of data allowed for key."""
        attrs = cls._allowed_attrs()
        try:
            return attrs[key]['type']
        except KeyError:
            raise ValueError(u'key {0} is not allowed for {1}'.format(key, cls))
