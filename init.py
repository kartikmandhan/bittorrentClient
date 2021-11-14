from downloadAndSeed import *
from threading import Thread, Timer
from peerWireProtocol import *
from torrentFile import *
import math
from loggerConfig import logger, logging
import argparse
import os
from beautifultable import BeautifulTable


def speedChecker(speed):
    speed = int(speed)
    if speed <= 0:
        raise argparse.ArgumentTypeError("speed must be greater than 0")
    return speed


def directoryChecker(path):
    if not os.path.exists(path):
        raise argparse.ArgumentTypeError("specified directory/file not exists")
    return path


def peerChecker(peerNo):
    if int(peerNo) > 100:
        raise argparse.ArgumentTypeError(
            "KKtorrent does not supports peer numbers greater than 100")
    return peerNo


description = "                             KKTorrent                             "
epilog = """Contributors:
                111903039: Kartik Mandhan
                111903044: Kunal Chaudhari"""
parser = argparse.ArgumentParser(add_help=True,
                                 formatter_class=argparse.RawDescriptionHelpFormatter,
                                 description=description, prog="python3 init.py", epilog=epilog)
parser.add_argument("-f", "--filename", metavar="", required=True,
                    help="Directory path of torrent file", type=directoryChecker)
parser.add_argument("-d", "--download", metavar="",
                    help="Destination directory path for downloading file", type=directoryChecker)
parser.add_argument("-s", "--speed", metavar="",
                    help="Set download/upload speed", type=speedChecker)
parser.add_argument("-p", "--maxpeer", metavar="",
                    help="Maximum number of peers", type=peerChecker)
parser.add_argument("-n", "--noseed",  action="store_true",
                    help="Disable seeding")
parser.add_argument("-l", "--debug",  action="store_true",
                    help="Enable logging")

args = vars(parser.parse_args())
fileName = args['filename']
torrentFileData = FileInfo(fileName)
torrentFileData.extractFileMetaData()
if args["download"]:
    DOWNLOAD_PATH = args["download"]
    downloader = downloadAndSeed([], torrentFileData, DOWNLOAD_PATH)
else:
    downloader = downloadAndSeed([], torrentFileData)

if args["noseed"]:
    ALLOW_SEEDING = False
if args["debug"]:
    logger.setLevel(logging.INFO)

interval = 20
ALLOW_SEEDING = True
MAX_INTERVAL = 180


def setInterval(func, sec):
    """ https://stackoverflow.com/questions/2697039/python-equivalent-of-setinterval"""
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
            mainRequestMaker = udpRequestMaker
        elif didUDPAnswer == 2:
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


def convertSize(size_bytes):
    """https://stackoverflow.com/questions/5194057/better-way-to-convert-file-sizes-in-python"""
    if size_bytes == 0:
        return "0B"
    sizeName = ("B", "KB", "MB", "GB", "TB", "PB", "EB", "ZB", "YB")
    i = int(math.floor(math.log(size_bytes, 1024)))
    p = math.pow(1024, i)
    s = round(size_bytes / p, 2)
    return "%s %s" % (s, sizeName[i])


def createTable():
    t = BeautifulTable()
    t.rows.append([torrentFileData.nameOfFile])

    t.rows.append(
        [convertSize(torrentFileData.lengthOfFileToBeDownloaded)])
    t.rows.append([str(downloader.stats.avgDownloadSpeed)+" kbps"])
    t.rows.append([str(downloader.stats.remainingTime)+" s"])
    t.rows.append(
        [convertSize(torrentFileData.pieceLength*downloader.stats.numOfPiecesDownloaded)])
    t.rows.header = ["FileName", "Size",
                     "Average Download Speed", "Time Remaining (ETA)", "Downloaded File Size"]
    return t


def updateProgress():
    while True:
        # os.system("clear")
        t = createTable()
        print(t)
        print("[{0}] {1}%".format("#" * math.floor(downloader.stats.percentdownloaded),
              round(downloader.stats.percentdownloaded, 2)))
        time.sleep(2)
        if not downloader.isDownloadRemaining():
            os.system("clear")
            t.rows[4] = [convertSize(
                torrentFileData.lengthOfFileToBeDownloaded)]
            print(t)
            print("[{0}] {1}%".format("#" * 100, 100))
            return


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
    if interval < MAX_INTERVAL:
        interval += 10


def makeRequest():
    k = Thread(target=updateProgress)
    k.start()
    global downloader
    global interval
    workingPeers, gotPeers = getPeers()
    t = setInterval(wrapper, interval)
    if(gotPeers):
        downloader.allPeers.extend(workingPeers)
        if ALLOW_SEEDING:
            seeding = Thread(target=downloader.seeding)
            seeding.daemon = True
            seeding.start()

        downloader.download()


makeRequest()
