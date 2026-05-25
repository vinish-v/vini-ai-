from helpers.extension import Extension


class InitialMessage(Extension):

    def execute(self, **kwargs):
        """
        Vini AI uses the native chat start screen for the initial greeting.
        Keep new contexts free of synthetic assistant messages until the user sends input.
        """
        return
