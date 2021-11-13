# dictionary model of tracker response is yet to implement
from downloadAndSeed import *
import hashlib
from threading import Thread, get_native_id, Timer
from peerWireProtocol import *
from torrentFile import *
import sys
from loggerConfig import logger
try:

    fileName = sys.argv[1]
except:
    print("usage python3 init.py <filename> ")
    exit(0)

torrentFileData = FileInfo(sys.argv[1])
torrentFileData.extractFileMetaData()

# logger.info(torrentFileData)
# logger.info(torrentFileData.infoDictionary[b"files"])
# logger.info("Paths :", torrentFileData.filesInfo)


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
    # logger.info(torrentFileData.announceList)
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

        logger.info("Piece Length : "+str(torrentFileData.pieceLength))
        logger.info("Peer addresses :"+str(peerAddresses))
        workingPeers = []
        for peer in peerAddresses:
            workingPeers.append(Peer(peer[0], peer[1], torrentFileData))
        return workingPeers, True
    else:
        logger.info("All trackers are useless")
        return [], False


def wrapper():
    global downloader
    global interval
    logger.info("\n\n\n\nwraper called\n\n\n\n")

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
    # if interval < MAX_INTERVAL:
    #     interval += 10
    #     print("wrapperinterval", interval)


downloader = downloadAndSeed([], torrentFileData)

interval = 20

MAX_INTERVAL = 180


def makeRequest():
    global downloader
    global interval
    workingPeers, gotPeers = getPeers()
    t = setInterval(wrapper, interval)
    if(gotPeers):
        downloader.allPeers.extend(workingPeers)
        downloader.download()


startTime = time.time()
makeRequest()
endTime = time.time()
print("speed:" + str((torrentFileData.lengthOfFileToBeDownloaded //
                      (endTime-startTime))*0.008) + "kbps")
# pwp = PeerWireProtocol(torrentFileData)
