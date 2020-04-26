import sys


from inquirer.render.console import ConsoleRender
from inquirer import themes, errors
from inquirer.themes import Theme


class NonTerminal(object):
    def __getattr__(self, item):
        return ''


class NonInteractiveRender(ConsoleRender):
    def __init__(self, event_generator=None, theme=None, *args, **kwargs):
        super(NonInteractiveRender, self).__init__(*args, **kwargs)
        self._event_gen = None
        self.terminal = NonTerminal()
        self._previous_error = None
        self._position = 0
        self._theme = theme or themes.Default()

    def render(self, question, answers=None):
        question.answers = answers or {}

        if question.ignore:
            return question.default

        clazz = self.render_factory(question.kind)
        render = clazz(question,
                       terminal=self.terminal,
                       theme=self._theme,
                       show_default=question.show_default)

        self.clear_eos()

        try:
            return self._event_loop(render)
        finally:
            print('')


    def print_str(self, base, lf=False, **kwargs):
        if lf:
            self._position += 1

        print(base.format(t=self.terminal, **kwargs), end='\n' if lf else '')
        sys.stdout.flush()

    def _relocate(self):
        print(self._position * ' ', end='\r')
        self._force_initial_column()
        self._position = 0


    def _go_to_end(self, render):
        print(self._position * ' ', end='')

    def clear_eos(self):
        print(' '*80, end='\r')

    def render_error(self, message):
        if message:
            symbol = '>> '
            size = len(symbol) + 1
            length = len(message)
            message = message.rstrip()
            message = (message
                       if length + size < self.width
                       else message[:self.width - (size + 3)] + '...')

            self.render_in_bottombar(
                '{t.red}{s}{t.normal}{t.bold}{msg}{t.normal} '
                    .format(msg=message, s=symbol, t=self.terminal)
            )

    def render_in_bottombar(self, message):
        self.clear_eos()
        self.print_str(message)

    def clear_bottombar(self):
        self.clear_eos()


    def _print_status_bar(self, render):
        if self._previous_error is None:
            self.clear_bottombar()
            return

        self.render_error(self._previous_error)
        self._previous_error = None

    def _process_input(self, render):
        raise errors.EndOfInput(input())

    @property
    def width(self):
        return 80

    @property
    def height(self):
        return 24

class Bland(Theme):
    def __init__(self):
        super(Bland, self).__init__()
        self.Question.mark_color = ''
        self.Question.brackets_color = ''
        self.Question.default_color = ''
        self.Editor.opening_prompt_color = ''
        self.Checkbox.selection_color = ''
        self.Checkbox.selection_icon = '>'
        self.Checkbox.selected_icon = 'X'
        self.Checkbox.selected_color = '' + ''
        self.Checkbox.unselected_color = ''
        self.Checkbox.unselected_icon = 'o'
        self.List.selection_color = ''
        self.List.selection_cursor = '>'
        self.List.unselected_color = ''
