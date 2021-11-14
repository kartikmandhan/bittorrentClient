from threading import Thread, get_native_id, Lock
import time
import os
import random
import sys
from socket import *
from fileOperations import *
from peerWireProtocol import *
from loggerConfig import logger
from Stats import *


class downloadAndSeed():

    def __init__(self, allPeers, torrentFileInfo, parentDir="./"):
        self.allBitfields = {}
        # self.fileDescriptor = open(torrentFileInfo.nameOfFile, "wb+")
        self.lengthOfFileToBeDownloaded = torrentFileInfo.lengthOfFileToBeDownloaded
        self.allPeers = allPeers
        self.downloadedPiecesBitfields = set()
        self.downloadLock = Lock()
        self.torrentFileInfo = torrentFileInfo
        self.fileHandler = fileOperations(
            torrentFileInfo, parentDir)
        self.clientPeer = Peer('', 6885, self.torrentFileInfo)
        self.peerThreadCreatedCount = 0
        self.connectedPeers = []
        self.stats = Stats(torrentFileInfo)

    def getBitfield(self, peerNumber):
        # logger.info("I am in getBitfield", get_native_id(), flush="true")
        retry = 0
        peer = self.allPeers[peerNumber]
        while(1):
            if(peer.doHandshake()):
                logger.info("HandShake Successful .. ")
                response = peer.decodeMsg(peer.receiveMsg())
                logger.info("Response in bitfield : " + str(response))
                peer.handleMessages(response)
                # function call for bitfield
                self.downloadLock.acquire()
                self.connectedPeers.append(peer)
                for pieceNumber in peer.bitfield:
                    if pieceNumber in self.allBitfields:
                        self.allBitfields[pieceNumber].append(peerNumber)
                    else:
                        self.allBitfields[pieceNumber] = [peerNumber]
                self.downloadLock.release()
                # tryToUnchokePeer(peer)
                break
            else:
                retry += 1
                if retry > 3:
                    break

    def isDownloadRemaining(self):
        if self.torrentFileInfo.numberOfPieces != len(self.downloadedPiecesBitfields):
            return True
        return False

    def rarestPieceFirstSelection(self):
        rarestPieces = []
        if len(self.allBitfields) == 0:
            # logger.info("In fun 0", rarestPieces)
            return rarestPieces
        # rarestCount = min(map(len, self.allBitfields.values()))
        rarestCount = min(map(lambda pieceNumber: len(
            self.allBitfields[pieceNumber]) if pieceNumber not in self.downloadedPiecesBitfields else sys.maxsize, self.allBitfields.keys()))
        logger.info("rarestCount " + str(rarestCount) +
                    " " + str(len(self.allBitfields)))
        for pieceNumber in self.allBitfields.keys():
            if len(self.allBitfields[pieceNumber]) == rarestCount and pieceNumber not in self.downloadedPiecesBitfields:
                rarestPieces.append(pieceNumber)
        # logger.info("In fun", rarestPieces)
        return rarestPieces

    def createPeerThreads(self):
        # use while setting
        # if self.peerThreadCreatedCount > 200:
        #     return
        peerNumber = 0
        while(peerNumber+self.peerThreadCreatedCount < len(self.allPeers)):
            if peerNumber > 20:
                break
            thread = Thread(target=self.getBitfield, args=(
                peerNumber + self.peerThreadCreatedCount,))
            thread.start()
            peerNumber += 1
        self.peerThreadCreatedCount += peerNumber

    def download(self):
        self.fileHandler.createFiles()
        self.createPeerThreads()
        # self.getBitfield(peer, peerNumber)
        while self.isDownloadRemaining():
            rarestPieces = self.rarestPieceFirstSelection()
            if len(rarestPieces) == 0:
                continue
            if len(self.allBitfields) > 0:
                logger.info(str(self.allBitfields))
            allDonwloadingThreads = []
            for pieceNumber in rarestPieces:
                peer = self.peerSelection(pieceNumber)
                if peer == None:

                    # logger.info("no peer is free" + str(pieceNumber))
                    continue
                thread = Thread(target=self.initiateDownloadingPiece,
                                args=(peer, pieceNumber))
                allDonwloadingThreads.append(thread)
                thread.start()
            count = 0
            for thread in allDonwloadingThreads:
                thread.join()
                count += 1
                logger.info("Need to join" + str(len(allDonwloadingThreads)) +
                            "Joined :" + str(count))

        logger.info("Downloaded File " + self.torrentFileInfo.nameOfFile)

    def initiateDownloadingPiece(self, peer, pieceNumber):
        peer.isDownloading = True
        # startTime = time.time()
        self.stats.startTimer()
        isPieceDownloaded, piece = peer.peerFSM(pieceNumber)
        self.stats.endTimer()
        peer.isDownloading = False
        # endTime = time.time()
        if isPieceDownloaded == False:
            return
        self.downloadLock.acquire()
        # logger.info("I am Acquiring Lock")
        # self.allBitfields.pop(pieceNumber)
        self.downloadedPiecesBitfields.add(pieceNumber)
        self.stats.setDownloadSpeed(pieceNumber)

        self.fileHandler.writePiece(pieceNumber, piece)

        logger.info(self.stats.getDownloadStatistics())
        # print(self.stats.getDownloadStatistics())

        self.downloadLock.release()
        # print("Downloaded Number of Pieces ....." +
        #       str(len(self.downloadedPiecesBitfields)))
        logger.info("Downloaded Number of Pieces ....." +
                    str(len(self.downloadedPiecesBitfields)))

        # peer.isDownloading = False
        # logger.info("I am Out of Download Piece",get_native_id())

    def seeding(self):
        self.clientPeer.startSeeding()
        leechers = {}
        while True:
            connectionRecieved = self.clientPeer.acceptConnection()
            logger.info("connection recvd " + str(connectionRecieved))
            if connectionRecieved != None:
                peerSocket, peerAddress = connectionRecieved
                peerIP, peerPort = peerAddress
                peerInstance = Peer(
                    peerIP, peerPort, self.torrentFileInfo, peerSocket, self.fileHandler)
                leechers[peerAddress] = peerInstance
                if len(self.connectedPeers) < 4 or len(leechers.keys()) < 4:
                    continue
                # Top four Algorithm
                self.seedToTop4Peers(leechers)

    def seedToTop4Peers(self, leechers, seedingTo):
        self.connectedPeers.sort(key=self.comparator, reverse=True)
        seedingTo = {}
        for i in range(4):
            if i != 3:
                peer = self.connectedPeers[i]
            else:
                r = random.randint(0, len(leechers))
                randomLeecher = list(leechers.keys())[r]
                peer = leechers[randomLeecher]
            peerAddress = (peer.IP, peer.Port)
            if peerAddress in leechers:
                thread = Thread(
                    target=leechers[peerAddress].uploadInitiator)
                thread.start()
                seedingTo[peerAddress] = leechers.pop(peerAddress)
        time.sleep(60)
        for peerAddress in seedingTo.keys():
            seedingTo[peerAddress].isSeeding = False
            leechers[peerAddress] = seedingTo.pop(peerAddress)

    def peerSelection(self, pieceNumber):

        random.shuffle(self.allBitfields[pieceNumber])
        # peersOfParticularPiece = []
        # for peerNumber in self.allBitfields[pieceNumber]:
        #     peersOfParticularPiece.append(self.allPeers[peerNumber])

        # peersOfParticularPiece.sort(key=self.comparator, reverse=True)
        for peerNumber in self.allBitfields[pieceNumber]:
            peer = self.allPeers[peerNumber]
            if not peer.isDownloading and peer.isConnectionAlive and peer.isHandshakeDone:
                # logger.info("peerNumber"+" " + str(peerNumber)+" " + str(peer.isDownloading)+" " +
                #             str(peer.isConnectionAlive)+" " + str(peer.isHandshakeDone))
                # if not peer.isConnectionAlive or not peer.isHandshakeDone:
                #     Thread(target=self.getBitfield,
                #            args=(peer, peerNumber)).start()
                return peer
        return None

    def comparator(self, peer):
        if not peer.isConnectionAlive:
            return -sys.maxsize
        return peer.peerStats.avgDownloadSpeed
