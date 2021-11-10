# dictionary model of tracker response is yet to implement
import sys
from torrentFile import *
from peerWireProtocol import *
from math import ceil
from threading import Thread, get_native_id
import hashlib
from downloadAndSeed import *
try:

    fileName = sys.argv[1]
except:
    print("usage python3 init.py <filename> ")
    exit(0)

torrentFileData = FileInfo(sys.argv[1])
torrentFileData.extractFileMetaData()
# print(torrentFileData)
# print(torrentFileData.infoDictionary[b"files"])
print("Paths :", torrentFileData.filesInfo)


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

# this returns empty list once all pieces are requested


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
    else:   # Since trackers list is optional
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
            mainRequestMaker = udpRequestMaker
        elif didUDPAnswer == 2:
            # pwp = PeerWireProtocol(httpRequestMaker)
            mainRequestMaker = httpRequestMaker

        peerAddresses = mainRequestMaker.peerAddresses

        print("Piece Length : ", torrentFileData.pieceLength)
        workingPeers = []
        for peer in peerAddresses:
            workingPeers.append(Peer(peer[0], peer[1], mainRequestMaker))

        downloader = downloadAndSeed(workingPeers, torrentFileData)
        downloader.download()
    else:
        print("All trackers are useless")

    # if(pwp.handshakeRequest() == False):
    #     # close connection
    #     pass
    # else:
    #     print("All trackers are useless")


makeRequest()
# pwp = PeerWireProtocol(torrentFileData)
