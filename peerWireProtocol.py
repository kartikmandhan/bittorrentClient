import struct
from socket import *


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
            if(len(response) < 4):
                return {"error": "Invalid Response"}
            lenPrefix = struct.unpack("!i", response[current: current + 4])[0]
            if(lenPrefix == 0):
                return
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
        self.torreFileInfo = torrentFileInfo
        self.IP = IP
        self.port = port
        # initial state is client not interested
        self.am_choking = True
        self.am_interested = False
        self.peer_choking = True
        self.peer_interested = False
        self.bitfield = 0
        self.connectionSocket = socket(AF_INET, SOCK_STREAM)
        self.isHandshakeDone = False
        # since makeConnectiona doHandshake Both require timeout
        self.connectionSocket.settimeout(10)

    def decodeHandshakeResponse(self, response):
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
            return True
        except:
            print("Unable Establish TCP Connection")
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
                    print("Received Incorrect Info Hash")
                    return False
            except Exception as errorMsg:
                self.connectionSocket.close()
                print("Error in doHandshake : ", errorMsg)
                return False
        return False

    def sendMsg(self, ID=None, optional=None):
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

    def scraped(self):
        # i = 0
        # while(i < 2):
        response1 = self.connectionSocket.recv(4096)

        # i += 1
        print(response1)
        # if len(response1) > 0:
        #     lenPrefix = struct.unpack("!i", response1[:4])[0]
        #     ID = struct.unpack("!b", response1[4:5])
        #     ID = int.from_bytes(ID, "big")
        #     print(lenPrefix, ID)

        peerMessages = self.decodeMsg(response1)
        print(peerMessages)

        print("Number of pieces :", self.numberOfPieces)
        # peer.send(handshakePacket)
        # handshakeResponse = peer.recv()
        self.connectionSocket.send(self._generateRequestMsg(0, 0, 2 ** 14))
        block = b''
        self.connectionSocket.settimeout(10)
        while(1):
            try:
                block += self.connectionSocket.recv(16384)
            except:
                print("timeout")
                break
        self.connectionSocket.settimeout(None)
        print("Block size :", len(block))
        print("Piece Size : ", self.torreFileInfo.pieceLength)
        # print(block)
        peerMessages = self.decodeMsg(block)
        print(peerMessages)
        return True

    def receiveMsg(self):
        response = b''
        while(1):
            try:
                response += self.connectionSocket.recv(4096)
            except timeout:
                break
            except Exception as errorMsg:
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
