#!/usr/bin/env python
##############################################################################
# Copyright 2009-2013 Stefaan Lippens
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
##############################################################################

'''
Command line tool for visualization of the disk space usage of a directory
and its subdirectories.

Copyright: 2009-2013 Stefaan Lippens
Website: http://soxofaan.github.io/duviz/
'''

import os
import sys
import re
import subprocess
import ctypes
import operator
import math
import platform # todo replace with os calls?

from terminalsize import get_terminal_size

##############################################################################
def bar(width, label, fill='-', left='[', right=']', one='|'):
    '''
    Helper function to render bar strings of certain width with a label.

    @param width the desired total width
    @param label the label to be rendered (will be clipped if too long).
    @param fill the fill character to fill empty space
    @param left the symbol to use at the left of the bar
    @param right the symbol to use at the right of the bar
    @param one the character to use when the bar should be only one character wide

    @return rendered string
    '''
    if width >= 2:
        label_width = width - len(left) - len(right)
        return left + label[:label_width].center(label_width, fill) + right
    elif width == 1:
        return one
    else:
        return ''


##############################################################################
def _human_readable_size(size, base, formats):
    '''Helper function to render counts and sizes in a easily readable format.'''
    for f in formats[:-1]:
        if round(size, 2) < base:
            return f % size
        size = float(size) / base
    return formats[-1] % size


def human_readable_byte_size(size, binary=True):
    '''Return byte size as 11B, 12.34KB or 345.24MB (or binary: 12.34KiB, 345.24MiB).'''
    if binary:
        return _human_readable_size(size, 1024, ['%dB', '%.2fKiB', '%.2fMiB', '%.2fGiB', '%.2fTiB'])
    else:
        return _human_readable_size(size, 1000, ['%dB', '%.2fKB', '%.2fMB', '%.2fGB', '%.2fTB'])


def human_readable_count(count):
    '''Return inode count as 11, 12.34k or 345.24M.'''
    return _human_readable_size(count, 1000, ['%d', '%.2fk', '%.2fM', '%.2fG', '%.2fT'])


##############################################################################
def path_split(path, base=''):
    '''
    Split a file system path in a list of path components (as a recursive os.path.split()),
    optionally only up to a given base path.
    '''
    if base.endswith(os.path.sep):
        base = base.rstrip(os.path.sep)
    items = []
    while True:
        if path == base:
            items.insert(0, path)
            break
        path, tail = os.path.split(path)
        if tail != '':
            items.insert(0, tail)
        if path == '':
            break
        if path == '/':
            items.insert(0, path)
            break
    return items


##############################################################################
class DirectoryTreeNode(object):
    '''
    Node in a directory tree, holds the name of the node, its size (including
    subdirectories) and the subdirectories.
    '''

    def __init__(self, path):
        # Name of the node. For root node: path up to root node as given, for subnodes: just the folder name
        self.name = path

        # Total size of node.
        # By default this is assumed to be total node size, inclusive sub nodes,
        # otherwise recalculate_own_sizes_to_total_sizes() should be called.
        self.size = None   # inclusive
        self.mySize = None # non-inclusive
        self.fileCount = 0
        self.myAllocSize = None # non-inclusive
        self.allocSize = None   # inclusive

        # TODO file information should go in a separate class?

        # Dictionary of subnodes
        self._subnodes = {}

    def import_path(self, path, size):
        '''
        Import directory tree data
        @param path Path object: list of path directory components.
        @param size total size of the path in bytes.
        '''
        # Get relative path
        path = path_split(path, base=self.name)[1:]
        # Walk down path and create subnodes if required.
        cursor = self
        for component in path:
            if component not in cursor._subnodes:
                cursor._subnodes[component] = DirectoryTreeNode(component)
            cursor = cursor._subnodes[component]

        # Set size at cursor
        assert cursor.size == None
        cursor.size = size
        cursor.mySize = size
        cursor.allocSize = AllocatedSize(size)
        cursor.myAllocSize = AllocatedSize(size)

        return cursor

    def AddFile(self, filename, filesize):
        '''
        Add a file to this node.
        @param filename: the name of the file to add
        @param size: size of the file in bytes.
        '''
        self.size += filesize   # accumulated file sizes
        self.mySize += filesize # my file sizes
        self.fileCount += 1
        self.allocSize += AllocatedSize(filesize)
        self.myAllocSize += AllocatedSize(filesize)
        # TODO track largest file in folder

    def AddDir(self, sub_tree):
        self.size += sub_tree.size      # add sub-node size to self
        self.allocSize += sub_tree.allocSize
        # TODO accumulated file counts
        # TODO accumulated largest file

    def recalculate_own_sizes_to_total_sizes(self):
        '''
        If provided sizes were own sizes instead of total node sizes.

        @return (recalculated) total size of node
        '''
        self.size = self.size + sum([n.recalculate_own_sizes_to_total_sizes() for n in self._subnodes.values()])
        return self.size

    def __cmp__(self, other):
        return - cmp(self.size, other.size)

    def __repr__(self):
        return '[%s(%d):%s]' % (self.name, self.size, repr(self._subnodes))

    def block_display(self, width, max_depth=5, top=True, size_renderer=human_readable_byte_size):
        if width < 1 or max_depth < 0:
            return ''

        lines = []

        if top:
            lines.append('_' * width)

        # Display of current dir.
        lines.append(bar(width, self.name, fill=' '))
        lines.append(bar(width, size_renderer(self.allocSize), fill=' '))
        lines.append(bar(width, size_renderer(self.size), fill='_'))

        # Display of subdirectories.
        subdirs = sorted(self._subnodes.values(), key=operator.attrgetter('name'))  # TODO by name or size (largest first?)
        if len(subdirs) > 0:
            # Generate block display.
            subdir_blocks = []
            cumsize = 0
            currpos = 0
            lastpos = 0
            for sd in subdirs:
                cumsize += sd.size
                currpos = int(float(width * cumsize) / self.size)
                subdir_blocks.append(sd.block_display(currpos - lastpos, max_depth - 1, top=False, size_renderer=size_renderer).split('\n'))
                lastpos = currpos
            # Assemble blocks.
            height = max([len(lns) for lns in subdir_blocks])
            for i in range(height):
                line = ''
                for sdb in subdir_blocks:
                    if i < len(sdb):
                        line += sdb[i]
                    elif len(sdb) > 0:
                        line += ' ' * len(sdb[0])
                lines.append(line.ljust(width))

        return '\n'.join(lines)

    def size_render(self, size_renderer=human_readable_byte_size):
        return "{} ({}):".format(size_renderer(self.size), size_renderer(self.allocSize))

    def tree_display(self, size_renderer=human_readable_byte_size):
        subdirs = sorted(self._subnodes.values(), key=operator.attrgetter('allocSize'), reverse=True)

        size_wide = len(self.size_render())
        for sd in subdirs:
            size_wide = max(len(sd.size_render()), size_wide)

        lines = []

        lines.append("+{0:>{wide}} {1}".format(self.size_render(), self.name, wide=size_wide))
        for sd in subdirs:
            lines.append('|')
            lines.append("`-{0:>{wide}} {1}".format(sd.size_render(), sd.name, wide=size_wide))

        return '\n'.join(lines)

class SubprocessException(Exception):
    pass


dirCount = 0 # dirty hack: display progress messages only periodically

##############################################################################
def build_du_tree(directory):
    '''
    Build a tree of DirectoryTreeNodes, starting at the given directory.
    '''
    directory = os.path.realpath(directory)
    dir_tree = DirectoryTreeNode(directory)
    _build_du_tree(directory, dir_tree)
    sys.stdout.write(' ' * terminal_width + '\r') # TODO feedback

    return dir_tree

def _build_du_tree(directory, dir_tree):
    global dirCount

    if (dirCount % 100 == 0):
        sys.stdout.write(('scanning %s' % directory).ljust(terminal_width)[:terminal_width] + '\r') # TODO feedback

    dirCount += 1

    me = dir_tree.import_path(directory,0)

    for athing in os.listdir(directory):
        fullpath = os.path.join(directory, athing)
        if (not os.path.isfile(fullpath)):
            sub_tree = _build_du_tree(fullpath, dir_tree)  # Depth-First-Search to get this full sub-node
            me.AddDir(sub_tree)
        else:
            me.AddFile(athing, os.path.getsize(fullpath))

    return me

def build_inode_count_tree(directory, feedback=sys.stdout, terminal_width=80):
    '''
    Build tree of DirectoryTreeNodes withinode counts.
    '''

    try:
        process = subprocess.Popen(['ls', '-aiR'] + [directory], stdout=subprocess.PIPE)
    except OSError:
        raise SubprocessException('Failed to launch "ls" subprocess.')

    tree = _build_inode_count_tree(directory, process.stdout, feedback=feedback, terminal_width=terminal_width)

    process.stdout.close()

    return tree

def _build_inode_count_tree(directory, ls_pipe, feedback=None, terminal_width=80):
    tree = DirectoryTreeNode(directory)
    # Path of current directory.
    path = directory
    count = 0
    all_inodes = set()

    # Process data per directory block (separated by two newlines)
    blocks = ls_pipe.read().rstrip('\n').split('\n\n')
    for i, dir_ls in enumerate(blocks):
        items = dir_ls.split('\n')

        # Get current path in directory tree
        if i == 0 and not items[0].endswith(':'):
            # BSD compatibility: in first block the root directory can be omitted
            path = directory
        else:
            path = items.pop(0).rstrip(':')

        if feedback:
            feedback.write(('scanning %s' % path).ljust(terminal_width)[:terminal_width] + '\r')

        # Collect inodes for current directory
        count = 0
        for item in items:
            inode, name = item.lstrip().split(' ', 1)
            # Skip parent entry
            if name == '..':
                continue
            # Get and process inode
            inode = int(inode)
            if inode not in all_inodes:
                count += 1
            all_inodes.add(inode)

        # Store count.
        tree.import_path(path, count)

    # Clear feedback output.
    if feedback:
        feedback.write(' ' * terminal_width + '\r')

    tree.recalculate_own_sizes_to_total_sizes()

    return tree

# For Windows: determine the cluster size for allocated file size
def getClusterSize():
    global gClusterSize 
    gClusterSize = None

    if (platform.system() == 'Windows'):
        sectorsPerCluster = ctypes.c_ulonglong(0)
        bytesPerSector = ctypes.c_ulonglong(0)
        rootPathName = ctypes.c_wchar_p(u"c:\\") # TODO change to drive being scanned!
        ctypes.windll.kernel32.GetDiskFreeSpaceW(rootPathName,ctypes.pointer(sectorsPerCluster),ctypes.pointer(bytesPerSector),None,None)
        gClusterSize = (int)(sectorsPerCluster.value) * (int)(bytesPerSector.value)

def AllocatedSize(size):
    if (gClusterSize != None):
        return math.ceil(size/gClusterSize) * gClusterSize
    else:
        return 0

# Hack: specify the output terminal width.
# TODO: use the Unix/Windows appropriate mechanisms
def getTerminalSize():
    global terminal_width
    os.system("mode con lines=25 cols=130")  # TODO hack for debugging
    terminal_width, ignore  = get_terminal_size()
    terminal_width -= 1 # seems to be necessary on windows? \r vs \r\n ?

##############################################################################
def main():

    getClusterSize()
    getTerminalSize()

    # TODO block/tree display option

    #########################################
    # Handle commandline interface.
    import optparse
    cliparser = optparse.OptionParser(
        '''usage: %prog [options] [DIRS]
        %prog gives a graphic representation of the disk space
        usage of the folder trees under DIRS.''',
        version='%prog 1.0')
    cliparser.add_option('-w', '--width',
        action='store', type='int', dest='display_width', default=terminal_width,
        help='total width of all bars', metavar='WIDTH')
    cliparser.add_option('-x', '--one-file-system',
        action='store_true', dest='onefilesystem', default=False,
        help='skip directories on different filesystems')
    cliparser.add_option('-L', '--dereference',
        action='store_true', dest='dereference', default=False,
        help='dereference all symbolic links')
    cliparser.add_option('--max-depth',
        action='store', type='int', dest='max_depth', default=5,
        help='maximum recursion depth', metavar='N')
    if (platform.system() != 'Windows'):
        cliparser.add_option('-i', '--inodes',
            action='store_true', dest='inode_count', default=False,
            help='count inodes instead of file size')
    cliparser.add_option('--no-progress',
        action='store_false', dest='show_progress', default=True,
        help='disable progress reporting')

    (clioptions, cliargs) = cliparser.parse_args()

    ########################################
    # Make sure we have a valid list of paths

    paths = ['.']  # Do current dir if no dirs are given.
    if len(cliargs) > 0:
        paths = []
        for path in cliargs:
            if os.path.exists(path):
                paths.append(path)
            else:
                sys.stderr.write('Warning: not a valid path: "%s"\n' % path)

    if clioptions.show_progress:
        feedback = sys.stdout
    else:
        feedback = None

    for directory in paths:
        tree = build_du_tree(directory)
        print (tree.tree_display())
        #print (tree.block_display(clioptions.display_width, max_depth=clioptions.max_depth))

if __name__ == '__main__':
    main()

# TODO display largest file (in tree)
# TODO display largest file (local)

# TODO display size in "this" folder (?)

# TODO file age statistics
# TODO file outlier statistics
# TODO allocated vs actual (how to get disk allocation size on windows?)
