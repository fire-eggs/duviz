#!/usr/bin/env python
# A command-line 'du' in python
#
# Scans a directory tree, outputs statistics as determined by arguments
#

import os
import platform
import optparse
import ctypes
import math

# -a allocated size
# -r recursive
# 

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
    return size

def build_du_tree(folder):
    folder = os.path.realpath(folder) # TODO is this necessary?
    for root, dirs, files in os.walk(folder):
        largeF = ('',0)
        rootFileSize = 0
        rootAllocSize = 0
        rootFileCount = len(files)

        if (rootFileCount > 0): # max falls over if tuples is empty
            filesizes = []
            allocsizes = []
            fileAccess = []
            fileCreate = []
            for name in files:
                aStat = os.stat(os.path.join(root,name))
                aSize = aStat.st_size
                # aSize = os.path.getsize(os.path.join(root,name))
                filesizes.append(aSize)
                allocsizes.append(AllocatedSize(aSize))
                fileAccess.append(aStat.st_atime)
                fileCreate.append(aStat.st_ctime)

            rootFileSize = sum(filesizes)
            rootAllocSize = sum(allocsizes)

            sizeTup = list(zip(files, filesizes))
            createTup = list(zip(files, fileCreate))
            accessTup = list(zip(files, fileAccess))
            largeF = max(sizeTup, key=lambda x:x[1])
            oldCF = min(createTup, key=lambda x:x[1])
            oldAF = min(accessTup, key=lambda x:x[1])

        # TODO drive which columns appear based on options
        print('{1}|{2}|{5}|{3}|{4}|{6}|{7}|{0}'.format(root, rootFileCount, rootFileSize, largeF[0], largeF[1], rootAllocSize, oldCF[0], oldCF[1]))
        (build_du_tree(dir) for dir in dirs)

def main():

    getClusterSize()

    argP = optparse.OptionParser('usage: %prog [options] [DIR]', version='%prog 1.0')
    (argO, argA) = argP.parse_args()
    paths = ['.']  # Do current dir if no dirs are given.
    if len(argA) > 0:
        paths = []
        for path in argA:
            if os.path.exists(path):
                paths.append(path)
            else:
                sys.stderr.write('Warning: not a valid path: "%s"\n' % path)

    for directory in paths:
        build_du_tree(directory)


if __name__ == '__main__':
    main()
