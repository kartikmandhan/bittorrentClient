import os


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
