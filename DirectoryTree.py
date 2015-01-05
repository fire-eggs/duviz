import os
import time

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

class DirectoryTree(object):
    def __init__(self, path):
        self.name = path
        self.subnodes = {}

        self.totFold = 0
        self.myCount = 0
        self.totCount = 0
        self.mySize = 0
        self.myAlloc = 0
        self.totSize = 0
        self.totAlloc = 0
        self.maxFileSize = -1
        self.maxFileName = ''
        self.oldFileDate = -1
        self.oldFileName = ''
        self.maxFoldSize = -1
        self.maxFoldName = ''

    def AddFolder(self, du_line):
        # receive a line from du.py: represents one folder and its stats, separated by bars

        parts = du_line.split('|')
        if (len(parts) != 8): # incompatible version of du
            exit
        relPath = path_split(parts[7], base=self.name)[1:]

        # Walk down path and create subnodes if required.
        cursor = self
        for component in relPath:
            if component not in cursor.subnodes:
                cursor.subnodes[component] = DirectoryTree(component)
            cursor = cursor.subnodes[component]

        # Store 'our' data to 'self' stats
        cursor.myCount = int(parts[0])
        cursor.mySize  = int(parts[1])
        cursor.myAlloc = int(parts[2])

        # Init 'our' total to 'self' data; later accumulation pass
        cursor.totCount = int(parts[0])
        cursor.totSize  = int(parts[1])
        cursor.totAlloc = int(parts[2])

        cursor.totFold += 1

        # Large file TODO distinguish self / total
        cursor.maxFileSize = int(parts[4])
        cursor.maxFileName = parts[3]

        # Oldest file TODO distinguish self / total
        cursor.oldFileDate = float(parts[6])
        cursor.oldFileName = parts[5]

        return cursor

    # TODO accumulate size/count data
    # TODO accumulate large file data
    # TODO accumulate old file data
    def Accum(self):
        for node in self.subnodes.values():
            node.Accum()
            self.totCount += node.totCount
            self.totAlloc += node.totAlloc
            self.totSize  += node.totSize
            self.totFold  += node.totFold

            if (node.maxFileSize > self.maxFileSize):
                self.maxFileName = node.maxFileName
                self.maxFileSize = node.maxFileSize
            if (node.oldFileDate < self.oldFileDate):
                self.oldFileName = node.oldFileName
                self.oldFileDate = node.oldFileDate

    # TODO total folder count is off-by-one because it includes 'self'
    def Dump(self, level=0, maxlevel=99999):
        print('{1}:{2}({5})-{3}({4}) \'{0}\''.format(self.name, level, self.totCount, self.totSize, self.totAlloc, self.totFold))
        print('    Large File:\'{0}\'({1})'.format(self.maxFileName, self.maxFileSize))
        print('    Aged  File:\'{0}\'({1})'.format(self.oldFileName, time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(int(self.oldFileDate)))))

        if ( level < maxlevel ):
            for node in self.subnodes.values():
                node.Dump(level+1, maxlevel)

