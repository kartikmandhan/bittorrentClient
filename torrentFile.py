import bencodepy
import hashlib
import random
import urllib.parse
import requests
import struct
from socket import *
from loggerConfig import logger
'''
    FileInfo
        ||
        ||  
        \/                
    httpTracker
    FileInfo
        ||
        ||  
        \/                
    udpTracker

'''


class FileInfo:
    def __init__(self, fileName):
        self.fileName = fileName
        self.announceURL = ""
        self.infoDictionary = {}
        self.filesInfo = []
        self.hashOfPieces = []
        self.lengthOfFileToBeDownloaded = 0
        self.peerID = "KK"+"0001" + \
            str(random.randint(10000000000000, 99999999999999))
        self.downloaded = 0
        self.uploaded = 0
        self.portNo = 6885
        self.announceList = []
        self.peerAddresses = []
        self.numberOfPieces = 0
        # self.encoding = ""

    def extractIPAdressandPort(self, ipAndPortString):
        port = int.from_bytes(ipAndPortString[-2:], "big")
        # logger.info(port)
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

    def _generate_infoHash(self):
        infoDictionaryBencode = bencodepy.encode(self.infoDictionary)
        infoHash = hashlib.sha1(infoDictionaryBencode).digest()
        return infoHash

    def _generate_hashOfPieces(self):
        previous = 0
        for i in range(20, len(self.pieces) + 20, 20):
            self.hashOfPieces.append(self.pieces[previous:i])
            self.numberOfPieces += 1
            previous = i

    def extractFileMetaData(self):
        fp = open(self.fileName, "rb")
        fileContent = bencodepy.decode(fp.read())
        if b"announce" in fileContent:
            self.announceURL = fileContent[b"announce"].decode()

        self.infoDictionary = fileContent[b"info"]
        self.nameOfFile = self.infoDictionary[b"name"].decode()
        self.pieces = self.infoDictionary[b"pieces"]
        self.pieceLength = self.infoDictionary[b"piece length"]
        self.infoHash = self._generate_infoHash()
        self._generate_hashOfPieces()
        if b"announce-list" in fileContent:
            for i in fileContent[b"announce-list"]:
                for j in i:
                    self.announceList.append(j.decode())
        if b"files" in self.infoDictionary:
            # multifile torrent
            for file in self.infoDictionary[b"files"]:
                fileDict = {}
                fileDict["length"] = file[b"length"]
                fileDict["path"] = file[b"path"]
                path = ""
                for i in fileDict["path"]:
                    path += i.decode() + "/"
                fileDict["path"] = path[:-1]
                self.filesInfo.append(fileDict)
                self.lengthOfFileToBeDownloaded += file[b"length"]
        else:
            #  single file torrent
            self.lengthOfFileToBeDownloaded = self.infoDictionary[b"length"]

    def __str__(self):
        return f"announceURL: {self.announceURL}\nfilename : {self.nameOfFile}\ninfoHash : {self.infoHash}\nfilesInfo :{self.filesInfo}\nlengthOfFileToBeDownloaded : {self.lengthOfFileToBeDownloaded}"


class httpTracker(FileInfo):
    def __init__(self, fileName):
        super().__init__(fileName)
        super().extractFileMetaData()

    def httpTrackerRequest(self):

        params = {"info_hash": self.infoHash, "peer_id": self.peerID, "port": self.portNo, "uploaded": self.uploaded,
                  "downloaded": self.downloaded, "left": self.lengthOfFileToBeDownloaded, "compact": 1}
        try:
            announceResponse = requests.get(
                self.announceURL, params, timeout=10).content
        except:
            logger.info("Error : request module")
            return False
        try:
            trackerResponseDict = bencodepy.decode(announceResponse)
            logger.info(str(trackerResponseDict))
        except:
            logger.info("Unable to decode tracker response")
            return False

        # if 'complete' in tracekerResponseDict:
        if b'complete' in trackerResponseDict:
            self.seeders = trackerResponseDict[b"complete"]
        if b'incomplete' in trackerResponseDict:
            self.leachers = trackerResponseDict[b"incomplete"]
        if b'interval' in trackerResponseDict:
            self.trackerInterval = trackerResponseDict[b"interval"]

        self.trackerPeers = trackerResponseDict[b"peers"]
        if isinstance(self.trackerPeers, list):
            for peer in self.trackerPeers:
                self.peerAddresses.append((peer[b'ip'], peer[b'port']))
        else:  # binary model
            allPeers = self._generate_peers()

            for i in allPeers:
                self.peerAddresses.append(self.extractIPAdressandPort(i))
        return True


class udpTracker(FileInfo):
    """
    https://www.libtorrent.org/udp_tracker_protocol.html
    http://xbtt.sourceforge.net/udp_tracker_protocol.html
    """

    def __init__(self, fileName):
        self.currentTrackerURL = ""
        super().__init__(fileName)
        super().extractFileMetaData()

    def udpTrackerRequest(self):
        if(self.udpTrackerRequest1()):
            if(self.udpTrackerRequest2()):
                return True
        return False

    def udpTrackerRequest1(self):
        parsedURL = urllib.parse.urlparse(self.announceURL)
        self.connectionSocket = socket(AF_INET, SOCK_DGRAM)
        self.url = parsedURL.netloc.split(":")[0]
        self.trackerPort = parsedURL.port
        connectionID = 0x41727101980
        action = 0
        transactionID = random.randint(5, 1000)
        connectionRequestString = struct.pack("!q", connectionID)
        connectionRequestString += struct.pack("!i", action)
        connectionRequestString += struct.pack("!i", transactionID)

        reply = self.udprecvTrackerResponse(connectionRequestString)
        if reply == "":
            return False
        self.actionID, self.transactionID, self.connectionID = struct.unpack(
            "!iiq", reply)
        if(len(reply) < 16 or self.actionID != 0 or transactionID != self.transactionID):
            # error
            return False
        return True

    def udpTrackerRequest2(self):
        announcePacket = self.createAnnouncePacket()
        reply = self.udprecvTrackerResponse(announcePacket)
        if reply == "":
            return False

        announceActionID, transactionID, self.interval, self.leechers, self.seeders = struct.unpack(
            "!iiiii", reply[:20])

        if(len(reply) < 20 or announceActionID != 1 or transactionID != self.transactionID):
            # error
            return False

        self.trackerPeers = reply[20:]

        allPeers = self._generate_peers()
        # if tracker didnt has any peers
        if len(allPeers) == 0:
            return False
        self.peerAddresses = []
        for i in allPeers:
            self.peerAddresses.append(self.extractIPAdressandPort(i))
        logger.info(str(self.peerAddresses))

        return True

    def udprecvTrackerResponse(self, message):
        self.connectionSocket.settimeout(5)
        try:
            self.connectionSocket.sendto(message, (self.url, self.trackerPort))
            reply, trackerAdress = self.connectionSocket.recvfrom(2048)

        except:
            logger.info("timeout in udprecvTrackerResponse")
            return ""
        return reply

    def createAnnouncePacket(self):
        # for announce actionID=1
        self.actionID = 1
        announcePacket = struct.pack("!q", self.connectionID)
        announcePacket += struct.pack("!i", self.actionID)
        announcePacket += struct.pack("!i", self.transactionID)
        announcePacket += struct.pack("!20s", self.infoHash)
        announcePacket += struct.pack("!20s", self.peerID.encode())
        announcePacket += struct.pack("!q", self.downloaded)
        announcePacket += struct.pack("!q", self.lengthOfFileToBeDownloaded)
        announcePacket += struct.pack("!q", self.uploaded)
        # 2 for start of downloading
        announcePacket += struct.pack("!i", 2)
        # IP adress set to 0 ,if we want tracker to detect ip adress
        announcePacket += struct.pack("!I", 0)
        # any random key
        announcePacket += struct.pack("!I", random.randint(0, 1000))
        # Number of peers to be connected, -1 for default number of peers
        announcePacket += struct.pack("!i", -1)
        announcePacket += struct.pack("!H", self.portNo)
        return announcePacket
