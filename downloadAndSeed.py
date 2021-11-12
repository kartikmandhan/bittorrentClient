from threading import Thread, get_native_id, Lock
import time
import os
import random
import sys
from socket import *


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

    def getBitfield(self, peer, peerNumber):
        # print("I am in getBitfield", get_native_id(), flush="true")
        retry = 0
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

    def download(self):
        self.fileHandler.createFiles()
        for peerNumber, peer in enumerate(self.allPeers):
            if peerNumber >= 30:
                break
            thread = Thread(target=self.getBitfield, args=(peer, peerNumber))
            thread.start()
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
        self.clientPeer = Peer('', 6885, self.torrentFileInfo)
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
                if not peer.isConnectionAlive or not peer.isHandshakeDone:
                    Thread(target=self.getBitfield,
                           args=(peer, peerNumber)).start()
                continue
            else:
                return peer
        return None


class fileOperations():
    def __init__(self, torrentFileInfo, parentDir="./"):
        self.torrentFileInfo = torrentFileInfo
        self.isMultiFile = False
        if len(torrentFileInfo.filesInfo) != 0:
            self.isMultiFile = True
        self.parentDir = parentDir
        if self.isMultiFile:
            self.parentDir += torrentFileInfo.nameOfFile

    def writeNullToFile(self, fp, size):
        # data = b"\x00" * size
        # fp.write(data)
        pass

    def writePieceInFile(self, pieceNumber, piece, filePath):
        with open(os.path.join(self.parentDir, filePath), 'rb+') as fp:
            fp.seek(pieceNumber*self.torrentFileInfo.pieceLength, 0)
            fp.write(piece)

    def createFiles(self):
        if self.isMultiFile:
            for file in self.torrentFileInfo.filesInfo:
                filePath = file["path"]
                dirs = os.path.dirname(filePath)
                # print("dirs", dirs)
                print("parent", self.parentDir)
                if len(dirs) > 0:
                    dirsPath = os.path.join(self.parentDir, dirs)
                else:
                    dirsPath = self.parentDir
                # print("dirspath", self.parentDir, dirsPath)
                if not os.path.exists(dirsPath):
                    print("herer")
                    os.makedirs(dirsPath)
                # create files at specified location
                with open(os.path.join(self.parentDir, filePath), 'wb') as fp:
                    self.writeNullToFile(fp, file["length"])
                    pass
        else:
            with open(os.path.join(self.parentDir, self.torrentFileInfo.nameOfFile), 'wb') as fp:
                self.writeNullToFile(
                    fp, self.torrentFileInfo.lengthOfFileToBeDownloaded)

    def writePiece(self, pieceNumber, piece):

        if not self.isMultiFile:
            self.writePieceInFile(pieceNumber, piece,
                                  self.torrentFileInfo.nameOfFile)
        else:
            offset = (pieceNumber * self.torrentFileInfo.pieceLength)
            allFiles = self.torrentFileInfo.filesInfo
            i = 0
            while i < len(allFiles):
                if offset < allFiles[i]["length"]:
                    if len(piece) <= allFiles[i]["length"] - offset:
                        fp = open(os.path.join(self.parentDir,
                                  allFiles[i]['path']), 'rb+')
                        fp.seek(offset, 0)
                        fp.write(piece)
                        fp.close()
                        return
                    else:
                        # condition when piece size is greater than filesizes
                        while(len(piece) != 0):
                            pieceToWrite = piece[:(
                                allFiles[i]["length"] - offset)]
                            fp = open(os.path.join(self.parentDir,
                                                   allFiles[i]['path']), 'rb+')
                            fp.seek(offset, 0)
                            fp.write(pieceToWrite)
                            fp.close()
                            piece = piece[(allFiles[i]["length"] - offset):]
                            offset = 0
                            i += 1
                        return
                else:
                    offset -= allFiles[i]["length"]
                    i += 1

    def readBlock(self, pieceNumber, offset, length):
        block = b''
        if not self.isMultiFile:
            try:
                fp = open(os.path.join(self.parentDir,
                                       self.torrentFileInfo.nameOfFile), 'rb+')
                offset += pieceNumber * self.torrentFileInfo.pieceLength
                fp.seek(offset, 0)
                block = fp.read(length)
                fp.close()
                return block, True
            except:
                return block, False
        else:
            try:
                pieceOffset = (
                    pieceNumber * self.torrentFileInfo.pieceLength)
                allFiles = self.torrentFileInfo.filesInfo
                i = 0
                pieceLength = self.torrentFileInfo.pieceLength
                if pieceNumber == self.torrentFileInfo.numberOfPieces-1:
                    pieceLength = (self.torrentFileInfo.lengthOfFileToBeDownloaded -
                                   (pieceNumber * self.torrentFileInfo.pieceLength))
                while i < len(allFiles):
                    if pieceOffset < allFiles[i]["length"]:
                        # checking if the single file can contain the whole piece
                        if pieceLength <= allFiles[i]["length"] - pieceOffset:
                            fp = open(os.path.join(self.parentDir,
                                                   allFiles[i]['path']), 'rb+')
                            blockOffset = pieceOffset + offset
                            fp.seek(blockOffset, 0)
                            block = fp.read(length)
                            fp.close()
                            return block, True
                        else:
                            # when piece lies in multiple files
                            piece = b''
                            while(pieceLength > 0):
                                pieceToRead = (
                                    allFiles[i]["length"] - pieceOffset)
                                fp = open(os.path.join(self.parentDir,
                                                       allFiles[i]['path']), 'rb+')
                                fp.seek(pieceOffset, 0)
                                piece += fp.read(pieceToRead)
                                fp.close()
                                pieceLength -= (allFiles[i]
                                                ["length"] - pieceOffset)
                                pieceOffset = 0
                                i += 1
                            return piece[offset:offset + length], True
                    else:
                        # condition when piece size is greater than filesizes
                        pieceOffset -= allFiles[i]["length"]
                        i += 1
            except:
                return block, False
