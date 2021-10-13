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

    def _generate_infoHash(self):
        infoDictionaryBencode = bencodepy.encode(self.infoDictionary)
        infoHash = hashlib.sha1(infoDictionaryBencode).digest()
        return infoHash
    def _generate_hashOfPieces(self):
        previous = 0
        self.hashOfPieces = []
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
            self.filesInfo = []
            for file in self.infoDictionary[b"files"]:
                fileDict = {}
                fileDict["length"] = file[b"length"]
                fileDict["path"] = file[b"path"].decode()
                self.filesInfo.append(fileDict)
                self.lengthOfFileToBeDownloaded +=file[b"length"]     
        else:
            #  single file torrent
            self.lengthOfFileToBeDownloaded = self.infoDictionary[b"length"]
    
    
    
class httpTrackerRequest(FileInfo):
    def extractIPAdressandPort(ipAndPortString):
        port = int.from_bytes(ipAndPortString[-2:], "big")
        # print(port)
        ipAddress = ""
        ip = list(map(str, ipAndPortString[:4]))
        ipAddress = ".".join(ip)
        return (ipAddress, port)

    def httpTrackerRequest(self):
        self.peerID = "KK"+"0001" + str(random.randint(10000000000000, 99999999999999))
        self.portNo = 6885
        params = {"info_hash": self.infoHash, "peer_id": self.peerID, "port": self.portNo, "uploaded": 0,
            "downloaded": 0, "left": self.lengthOfFileToBeDownloaded, "compact": 1}
        # print(urllib.parse.urlencode(params))
        announceResponse = requests.get(self.announceURL, params).fileContent
        trackerResponseDict = bencodepy.decode(announceResponse)
        # print(announceResponse)
        self.trackerComplete = trackerResponseDict[b"complete"]
        self.trackerIncomplete = trackerResponseDict[b"incomplete"]
        self.trackerInterval = trackerResponseDict[b"interval"]
        trackerPeers = trackerResponseDict[b"peers"]
        allPeers = []
        previous = 0
        for i in range(6, len(trackerPeers) + 6, 6):
            allPeers.append(trackerPeers[previous:i])
            previous = i
        peerAddresses = []
        for i in allPeers:
            peerAddresses.append(self.extractIPAdressandPort(i))
        # print(peerAddresses)
        # print(allPeers)
class udpTrackerRequest(FileInfo):
    def udpTrackerRequest(self):
        parsedURL = urllib.parse.urlparse(self.announceURL)
        connectionSocket= socket(AF_INET, SOCK_DGRAM)
        url = parsedURL.netloc.split(":")[0]
        print(url)
        self.transactionID = 0x41727101980
        
        connectionSocket.sendto("asd",(url,parsedURL.port))

