from threading import Thread, get_native_id, Lock
import time
import os
import random
import sys
from socket import *
from fileOperations import *
from peerWireProtocol import *


class downloadAndSeed():

    def __init__(self, allPeers, torrentFileInfo):
        self.allBitfields = {}
        # self.fileDescriptor = open(torrentFileInfo.nameOfFile, "wb+")
        self.lengthOfFileToBeDownloaded = torrentFileInfo.lengthOfFileToBeDownloaded
        self.allPeers = allPeers
        self.downloadedPiecesBitfields = set()
        self.downloadLock = Lock()
        self.torrentFileInfo = torrentFileInfo
        self.fileHandler = fileOperations(torrentFileInfo)
        self.clientPeer = Peer('', 6885, self.torrentFileInfo)
        self.peerThreadCreatedCount = 0

    def getBitfield(self, peerNumber):
        # print("I am in getBitfield", get_native_id(), flush="true")
        retry = 0
        peer = self.allPeers[peerNumber]
        while(1):
            if(peer.doHandshake()):
                print("HandShake Successful .. ")
                response = peer.decodeMsg(peer.receiveMsg())
                print("Response in bitfield :", response)
                peer.handleMessages(response)
                # function call for bitfield
                self.downloadLock.acquire()
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
            # print("In fun 0", rarestPieces)
            return rarestPieces
        # rarestCount = min(map(len, self.allBitfields.values()))
        rarestCount = min(map(lambda pieceNumber: len(
            self.allBitfields[pieceNumber]) if pieceNumber not in self.downloadedPiecesBitfields else sys.maxsize, self.allBitfields.keys()))
        print("rarestCount", rarestCount)
        for pieceNumber in self.allBitfields.keys():
            if len(self.allBitfields[pieceNumber]) == rarestCount and pieceNumber not in self.downloadedPiecesBitfields:
                rarestPieces.append(pieceNumber)
        # print("In fun", rarestPieces)
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
            if len(self.allBitfields) > 0:
                print(self.allBitfields)
            allDonwloadingThreads = []
            if len(self.downloadedPiecesBitfields) > 0:
                print("Donwloaded Number of Pieces .....",
                      len(self.downloadedPiecesBitfields), len(rarestPieces))
            for pieceNumber in rarestPieces:
                peer = self.peerSelection(pieceNumber)
                if peer == None:

                    print("no peer is free", pieceNumber)
                    continue
                thread = Thread(target=self.downloadPiece,
                                args=(peer, pieceNumber))
                allDonwloadingThreads.append(thread)
                thread.start()
            count = 0
            for thread in allDonwloadingThreads:
                thread.join()
                count += 1
                print("Need to join" + str(len(allDonwloadingThreads)) +
                      "Joined :" + str(count))

        print("Downloaded File", self.torrentFileInfo.nameOfFile)

    def downloadPiece(self, peer, pieceNumber):
        peer.isDownloading = True
        startTime = time.time()
        isPieceDownloaded, piece = peer.peerFSM(pieceNumber)
        peer.isDownloading = False
        endTime = time.time()
        if isPieceDownloaded == False:
            return
        print("time taken in downloading a piece", endTime-startTime)
        self.downloadLock.acquire()
        # print("I am Acquiring Lock")
        # self.allBitfields.pop(pieceNumber)
        self.downloadedPiecesBitfields.add(pieceNumber)
        self.fileHandler.writePiece(pieceNumber, piece)
        self.downloadLock.release()
        # peer.isDownloading = False
        # print("I am Out of Download Piece",get_native_id())

    def seeding(self):
        self.clientPeer.startSeeding()
        while True:
            connectionRecieved = self.clientPeer.acceptConnection()
            print("connection recvd", connectionRecieved)
            # if connectionRecieved != None:
            #     peerSocket, peerAddress = connectionRecieved
            #     peerIP, peerPort = peerAddress
            #     peerInstance = Peer(
            #         peerIP, peerPort, self.torrentFileInfo, peerSocket)
            #     Thread(target=peerInstance.uploadInitiator).start()
            # else:
            #     time.sleep(3)

    def peerSelection(self, pieceNumber):
        random.shuffle(self.allBitfields[pieceNumber])
        for peerNumber in self.allBitfields[pieceNumber]:
            peer = self.allPeers[peerNumber]
            if peer.isDownloading or not peer.isConnectionAlive or not peer.isHandshakeDone:
                print("peerNumber", peerNumber, peer.isDownloading,
                      peer.isConnectionAlive, peer.isHandshakeDone)
                # if not peer.isConnectionAlive or not peer.isHandshakeDone:
                #     Thread(target=self.getBitfield,
                #            args=(peer, peerNumber)).start()
                # continue
            else:
                return peer
        return None
