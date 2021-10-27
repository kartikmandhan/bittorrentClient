import struct
from socket import *


class PeerWireProtocol:
    def __init__(self, torrentFileInfo):
        self.infoHash = torrentFileInfo.infoHash
        self.myPeerID = torrentFileInfo.peerID
        self.numberOfPieces = len(torrentFileInfo.hashOfPieces)
        self.peerAddresses = torrentFileInfo.peerAddresses
        # timepass nikal dege
        self.torreFileInfo = torrentFileInfo

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

    def _generateRequestMsg(self, index, begin, length):
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

    def _generateBitFieldMsg(self, x, payload):
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

    def handshakeRequest(self):
        handshakePacket = self.makeHandshakePacket()
        for add in self.peerAddresses:
            # peerAdress = ('66.212.20.8', 6881)
            connectionSocket = socket(AF_INET, SOCK_STREAM)
            connectionSocket.settimeout(5)
            try:
                connectionSocket.connect(add)
                break
            except:
                connectionSocket.close()
                print("Faltu peer")
                continue
        connectionSocket.send(handshakePacket)
        response = b""
        while(1):
            try:
                response += connectionSocket.recv(4096)
            except:
                print("timeout1")
                break
        print("Handshake Response :", response)
        print()
        connectionSocket.settimeout(None)
        recvdinfoHash, handshakeLen = self.decodeHandshakeResponse(response)
        # print("my infohash", self.infoHash)
        if(recvdinfoHash != self.infoHash):
            # error handshake failed
            print("Info Hash unmatched")
            return False

        peerMessages = self.decodeMsg(response[handshakeLen:])
        print(peerMessages)
        # lenPrefix = struct.unpack(
        #     "!i", response[handshakeLen:handshakeLen + 4])[0]
        # ID = struct.unpack("!b", response[handshakeLen+4:handshakeLen + 5])
        # ID = int.from_bytes(ID, "big")
        # # if id==5 then bitfield
        # print(lenPrefix, ID)
        connectionSocket.send(self._generateInterestedMsg())
        # i = 0
        # while(i < 2):
        response1 = connectionSocket.recv(4096)

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
        connectionSocket.send(self._generateRequestMsg(0, 0, 2 ** 14))
        block = b''
        connectionSocket.settimeout(10)
        while(1):
            try:
                block += connectionSocket.recv(16384)
            except:
                print("timeout")
                break
        connectionSocket.settimeout(None)
        print("Block size :", len(block))
        print("Piece Size : ", self.torreFileInfo.pieceLength)
        # print(block)
        peerMessages = self.decodeMsg(block)
        print(peerMessages)
        return True

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

    def makeHandshakePacket(self):
        pstr = "BitTorrent protocol"
        pstrlen = len(pstr)
        reserved = 0
        handshakePacket = struct.pack("!b", pstrlen)
        handshakePacket += struct.pack("!19s", pstr.encode())
        handshakePacket += struct.pack("!q", reserved)
        handshakePacket += struct.pack("!20s", self.infoHash)
        handshakePacket += struct.pack("!20s", self.myPeerID.encode())
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
