import struct
from socket import *
import time
import hashlib
from math import ceil
from fileOperations import *
from loggerConfig import logger
from Stats import Stats


class PeerWireProtocol:

    def _generateInterestedMsg(self):
        interested = struct.pack("!i", 1)
        interested += struct.pack("!b", 2)
        return interested

    def _generateNotInterestedMsg(self):
        notInterested = struct.pack("!i", 1)
        notInterested += struct.pack("!b", 3)
        return notInterested

    def _generateKeepAliveMsg(self):
        keepAlive = struct.pack("!i", 0)
        return keepAlive

    def _generateChokeMsg(self):
        choke = struct.pack("!i", 1)
        choke += struct.pack("!b", 0)
        return choke

    def _generateUnchokeMsg(self):
        unchoke = struct.pack("!i", 1)
        unchoke += struct.pack("!b", 1)
        return unchoke

    def _generateRequestMsg(self, argument):
        index, begin, length = argument
        request = struct.pack("!i", 13)
        request += struct.pack("!b", 6)
        request += struct.pack("!i", index)
        request += struct.pack("!i", begin)
        request += struct.pack("!i", length)
        return request

    def _generatePieceMsg(self, index, begin, block):
        piece = struct.pack("!i", 13 + len(block))
        piece += struct.pack("!b", 7)
        piece += struct.pack("!i", index)
        piece += struct.pack("!i", begin)
        piece += block
        return piece

    def _generateBitFieldMsg(self, payload):
        bitField = struct.pack("!i", 13 + len(payload))
        bitField += struct.pack("!b", 5)
        bitField += payload
        return bitField

    def _generateHaveMsg(self, pieceIndex):
        have = struct.pack("!i", 1)
        have += struct.pack("!b", 1)
        have += pieceIndex
        return have

    def _generateCancelMsg(self, index, begin, length):
        cancel = struct.pack("!i", 13)
        cancel += struct.pack("!b", 8)
        cancel += struct.pack("!i", index)
        cancel += struct.pack("!i", begin)
        cancel += struct.pack("!i", length)
        return cancel

    def _generatePortMsg(self, listenPort):
        port = struct.pack("!i", 3)
        port += struct.pack("!b", 9)
        port += struct.pack("!h", listenPort)
        return port

    def makeHandshakePacket(self, infoHash, myPeerID):
        pstr = "BitTorrent protocol"
        pstrlen = len(pstr)
        reserved = 0
        handshakePacket = struct.pack("!b", pstrlen)
        handshakePacket += struct.pack("!19s", pstr.encode())
        handshakePacket += struct.pack("!q", reserved)
        handshakePacket += struct.pack("!20s", infoHash)
        handshakePacket += struct.pack("!20s", myPeerID.encode())
        return handshakePacket

    def decodeMsg(self, response):
        if response == None:
            return {}
        payloadStartIndex = 5
        current = 0
        peerMessages = {}
        try:
            while(current != len(response)):
                if(len(response) - current < 4):
                    return {"error": "Invalid Response"}
                lenPrefix = struct.unpack(
                    "!i", response[current: current + 4])[0]
                if(lenPrefix == 0):
                    peerMessages["keepAlive"] = True
                    current += payloadStartIndex - 1
                    continue
                ID = struct.unpack("!b", response[current + 4: current + 5])
                ID = int.from_bytes(ID, "big")

                if ID == 0:
                    peerMessages["choke"] = True
                    current += payloadStartIndex
                if ID == 1:
                    peerMessages["unchoke"] = True
                    current += payloadStartIndex
                if ID == 2:
                    peerMessages["interested"] = True
                    current += payloadStartIndex
                if ID == 3:
                    peerMessages["notInterested"] = True
                    current += payloadStartIndex
                if ID == 4:
                    pieceIndex = struct.unpack(
                        "!i", response[current + payloadStartIndex: current + payloadStartIndex + 4])
                    peerMessages["have"] = pieceIndex
                    current += (lenPrefix-1) + payloadStartIndex
                if ID == 5:
                    bitfield = response[current + payloadStartIndex:(lenPrefix-1) +
                                        current + payloadStartIndex]
                    peerMessages["bitfield"] = bitfield
                    current += (lenPrefix-1) + payloadStartIndex
                if ID == 6:
                    payload = response[current + payloadStartIndex:(
                        lenPrefix-1) + current + payloadStartIndex]
                    index, begin, length = struct.unpack("!iii", payload)
                    peerMessages["request"] = [index, begin, length]
                    current += (lenPrefix-1) + payloadStartIndex
                if ID == 7:
                    payload = response[current + payloadStartIndex:(
                        lenPrefix-1) + current + payloadStartIndex]
                    index, begin = struct.unpack("!ii", payload[:8])
                    block = payload[8:]
                    peerMessages["piece"] = [index, begin, block]
                    current += (lenPrefix-1) + payloadStartIndex
                if ID == 8:
                    payload = response[current + payloadStartIndex:(
                        lenPrefix-1) + current + payloadStartIndex]
                    index, begin = struct.unpack("!ii", payload[:8])
                    length = payload[8:]
                    peerMessages["cancel"] = [index, begin, length]
                    current += (lenPrefix-1) + payloadStartIndex
                if ID == 9:
                    listenPort = struct.unpack(
                        "!h", response[current + payloadStartIndex:current + payloadStartIndex + 2])
                    peerMessages["port"] = listenPort
                    current += (lenPrefix-1) + payloadStartIndex
            return peerMessages
        except:
            logger.info("Error in decodemsg")


class Peer(PeerWireProtocol):
    def __init__(self, IP, port, torrentFileInfo, peerSocket=None, fileHandler=None):
        self.infoHash = torrentFileInfo.infoHash
        self.myPeerID = torrentFileInfo.peerID
        self.numberOfPieces = len(torrentFileInfo.hashOfPieces)
        self.torrentFileInfo = torrentFileInfo
        self.IP = IP
        self.port = port
        self.keepAliveTimeout = 120
        self.keepAliveTimer = None
        self.isSeeding = False
        self.bitfield = set()
        if peerSocket == None:
            # this for downloading
            self.connectionSocket = socket(AF_INET, SOCK_STREAM)
        else:
            # this is for seeding
            self.connectionSocket = peerSocket
        self.isHandshakeDone = False
        # since makeConnectiona doHandshake Both require timeout
        self.connectionSocket.settimeout(4)
        self.isConnectionAlive = False
        # to keep track if peer is currently being requested a piece
        self.isDownloading = False
        self.myBitFieldList = []
        if fileHandler != None:
            self.fileOperations = fileHandler
        self.peerStats = Stats(torrentFileInfo)
        self.amChoking = True
        self.amInterested = False
        self.peerChoking = True
        self.peerInterested = False

    def decodeHandshakeResponse(self, response):
        if(len(response) < 68):
            logger.info("Bad response in handshake " + str(response))
            return (b'', len(response))
        pstrlen = struct.unpack("!b", response[:1])
        pstrlen = int.from_bytes(pstrlen, 'big')
        pstr = struct.unpack("!19s", response[1: pstrlen + 1])[0]
        reserved = struct.unpack("!q", response[pstrlen + 1:pstrlen + 9])[0]
        recvdinfoHash = struct.unpack(
            "!20s", response[pstrlen + 9:pstrlen + 29])[0]
        peerID = struct.unpack(
            "!20s", response[pstrlen + 29:pstrlen + 49])[0]
        logger.info(str(pstrlen) + " " + str(pstr) + " " +
                    str(reserved) + " " + str(recvdinfoHash) + " " + str(peerID))
        return (recvdinfoHash, pstrlen + 49)

    def makeConnection(self):
        try:
            self.connectionSocket.connect((self.IP, self.port))
            self.isConnectionAlive = True
            return True
        except Exception as errorMsg:
            logger.info("Unable Establish TCP Connection")
            self.disconnectPeer()
            return False

    def receiveHandshake(self):
        try:
            HANDSHAKE_PACKET_LENGTH = 68
            handshakeResponse = self.connectionSocket.recv(
                HANDSHAKE_PACKET_LENGTH)
            recvdinfoHash, handshakeLen = self.decodeHandshakeResponse(
                handshakeResponse)
            if(recvdinfoHash == self.infoHash):
                self.isHandshakeDone = True
                self.connectionSocket.settimeout(4)
                self.keepAliveTimer = time.time()
                logger.info("Info Hash matched")
                return True
            else:
                self.isHandshakeDone = False
                logger.info("Received Incorrect Info Hash")
                return False
        except Exception as errorMsg:
            self.isHandshakeDone = False
            logger.info("Error in receiveHandshake ")
            return False

    def doHandshake(self):
        self.connectionSocket.settimeout(25)
        if not self.isConnectionAlive:
            self.makeConnection()

        handshakeResponse = b""
        if(not self.isHandshakeDone and self.isConnectionAlive):
            handshakePacket = self.makeHandshakePacket(
                self.infoHash, self.myPeerID)
            try:
                self.connectionSocket.send(handshakePacket)
                return self.receiveHandshake()
            except Exception as errorMsg:
                logger.info("Error in doHandshake : " + str(handshakeResponse))
                self.disconnectPeer()
                return False
        if(self.isHandshakeDone):
            return True
        return False

    def sendMsg(self, ID=None, optional=None):
        try:
            if ID == None:
                self.connectionSocket.send(self._generateKeepAliveMsg())
            elif ID == 0:
                self.connectionSocket.send(self._generateChokeMsg())
            elif ID == 1:
                self.connectionSocket.send(self._generateUnchokeMsg())
            elif ID == 2:
                self.connectionSocket.send(self._generateInterestedMsg())
            elif ID == 3:
                self.connectionSocket.send(self._generateNotInterestedMsg())
            elif ID == 4:
                self.connectionSocket.send(self._generateHaveMsg(optional))
            elif ID == 5:
                self.connectionSocket.send(self._generateBitFieldMsg())
            elif ID == 6:
                self.connectionSocket.send(self._generateRequestMsg(optional))
            elif ID == 7:
                self.connectionSocket.send(self._generatePieceMsg(optional))
            elif ID == 8:
                self.connectionSocket.send(self._generateCancelMsg())
            elif ID == 9:
                self.connectionSocket.send(self._generatePortMsg())
            return True
        except:
            self.disconnectPeer()
            logger.info("error in sendmsg" + str(ID))
            return False

    def receiveMsg(self):
        if self.isConnectionAlive == False:
            return None
        lengthPrefixSize = 4
        try:
            response = self.connectionSocket.recv(lengthPrefixSize)
            if len(response) < lengthPrefixSize:
                return None
            lenPrefix = struct.unpack("!i", response)[0]
            if lenPrefix == 0:
                # keepAlive message
                return response
            completeResponse = response
            while lenPrefix > 0:
                r = self.connectionSocket.recv(lenPrefix)
                if len(r) == 0:
                    return None
                completeResponse += r
                lenPrefix -= len(r)
        except timeout:
            logger.info("Unable To receive")
            return None
        except Exception as errorMsg:
            self.disconnectPeer()
            logger.info("Error in receiveMsg  ")
            return None
        self.keepAliveTimer = time.time()
        return completeResponse

    def extractBitField(self, bitfieldString):
        self.bitfield = set()
        for i, byte in enumerate(bitfieldString):
            for j in range(8):
                if ((byte >> j) & 1):
                    # since we are evaluating each bit from right to left
                    pieceNumber = i*8+7-j
                    self.bitfield.add(pieceNumber)

    def handleMessages(self, messages):
        if 'choke' in messages:
            self.amInterested = False
            self.peerChoking = True
        if 'unchoke' in messages:
            self.peerChoking = False
        if 'keepAlive' in messages:
            self.keepAliveTimer = time.time()
        if 'interested' in messages:
            self.peerInterested = True
        if 'notInterested' in messages:
            self.peerInterested = False
        if 'bitfield' in messages:
            self.extractBitField(messages['bitfield'])
        if 'have' in messages:
            self.bitfield.add(messages['have'][0])
            logger.info("recieved have msg " + str(messages["have"]))

    def downloadHandler(self, pieceNumber):
        isPieceDownloaded = (False, b'')
        isON = True
        count = 0
        while isON:
            # not interested,   peer choking
            if(not self.amInterested and self.peerChoking):
                if(self.sendMsg(2)):
                    self.amInterested = True
                else:
                    count += 1
                    if count > 3:
                        break
            # interested,    peer choking
            elif(self.amInterested and self.peerChoking):
                response = self.receiveMsg()
                if response == None:
                    self.amInterested = False
                    break
                messages = self.decodeMsg(response)
                self.handleMessages(messages)

            # interested,  peer not choking
            elif(self.amInterested and not self.peerChoking):
                # download the piece when in this state
                isPieceDownloaded = self.downloadPiece(pieceNumber)
                isON = False
        return isPieceDownloaded

    def downloadPiece(self, pieceNumber):
        logger.info("Downloading Piece .." + str(pieceNumber))
        self.peerStats.startTimer()
        BLOCK_SIZE = 2**14
        numberOfBlocks = ceil(self.torrentFileInfo.pieceLength/(BLOCK_SIZE))
        currentPieceLength = self.torrentFileInfo.pieceLength
        if pieceNumber == self.torrentFileInfo.numberOfPieces-1:
            currentPieceLength = (self.torrentFileInfo.lengthOfFileToBeDownloaded -
                                  (pieceNumber * self.torrentFileInfo.pieceLength))
            numberOfBlocks = ceil(currentPieceLength/BLOCK_SIZE)
            logger.info("last piecelength " +
                        str(currentPieceLength) + " " + str(numberOfBlocks))
        piece = b''
        offset = 0
        blockNumber = 0
        currentBlockLength = 0
        while blockNumber < numberOfBlocks:
            if currentPieceLength-offset >= BLOCK_SIZE:
                currentBlockLength = BLOCK_SIZE
            else:
                currentBlockLength = currentPieceLength - offset
            logger.info(str(currentBlockLength) + " " + str(currentPieceLength) + " " +
                        str(numberOfBlocks) + " " + str(blockNumber) + " " + str(pieceNumber))
            block = self.downloadBlock(pieceNumber, offset, currentBlockLength)
            if len(block) == 0:
                logger.info("Unable to Download block" +
                            str(blockNumber) + " " + str(pieceNumber))
                return (False, b'')
            piece += block
            offset += len(block)
            logger.info("Downloaded Block ..." +
                        str(blockNumber) + " " + str(pieceNumber))
            blockNumber += 1

        pieceHash = hashlib.sha1(piece).digest()
        logger.info(str(pieceHash) + " " +
                    str(self.torrentFileInfo.hashOfPieces[pieceNumber]))
        if pieceHash == self.torrentFileInfo.hashOfPieces[pieceNumber]:
            logger.info(
                "pieceHash matched,writing in file , Downloaded Piece .." + str(pieceNumber))
            self.peerStats.endTimer()
            self.peerStats.setDownloadSpeed(pieceNumber)
            return (True, piece)
        return (False, b'')

    def disconnectPeer(self):
        self.isHandshakeDone = False
        self.isConnectionAlive = False
        self.bitfield = set()
        self.isDownloading = False

    def downloadBlock(self, pieceNumber, offset, blockLength):
        if self.isHandshakeDone == False:
            logger.info("hndshake not done .....")
            return b''
        if self.peerChoking == True:
            logger.info("choking  .....")
            return b''
        if self.isConnectionAlive == False:
            logger.info("Connection Not Alive ..")
            return b''
        if(self.sendMsg(6, (pieceNumber, offset, blockLength))):
            # peer.connectionSocket.settimeout(None)
            response = self.decodeMsg(self.receiveMsg())
            if response and 'piece' in response:
                if pieceNumber == response['piece'][0] and offset == response['piece'][1]:
                    return response['piece'][2]
        return b''

    #  upload and leechers related functions

    def startSeeding(self):
        try:
            self.connectionSocket.bind((self.IP, self.port))
            self.connectionSocket.listen()
        except Exception as errorMsg:
            logger.info("Error in startSeeding")

    def acceptConnection(self):
        try:
            connectionSocket = self.connectionSocket.accept()
            return connectionSocket
        except Exception as erroMsg:
            logger.info("Error in acceptConnection ")
            return None

    def createBitField(self):
        bitfield = b""
        pieceByte = 0
        for i in range(self.torrentFileInfo.numberOfPieces):
            if i in self.myBitFieldList:
                piece_byte = piece_byte | (2 ** (7 - (i % 8)))
            if (i + 1) % 8 == 0:
                bitfield += struct.pack("!B", pieceByte)
                pieceByte = 0
        # adding the last piece's bytes
        if self.torrentFileInfo.numberOfPieces % 8 != 0:
            bitfield += struct.pack("!B", pieceByte)

        return bitfield

    def sendBitfield(self):
        self._generateBitFieldMsg(self.createBitField())
        self.sendMsg(5)

    def respondHandshake(self):
        self.keepAliveTimer = time.time()
        while(time.time() - self.keepAliveTimer < self.keepAliveTimeout):
            if(self.receiveHandshake()):
                try:
                    handshakePacket = self.makeHandshakePacket(
                        self.infoHash, self.myPeerID)
                    self.connectionSocket.send(handshakePacket)
                    self.sendBitfield()
                    return True
                except Exception as errorMsg:
                    logger.info("Error in respondHandshake " + errorMsg)
        return False

    def uploadHandler(self):
        self.keepAliveTimer = time.time()
        isON = True
        while isON:
            # checking for keep alive timeouts
            if(time.time() - self.keepAliveTimer > self.keepAliveTimeout):
                self.amChoking = True
                self.peerInterested = False
                self.disconnectPeer()
                isON = False
            # not interested and peer  choking
            elif(self.amChoking and not self.peerInterested):
                response_message = self.handleMessages()
            # interested,  peer  choking
            elif(self.amChoking and self.peerInterested):
                if(self.sendMsg(1)):
                    self.amChoking = False
                else:
                    isON = False
            # interested,  peer not choking
            elif(not self.amChoking and self.peerInterested):
                self.uploadPieces()
                isON = False

    def uploadInitiator(self):
        if self.respondHandshake():
            self.uploadHandler()
        else:
            return

    def uploadPieces(self):
        self.keepAliveTimer = time.time()
        self.peerStats.startTime()
        self.isSeeding = True
        while(self.isSeeding and time.time() - self.keepAliveTimer < self.keepAliveTimeout):
            response = self.receiveMsg()
            if response == None:
                continue
            response = self.decodeMsg(response)
            self.handleMessages(response)
            if "request" in response:
                pieceIndex = response["request"][0]
                offset = response["request"][1]
                length = response["request"][2]
                block, isValid = fileOperations.readBlock(
                    pieceIndex, offset, length)
                if(isValid):
                    self.sendMsg(7, (pieceIndex, offset, block))
                    self.peerStats.endTimer()
                    self.peerStats.setuploadSpeed()
                else:
                    logger.info("Invalid Request for block")
        if self.isSeeding == False:
            self.sendMsg(0)
