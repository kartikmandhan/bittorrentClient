
from torrentFile import *
try:
    
    fileName=sys.argv[1]
except:
    print("usage python3 init.py <filename> ")
    exit(0)

torrentFileData = FileInfo(sys.argv[1])
torrentFileData.extractFileMetaData()
# print(torrentFileData.infoDictionary[b"files"])