from typing import Optional

import sys
import os
import platform

import colorama


# getch copied from https://code.activestate.com/recipes/134892/

class _Getch:
    """Gets a single character from standard input.  Does not echo to the screen."""
    def __init__(self):
        try:
            self.impl = _GetchWindows()
        except ImportError:
            self.impl = _GetchUnix()

    def __call__(self): return self.impl()


class _GetchUnix:
    def __init__(self):
        import tty, sys

    def __call__(self):
        import sys, tty, termios
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setraw(sys.stdin.fileno())
            ch = sys.stdin.read(1)
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        return ch


class _GetchWindows:
    def __init__(self):
        import msvcrt

    def __call__(self):
        import msvcrt
        return msvcrt.getch()

getch = _Getch()


class BaseScreen:
    def print_text(self, x: int, y: int, text: str, attr: Optional[str] = None) -> None:
        if attr is None:
            print(colorama.Cursor.POS(x + 1, y + 1) + text, flush=True)
        else:
            print(colorama.Cursor.POS(x + 1, y + 1) + attr + text + colorama.Style.RESET_ALL, flush=True)

    def clear(self) -> None:
        print(colorama.ansi.clear_screen(), flush=True)

    def __enter__(self):
        raise NotImplementedError("__enter__ method should be implemented in the derived class")

    def __exit__(self, exc_type, exc_val, exc_tb):
        raise NotImplementedError("__exit__ method should be implemented in the derived class")

    def getch(self) -> int:
        return getch()


if platform.system() == "Windows":
    import msvcrt


    class WindowsScreen(BaseScreen):
        def __init__(self):
            self._stdin_handle = msvcrt.get_osfhandle(sys.stdin.fileno())
            self._mode = msvcrt.setmode(sys.stdin.fileno(), os.O_BINARY)
            colorama.init()

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            msvcrt.setmode(self._stdin_handle, self._mode)
            colorama.deinit()

else:
    import curses


    class LinuxScreen(BaseScreen):
        def __init__(self):
            self._screen = curses.initscr()
            curses.noecho()
            curses.cbreak()
            self._screen.keypad(True)

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            self._screen.keypad(False)
            curses.nocbreak()
            curses.echo()
            curses.endwin()


def screen() -> BaseScreen:
    if platform.system() == "Windows":
        return WindowsScreen()
    else:
        return LinuxScreen()


# if __name__ == '__main__':
#     import time
#     with screen() as scr:
#         for x in range(20):
#             y = abs(x % 8 - 4)
#             scr.clear()
#             scr.print_text(x, y, '@', attr=colorama.Fore.BLUE)
#             time.sleep(0.3)


if __name__ == '__main__':
    import time
    with screen() as scr:
        while True:
            ch = scr.getch()
            print("ch = %s" % repr(ch))
