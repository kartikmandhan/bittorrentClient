# dictionary model of tracker response is yet to implement
import sys
from torrentFile import *
from peerWireProtocol import *
from math import ceil
from threading import Thread, get_native_id, Timer
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
# print("Paths :", torrentFileData.filesInfo)


def setInterval(func, sec):
    def func_wrapper():
        setInterval(func, sec)
        func()
    t = Timer(sec, func_wrapper)
    t.daemon = True
    t.start()
    return t


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
            if(httpRequestMaker.httpTrackerRequest()):
                didWeRecieveAddresses = True
                # http answered
                didUDPAnswer = 2
                break
    return (didWeRecieveAddresses, didUDPAnswer)

# this returns empty list once all pieces are requested


def getPeers():
    udpRequestMaker = udpTracker(fileName)
    httpRequestMaker = httpTracker(fileName)
    didWeRecieveAddresses = False
    didUDPAnswer = -1
    # print(torrentFileData.announceList)
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
            if(httpRequestMaker.httpTrackerRequest()):
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
        print("Peer addresses :", peerAddresses)
        workingPeers = []
        for peer in peerAddresses:
            workingPeers.append(Peer(peer[0], peer[1], torrentFileData))
        return workingPeers, True
    else:
        print("All trackers are useless")
        return [], False


def wrapper():
    global downloader
    print("\n\n\n\nwraper called\n\n\n\n")

    workingPeers, gotPeers = getPeers()
    if(gotPeers):
        for peer1 in workingPeers:
            isMatched = False
            for peer2 in downloader.allPeers:
                if peer1.IP == peer2.IP and peer1.port == peer2.port:
                    isMatched = True
                    break
            if not isMatched:
                downloader.allPeers.append(peer1)
        downloader.createPeerThreads()


downloader = downloadAndSeed([], torrentFileData)

interval = 20


def makeRequest():
    global downloader
    global interval
    workingPeers, gotPeers = getPeers()
    t = setInterval(wrapper, interval)
    if(gotPeers):
        downloader.allPeers.extend(workingPeers)
        downloader.download()
    interval += 10


startTime = time.time()
makeRequest()
endTime = time.time()
print("speed:", (torrentFileData.lengthOfFileToBeDownloaded //
      (endTime-startTime))*0.008, "kbps")
# pwp = PeerWireProtocol(torrentFileData)
