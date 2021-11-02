# dictionary model of tracker response is yet to implement
import sys
from torrentFile import *
from peerWireProtocol import *
from math import ceil
import hashlib
try:

    fileName = sys.argv[1]
except:
    print("usage python3 init.py <filename> ")
    exit(0)

torrentFileData = FileInfo(sys.argv[1])
torrentFileData.extractFileMetaData()
# print(torrentFileData)
# print(torrentFileData.infoDictionary[b"files"])


def tryAllTrackerURLs(udpRequestMaker, httpRequestMaker):
    didWeRecieveAddresses = False
    didUDPAnswer = -1
    for url in torrentFileData.announceList:
        if "udp://" in url:
            udpRequestMaker.announceURL = url
            if(udpRequestMaker.udpTrackerRequest()):
                didWeRecieveAddresses = True
                didUDPAnswer = 1
                break
        else:
            httpRequestMaker.announceURL = url
            httpRequestMaker.httpTrackerRequest()
            didWeRecieveAddresses = True
            # http answered
            didUDPAnswer = 2
            break
    return (didWeRecieveAddresses, didUDPAnswer)


def makeRequest():
    udpRequestMaker = udpTracker(fileName)
    httpRequestMaker = httpTracker(fileName)
    didWeRecieveAddresses = False
    didUDPAnswer = -1
    print(torrentFileData.announceList)
    if len(torrentFileData.announceList) > 0:
        for i in range(5):
            didWeRecieveAddresses, didUDPAnswer = tryAllTrackerURLs(
                udpRequestMaker, httpRequestMaker)
            if(didWeRecieveAddresses):
                break
    else:
        if "udp://" in torrentFileData.announceURL:
            if(udpRequestMaker.udpTrackerRequest()):
                didWeRecieveAddresses = True
                didUDPAnswer = 1
        else:
            httpRequestMaker.httpTrackerRequest()
            didWeRecieveAddresses = True
            # http answered
            didUDPAnswer = 2

    if(didWeRecieveAddresses):
        if didUDPAnswer == 1:
            # pwp = PeerWireProtocol(udpRequestMaker)
            mainRequestMaker = udpRequestMaker;        
        elif didUDPAnswer == 2:
            # pwp = PeerWireProtocol(httpRequestMaker)
            mainRequestMaker = httpRequestMaker;        
        
        peerAddresses = mainRequestMaker.peerAddresses
        workingPeers=[]
        didreceiveUnchoke=False
        print("Piece Length : ", torrentFileData.pieceLength)
        BLOCK_SIZE=2**14
        numberOfBlocks=ceil(torrentFileData.pieceLength/(BLOCK_SIZE))
        for peer in peerAddresses:
            workingPeers.append(Peer(peer[0], peer[1], mainRequestMaker))
        for peer in workingPeers:
            if(peer.doHandshake()):
                print("HandShake Successful .. ")
                response = peer.decodeMsg(peer.receiveMsg())  
                if 'unchoke' in response:
                    didreceiveUnchoke = True
                peer.sendMsg(2)
                response = peer.decodeMsg(peer.receiveMsg())
                if didreceiveUnchoke or 'unchoke' in response :
                    piece = b''
                    offset = 0
                    indexOfPiece=0
                    for i in range(numberOfBlocks):
                        peer.sendMsg(6, (indexOfPiece ,offset, BLOCK_SIZE))
                        response = peer.decodeMsg(peer.receiveMsg())
                        offset += BLOCK_SIZE
                        print("responseof piecec",response)
                        piece+= response['piece'][2]
                    pieceHash = hashlib.sha1(piece).digest()
                    print(pieceHash , torrentFileData.hashOfPieces[indexOfPiece])
                    print("Length of Piece", len(piece))
                    f = open("temp","wb+")
                    f.write(piece)

                    
    else:
        print("All trackers are useless")
    
    # if(pwp.handshakeRequest() == False):
    #     # close connection
    #     pass
    # else:
    #     print("All trackers are useless")


makeRequest()

# pwp = PeerWireProtocol(torrentFileData)
