from enum import Enum, EnumMeta


class StrEnumMeta(EnumMeta):
    """A metaclass for creating a hybrid between a namedtuple and an Enum."""

    def keys(cls):
        return list(cls.__members__.keys())

    def items(cls):
        return {m: v.value for m, v in cls.__members__.items()}

    def values(cls):
        return list(cls)

    def __contains__(cls, member):
        """Allow strings to match against member values."""
        if isinstance(member, str):
            return any(x == member for x in cls)
        return super().__contains__(member)

    def __getitem__(cls, member):
        """Allow member values to be accessed by index."""
        if isinstance(member, int):
            return list(cls)[member]
        return super().__getitem__(member).value

    def __iter__(cls):
        for item in super().__iter__():
            yield item.value


class StrEnum(str, Enum, metaclass=StrEnumMeta):
    """
    Hybrid namedtuple and Enum.

    Creates an iterable which can use dotted access notation,
    but which is declared in class form like an Enum.
    """

    def __str__(self):
        """Use value when cast to str."""
        return str(self.value)
