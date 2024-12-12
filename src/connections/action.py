

class Action:
    def __init__(self, name, func, args, description, tips):
        self.name = name
        self.func = func
        self.args = args
        self.description = description
        self.tips = tips

    def run(self, **kwargs):
        # TODO: Validate kwargs
        self.func(**kwargs)