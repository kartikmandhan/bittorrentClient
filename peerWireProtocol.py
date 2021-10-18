import struct
from socket import *
class PeerWireProtocol:
    def __init__(self, torrentFileInfo):
        self.infoHash = torrentFileInfo.infoHash
        self.myPeerID = torrentFileInfo.peerID
        
    def handshakeRequest(self):
        peerAdress=("89.23.141.201",44121)
        handshakePacket = self.makeHandshakePacket()
        connectionSocket=socket(AF_INET,SOCK_STREAM)
        connectionSocket.connect(peerAdress)
        connectionSocket.send(handshakePacket)
        response = connectionSocket.recv(4096)
        print(response)
        # peer.send(handshakePacket)
        # handshakeResponse = peer.recv()

        # recvdinfoHash =self.decodeHandshakeResponse(handshakeResponse)
        # if(recvdinfoHash != self.infoHash):
        #     #error handshake failed
        #     return
        
    def decodeHandshakeResponse(self, response):
        pstrlen, pstr, reserved, recvdinfoHash, peerID = struct.unpack("!b19sq20s20s", response)
        return recvdinfoHash 

    def makeHandshakePacket(self):
        pstr = "BitTorrent protocol"
        pstrlen = len(pstr)
        reserved = 0
        handshakePacket=struct.pack("!b", pstrlen)
        handshakePacket+=struct.pack("!19s", pstr.encode())
        handshakePacket+=struct.pack("!q", reserved)
        handshakePacket+=struct.pack("!20s", self.infoHash)
        handshakePacket+=struct.pack("!20s", self.myPeerID.encode())
        return handshakePacket