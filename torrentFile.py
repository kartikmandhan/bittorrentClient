import bencodepy
import hashlib
import random
import urllib.parse
import requests
import sys
from socket import *
class FileInfo:
    def __init__(self, fileName):
        self.fileName = fileName
        self.announceURL = ""
        self.infoDictionary = {} 
        self.filesInfo=[]
        self.hashOfPieces = []
        self.lengthOfFileToBeDownloaded = 0

    def _generate_infoHash(self):
        infoDictionaryBencode = bencodepy.encode(self.infoDictionary)
        infoHash = hashlib.sha1(infoDictionaryBencode).digest()
        return infoHash
    def _generate_hashOfPieces(self):
        previous = 0
        for i in range(20, len(self.pieces) + 20, 20):
            self.hashOfPieces.append(self.pieces[previous:i])
            previous = i
    def extractFileMetaData(self):
        fp = open(self.fileName, "rb")
        fileContent = bencodepy.decode(fp.read())
        self.announceURL = fileContent[b"announce"].decode()
        self.infoDictionary = fileContent[b"info"]
        self.nameOfFile = self.infoDictionary[b"name"].decode()
        self.pieces = self.infoDictionary[b"pieces"]
        self.pieceLength = self.infoDictionary[b"piece length"]
        self.infoHash =self._generate_infoHash()
        self._generate_hashOfPieces()
        if b"files" in self.infoDictionary:
            # multifile torrent
            for file in self.infoDictionary[b"files"]:
                fileDict = {}
                fileDict["length"] = file[b"length"]
                fileDict["path"] = file[b"path"]
                self.filesInfo.append(fileDict)
                self.lengthOfFileToBeDownloaded +=file[b"length"]     
        else:
            #  single file torrent
            self.lengthOfFileToBeDownloaded = self.infoDictionary[b"length"]
    def __str__(self): 
        return f"announceURL: {self.announceURL}\nfilename : {self.nameOfFile}\ninfoHash : {self.infoHash}\nfilesInfo :{self.filesInfo}\nlengthOfFileToBeDownloaded : {self.lengthOfFileToBeDownloaded}"
     
class httpTracker(FileInfo):
    def __init__(self, fileName):
        super().__init__(fileName)
        super().extractFileMetaData()

    def extractIPAdressandPort(self,ipAndPortString):
        port = int.from_bytes(ipAndPortString[-2:], "big")
        # print(port)
        ipAddress = ""
        ip = list(map(str, ipAndPortString[:4]))
        ipAddress = ".".join(ip)
        return (ipAddress, port)
    def _generate_peers(self):
        allPeers = []
        previous = 0
        for i in range(6, len(self.trackerPeers) + 6, 6):
            allPeers.append(self.trackerPeers[previous:i])
            previous = i
        return allPeers
    def httpTrackerRequest(self):
        self.peerID = "KK"+"0001" + str(random.randint(10000000000000, 99999999999999))
        self.portNo = 6885
        params = {"info_hash": self.infoHash, "peer_id": self.peerID, "port": self.portNo, "uploaded": 0,
            "downloaded": 0, "left": self.lengthOfFileToBeDownloaded, "compact": 1}
        # print(urllib.parse.urlencode(params))
        announceResponse = requests.get(self.announceURL, params).content
        trackerResponseDict = bencodepy.decode(announceResponse)
        # print(announceResponse)
        self.trackerComplete = trackerResponseDict[b"complete"]
        self.trackerIncomplete = trackerResponseDict[b"incomplete"]
        self.trackerInterval = trackerResponseDict[b"interval"]
        self.trackerPeers = trackerResponseDict[b"peers"]
        allPeers = self._generate_peers()
        self.peerAddresses = []
        for i in allPeers:
            self.peerAddresses.append(self.extractIPAdressandPort(i))
        print(self.peerAddresses)
        # print(allPeers)

class udpTrackerRequest(FileInfo):
    def udpTrackerRequest(self):
        parsedURL = urllib.parse.urlparse(self.announceURL)
        connectionSocket= socket(AF_INET, SOCK_DGRAM)
        url = parsedURL.netloc.split(":")[0]
        print(url)
        self.transactionID = 0x41727101980
        
        connectionSocket.sendto("asd",(url,parsedURL.port))

