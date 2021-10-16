import sys
from torrentFile import *
try:

    fileName = sys.argv[1]
except:
    print("usage python3 init.py <filename> ")
    exit(0)

torrentFileData = FileInfo(sys.argv[1])
torrentFileData.extractFileMetaData()
# print(torrentFileData)
# print(torrentFileData.infoDictionary[b"files"])


def makeRequest():
    if "udp://" in torrentFileData.announceURL:
        requestMaker = udpTracker(fileName)
        requestMaker.udpTrackerRequest()
    else:
        requestMaker = httpTracker(fileName)
        requestMaker.httpTrackerRequest()


makeRequest()
