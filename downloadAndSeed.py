from threading import Thread, Lock
import time
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
        # {
        # pieceNumber1:[peerNumber1,peerNumber2,...]
        # pieceNumber2:[peerNumber1,peerNumber2,...]
        # }
        self.lengthOfFileToBeDownloaded = torrentFileInfo.lengthOfFileToBeDownloaded
        # list of peers, thus allPeers[allBitfields[<pieceNumber>][0]] will give peer object
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
        """
            Doing handshake with peers and getting bitfields
        """
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
                break
            else:
                # Retry 3 time if handshake failed
                retry += 1
                if retry > 3:
                    break

    def isDownloadRemaining(self):
        """
            Check for downloading progress
        """
        if self.torrentFileInfo.numberOfPieces != len(self.downloadedPiecesBitfields):
            return True
        return False

    def rarestPieceFirstSelection(self):
        """
            Rarest Piece First piece selection stratergy 
        """
        rarestPieces = []
        if len(self.allBitfields) == 0:
            return rarestPieces
        rarestCount = min(map(lambda pieceNumber: len(
            self.allBitfields[pieceNumber]) if pieceNumber not in self.downloadedPiecesBitfields else sys.maxsize, self.allBitfields.keys()))
        logger.info("rarestCount " + str(rarestCount) +
                    " " + str(len(self.allBitfields)))
        for pieceNumber in self.allBitfields.keys():
            if len(self.allBitfields[pieceNumber]) == rarestCount and pieceNumber not in self.downloadedPiecesBitfields:
                rarestPieces.append(pieceNumber)
        return rarestPieces

    def createPeerThreads(self):
        """
            Calls getfield function of new peers
        """
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
        """
        Function to create required files and threads
        """
        self.fileHandler.createFiles()
        self.createPeerThreads()
        while self.isDownloadRemaining():
            # Selecting rarest piece
            rarestPieces = self.rarestPieceFirstSelection()
            if len(rarestPieces) == 0:
                continue
            if len(self.allBitfields) > 0:
                logger.info(str(self.allBitfields))
            allDownloadingThreads = []
            for pieceNumber in rarestPieces:
                # Selecting peer for piece to download
                peer = self.peerSelection(pieceNumber)
                if peer == None:
                    continue
                thread = Thread(target=self.initiateDownloadingPiece,
                                args=(peer, pieceNumber))
                allDownloadingThreads.append(thread)
                thread.start()
            count = 0
            # Waiting for previously requested pieces
            for thread in allDownloadingThreads:
                thread.join()
                count += 1
                logger.info("Need to join" + str(len(allDownloadingThreads)) +
                            "Joined :" + str(count))

        logger.info("Downloaded File " + self.torrentFileInfo.nameOfFile)

    def initiateDownloadingPiece(self, peer, pieceNumber):
        peer.isDownloading = True
        self.stats.startTimer()
        isPieceDownloaded, piece = peer.downloadHandler(pieceNumber)
        self.stats.endTimer()
        peer.isDownloading = False
        if isPieceDownloaded == False:
            return
        # Acquiring lock and updating shared resources
        self.downloadLock.acquire()
        self.downloadedPiecesBitfields.add(pieceNumber)
        self.stats.setDownloadSpeed(pieceNumber)
        self.fileHandler.writePiece(pieceNumber, piece)
        logger.info(self.stats.getDownloadStatistics())
        self.downloadLock.release()
        logger.info("Downloaded Number of Pieces ....." +
                    str(len(self.downloadedPiecesBitfields)))

    def seeding(self):
        """
            Function to do seeding
        """
        self.clientPeer.startSeeding()
        leechers = {}
        while True:
            # Accept incoming connection
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
                # Seeding according to Top four Algorithm
                self.seedToTop4Peers(leechers)

    def seedToTop4Peers(self, leechers):
        # sorting peers according to their contribution in downloading
        self.connectedPeers.sort(key=self.comparator, reverse=True)
        seedingTo = {}
        # Selecting 3 fasted downloadind ans 1 random peer for seeding
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
        # Waiting for 60 sec
        time.sleep(60)
        # Stop seeding to peers
        for peerAddress in seedingTo.keys():
            seedingTo[peerAddress].isSeeding = False
            leechers[peerAddress] = seedingTo.pop(peerAddress)

    def peerSelection(self, pieceNumber):
        """
            Peer selection stratergy
        """
        # shuffling peers
        random.shuffle(self.allBitfields[pieceNumber])
        for peerNumber in self.allBitfields[pieceNumber]:
            peer = self.allPeers[peerNumber]
            # checking
            if not peer.isDownloading and peer.isConnectionAlive and peer.isHandshakeDone:
                if not peer.isConnectionAlive or not peer.isHandshakeDone:
                    Thread(target=self.getBitfield,
                           args=(peer, peerNumber)).start()
                return peer
        return None

    def comparator(self, peer):
        if not peer.isConnectionAlive:
            return -sys.maxsize
        return peer.peerStats.avgDownloadSpeed
