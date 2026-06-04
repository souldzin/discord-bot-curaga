class MatchInstanceOf:
    def __init__(self, typ):
        self.typ = typ

    def __eq__(self, other):
        return isinstance(other, self.typ)


class MatchContains:
    def __init__(self, thing):
        self.thing = thing

    def __eq__(self, other):
        return self.thing in other
