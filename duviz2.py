import optparse
import os

from terminalsize import get_terminal_size
from du import build_du_tree
from DirectoryTree import DirectoryTree

# TODO push into terminalsize.py ?
def getTerminalSize():
    global terminal_width
    os.system("mode con lines=40 cols=130")  # TODO hack for debugging
    terminal_width, ignore  = get_terminal_size()
    terminal_width -= 1 # seems to be necessary on windows? \r vs \r\n ?

def main():
    getTerminalSize()

    argP = optparse.OptionParser('''usage: %prog [options] [DIRS]''', version='%prog 1.0')
    (argO, argA) = argP.parse_args()

    # TODO push into a utility file
    paths = ['.']  # Do current dir if no dirs are given.
    if len(argA) > 0:
        paths = []
        for path in argA:
            if os.path.exists(path):
                paths.append(path)
            else:
                sys.stderr.write('Warning: not a valid path: "%s"\n' % path)

    for directory in paths:
        lines = build_du_tree(directory)
        dir_tree = DirectoryTree(directory)
        for line in lines:
            dir_tree.AddFolder(line)
        dir_tree.Accum()

        print(len(lines))
        dir_tree.Dump(0,1)

if __name__ == '__main__':
    main()
