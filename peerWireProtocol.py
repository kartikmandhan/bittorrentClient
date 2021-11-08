from enum import Flag
import struct
from socket import *
import time
import hashlib
from math import ceil

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
        # len(lenPrefix)+ 1 byte of Id==5
        payloadStartIndex = 5
        current = 0
        peerMessages = {}
        while(current != len(response)):
            if(len(response) - current < 4):
                return {"error": "Invalid Response"}
            lenPrefix = struct.unpack("!i", response[current: current + 4])[0]
            if(lenPrefix == 0):
                return peerMessages
            ID = struct.unpack("!b", response[current + 4: current + 5])
            ID = int.from_bytes(ID, "big")

            if ID == 0:
                # choke
                peerMessages["keepAlive"] = True
                current += payloadStartIndex
            if ID == 1:
                # unchoke
                peerMessages["unchoke"] = True
                current += payloadStartIndex
                self.peer_choking = False
            if ID == 2:
                # interested
                peerMessages["interested"] = True
                current += payloadStartIndex
            if ID == 3:
                # not interested
                peerMessages["notInterested"] = True
                current += payloadStartIndex
            if ID == 4:
                # have
                pieceIndex = struct.unpack(
                    "!i", response[current + payloadStartIndex: current + payloadStartIndex + 4])
                peerMessages["have"] = pieceIndex
                current += (lenPrefix-1) + payloadStartIndex
            if ID == 5:
                # since lenPrefix=lenofpayload+ 1 byte of ID
                bitfield = response[current + payloadStartIndex:(lenPrefix-1) +
                                    current + payloadStartIndex]
                # print("Bitfield : \n", len(bitfield)*8)
                peerMessages["bitfield"] = bitfield
                # return ("bitfield", bitfield)
                current += (lenPrefix-1) + payloadStartIndex
            if ID == 6:
                # Request
                pass
            if ID == 7:
                # piece
                payload = response[current + payloadStartIndex:(
                    lenPrefix-1) + current + payloadStartIndex]
                index, begin = struct.unpack("!ii", payload[:8])
                block = payload[8:]
                peerMessages["piece"] = [index, begin, block]
                # return ("piece", [index, begin, block])
                current += (lenPrefix-1) + payloadStartIndex
            if ID == 8:
                payload = response[current + payloadStartIndex:(
                    lenPrefix-1) + current + payloadStartIndex]
                index, begin = struct.unpack("!ii", payload[:8])
                length = payload[8:]
                peerMessages["cancel"] = [index, begin, length]
                # return ("piece", [index, begin, block])
                current += (lenPrefix-1) + payloadStartIndex
            if ID == 9:
                listenPort = struct.unpack(
                    "!h", response[current + payloadStartIndex:current + payloadStartIndex + 2])
                peerMessages["port"] = listenPort
                current += (lenPrefix-1) + payloadStartIndex
        return peerMessages


class Peer(PeerWireProtocol):
    def __init__(self, IP, port, torrentFileInfo):
        self.infoHash = torrentFileInfo.infoHash
        self.myPeerID = torrentFileInfo.peerID
        self.numberOfPieces = len(torrentFileInfo.hashOfPieces)
        self.peerAddresses = torrentFileInfo.peerAddresses
        # timepass nikal dege
        self.torrentFileInfo = torrentFileInfo
        self.IP = IP
        self.port = port
        # initial state is client not interested
        self.state=peerState()
        self.keepAliveTimeout = 10
        # keep alive timer
        self.keepAliveTimer = None
        self.bitfield = set()
        self.connectionSocket = socket(AF_INET, SOCK_STREAM)
        self.isHandshakeDone = False
        # since makeConnectiona doHandshake Both require timeout
        self.connectionSocket.settimeout(10)
        self.isConnectionAlive = False
        self.piece=b""
        # to keep track if peer is currently being requested a piece
        self.isDownloading=False

    def decodeHandshakeResponse(self, response):
        if(len(response) < 68):
            print("ganda response", response)
            return
        pstrlen = struct.unpack("!b", response[:1])
        pstrlen = int.from_bytes(pstrlen, 'big')
        pstr = struct.unpack("!19s", response[1: pstrlen + 1])[0]
        reserved = struct.unpack("!q", response[pstrlen + 1:pstrlen + 9])[0]
        recvdinfoHash = struct.unpack(
            "!20s", response[pstrlen + 9:pstrlen + 29])[0]
        # recvdinfoHash = recvdinfoHash.decode()
        peerID = struct.unpack(
            "!20s", response[pstrlen + 29:pstrlen + 49])[0]
        print(pstrlen, pstr, reserved, recvdinfoHash, peerID)
        return (recvdinfoHash, pstrlen + 49)

    def makeConnection(self):
        try:
            self.connectionSocket.connect((self.IP, self.port))
            self.isConnectionAlive = True
            return True
        except:
            print("Unable Establish TCP Connection")
            self.isConnectionAlive = False
            return False

    def doHandshake(self):
        if(self.makeConnection() and not self.isHandshakeDone):
            handshakePacket = self.makeHandshakePacket(
                self.infoHash, self.myPeerID)
            self.connectionSocket.send(handshakePacket)
            handshakeResponse = b""
            try:
                HANDSHAKE_PACKET_LENGTH = 68
                handshakeResponse = self.connectionSocket.recv(
                    HANDSHAKE_PACKET_LENGTH)
                # print("Handshake Response :", handshakeResponse, len(handshakeResponse))
                recvdinfoHash, handshakeLen = self.decodeHandshakeResponse(
                    handshakeResponse)
                # print("my infohash", self.infoHash)
                if(recvdinfoHash == self.infoHash):
                    self.isHandshakeDone = True
                    print("Info Hash matched")
                    return True
                else:
                    self.connectionSocket.close()
                    self.isConnectionAlive = False
                    print("Received Incorrect Info Hash")
                    return False
            except Exception as errorMsg:
                print("Error in doHandshake : ", errorMsg, handshakeResponse)
                self.isConnectionAlive = False
                return False
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
            self.isConnectionAlive = False
            print("error in sendmsg")
            return False

    def receiveMsg(self):
        response = b''
        while(1):
            try:
                response += self.connectionSocket.recv(4096)
            except timeout:
                break
            except Exception as errorMsg:
                self.isConnectionAlive = False
                print("Error in receiveMsg : ", errorMsg)
        return response

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
            self.state = DOWNSTATE0
            print("\x1b]35mChoking ........")
        if 'unchoke' in messages:
            self.state = DOWNSTATE2
        if 'keepAlive' in messages:
            self.keepAliveTimer=time.time()
        if 'interested' in messages:
            pass
        if 'notInterested' in messages:
            pass
        if 'bitfield' in messages:
            self.extractBitField(messages['bitfield'])
        if 'have' in messages:
            # self.bitfield.add(messages['have'])
            pass
        if 'request' in messages:
            pass
        
    def peerFSM( self,pieceNumber):
        isPieceDownloaded = False
        isFiniteMachineON = True
        #DOWNSTATE are the objects of peerState Class
        while isFiniteMachineON:
            print(self.state)
            # client state 0    : (client = not interested,  peer = choking)
            if(self.state == DOWNSTATE0):
                if(self.sendMsg(2)):
                    self.state=DOWNSTATE1

            # client state 1    : (client = interested,      peer = choking)
            elif(self.state == DOWNSTATE1):
                # recieve message 
                response = self.receiveMsg()
                messages = self.decodeMsg(response)
                self.handleMessages(messages)
                # self.state=DOWNSTATE2

            # client state 2    : (client = interested,      peer = not choking)
            elif(self.state == DOWNSTATE2):
                # download the piece when in this state 
                isPieceDownloaded = self.downloadPiece(pieceNumber)
                isFiniteMachineON = False

            #   think of sending uninterested messages in this state of FSM
            elif(self.state==DOWNSTATE3):
                isFiniteMachineON = False

        return isPieceDownloaded
        
    def downloadPiece(self,pieceNumber):
        print("Downloading Piece ..", pieceNumber, flush='true')
        ###
        BLOCK_SIZE = 2**14
        numberOfBlocks = ceil(self.torrentFileInfo.pieceLength/(BLOCK_SIZE))
        currentPieceLength = self.torrentFileInfo.pieceLength
        if pieceNumber == self.torrentFileInfo.numberOfPieces-1:
            currentPieceLength = (self.torrentFileInfo.lengthOfFileToBeDownloaded -
                                (pieceNumber * self.torrentFileInfo.pieceLength))
            numberOfBlocks = ceil(currentPieceLength/BLOCK_SIZE)
            print("last piecelength", currentPieceLength, numberOfBlocks)
        ###
        piece = b''
        offset = 0
        blockNumber = 0
        currentBlockLength = 0
        while blockNumber < numberOfBlocks:
            if currentPieceLength-offset >= BLOCK_SIZE:
                currentBlockLength = BLOCK_SIZE
            else:
                currentBlockLength = currentPieceLength - offset
            print(currentBlockLength, currentPieceLength)
            block = self.downloadBlock(pieceNumber, offset, currentBlockLength)
            if len(block) == 0:
                print("Unable to Download block")
                return (False, b'')
            piece += block
            offset += len(block)
            print("Donwloaded Block ...", blockNumber, pieceNumber)
            blockNumber += 1

        pieceHash = hashlib.sha1(piece).digest()
        print(pieceHash, self.torrentFileInfo.hashOfPieces[pieceNumber])
        if pieceHash == self.torrentFileInfo.hashOfPieces[pieceNumber]:
            print("pieceHash matched,writing in file", self.torrentFileInfo.nameOfFile)
            # writePieceInFile(pieceNumber, piece)
            return (True, piece)
        return (False, b'')


    def downloadBlock(self, pieceNumber, offset, blockLength):
        if self.isHandshakeDone == False:
            print("hndshake not done .....")
            return b''
        if self.peer_choking == True:
            print("choking  .....")
            return b''
        retries = 0
        while(retries < 3):
            if self.isConnectionAlive == False:
                print("Connection Not Alive ..")
                break
            if(self.sendMsg(6, (pieceNumber, offset, blockLength))):
                # peer.connectionSocket.settimeout(None)
                response = self.decodeMsg(self.receiveMsg())
                if response and 'piece' in response:
                    # print("response of piece : ", response, flush='true')
                    return response['piece'][2]
            retries += 1
            print("Retrying ......")
        return b''

    # def isAbleToDownload(self):
    #     if self.isConnectionAlive == False or self.isHandshakeDone == False:
    #         return False
    #     return True

class peerState():
    def __init__(self):
        self.am_choking = True   
        self.am_interested = False
        self.peer_choking = True   
        self.peer_interested = False           
    
    def makeDeadState(self):
        self.am_choking = None  
        self.am_interested = None
        self.peer_choking = None  
        self.peer_interested = None           

    def __eq__(self, other): 
        if self.am_choking != other.am_choking :
            return False
        if self.am_interested != other.am_interested:
            return False
        if self.peer_choking != other.peer_choking: 
            return False
        if self.peer_interested != other.peer_interested:
            return False
        return True
    
    def  __ne__(self, other):
        return not self.__eq__(other)

    def __str__(self):
        peer_state_log  = '[ client choking : '     + str(self.am_choking)
        peer_state_log += ', client interested : '  + str(self.am_interested) 
        peer_state_log += ', peer choking : '       + str(self.peer_choking)
        peer_state_log += ', peer interested : '    + str(self.peer_interested) + ']'
        return peer_state_log

DOWNSTATE0 = peerState()

DOWNSTATE1 = peerState()
DOWNSTATE1.am_interested   = True
    
DOWNSTATE2 = peerState()
DOWNSTATE2.am_interested   = True
DOWNSTATE2.peer_choking    = False

DOWNSTATE3 = peerState()
DOWNSTATE3.makeDeadState()

UPSTATE0 = peerState()

UPSTATE1 = peerState()
UPSTATE1.peer_interested = True
   
UPSTATE2 = peerState()
UPSTATE2.peer_interested = True
UPSTATE2.am_choking = False

UPSTATE3 = peerState()
UPSTATE3.makeDeadState()


