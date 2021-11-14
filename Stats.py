import time
from loggerConfig import logger


class Stats():
    def __init__(self, torrentFileInfo):
        self.downloadSpeed = 0
        self.maxDownloadSpeed = 0
        self.totalDownloadSpeed = 0
        self.avgDownloadSpeed = 0
        self.uploadSpeed = 0
        self.maxUploadSpeed = 0
        self.totalUploadSpeed = 0
        self.avgUploadSpeed = 0
        self.torrentFileInfo = torrentFileInfo
        self.downloaded = set()
        self.uploaded = set()
        self.startTime = 0
        self.endTime = 0
        self.numOfPiecesDownloaded = 0
        self.numOfPiecesUpload = 0
        self.remainingTime = 0
        self.percentdownloaded = 0

    def setDownloadSpeed(self, pieceNumber):
        currentPieceLength = self.torrentFileInfo.pieceLength
        if pieceNumber == self.torrentFileInfo.numberOfPieces-1:
            currentPieceLength = (self.torrentFileInfo.lengthOfFileToBeDownloaded -
                                  (pieceNumber * self.torrentFileInfo.pieceLength))
        pieceSizeKB = currentPieceLength / 1024
        timeTaken = (self.endTime - self.startTime)
        self.downloadSpeed = round(pieceSizeKB*8 / timeTaken, 2)
        self.downloaded.add(pieceNumber)
        self.numOfPiecesDownloaded += 1
        self.totalDownloadSpeed += self.downloadSpeed
        self.avgDownloadSpeed = round(
            self.totalDownloadSpeed / self.numOfPiecesDownloaded, 2)
        self.maxDownloadSpeed = max(self.maxDownloadSpeed, self.downloadSpeed)
        self.percentdownloaded = round(
            (self.numOfPiecesDownloaded * 100)/self.torrentFileInfo.numberOfPieces, 2)
        self.remainingTime = round((
            self.torrentFileInfo.numberOfPieces - self.numOfPiecesDownloaded) * timeTaken, 2)
        self.remainingTime = time.strftime(
            "%H:%M:%S", time.gmtime(self.remainingTime))

    def startTimer(self):
        self.startTime = time.time()

    def endTimer(self):
        self.endTime = time.time()

    def setUploadSpeed(self, pieceNumber):
        currentPieceLength = self.torrentFileInfo.pieceLength
        if pieceNumber == self.torrentFileInfo.numberOfPieces-1:
            currentPieceLength = (self.torrentFileInfo.lengthOfFileToBeDownloaded -
                                  (pieceNumber * self.torrentFileInfo.pieceLength))
        pieceSizeKB = currentPieceLength / 1024
        timeTaken = (self.endTime - self.startTime)
        self.uploadSpeed = round(pieceSizeKB * 8 / timeTaken, 2)
        self.numOfPiecesUploaded += 1
        self.totalUploadSpeed += self.uploadSpeed
        self.avgUploadSpeed = round(
            self.totalUploadSpeed / self.numOfPiecesUploaded, 2)
        self.maxUploadSpeed = max(self.maxUploadSpeed, self.uploadSpeed)

    def getDownloadStatistics(self):
        downloadLog = 'File downloaded : '
        downloadLog += str(self.percentdownloaded) + ' % '
        downloadLog += '(Average downloading speed : '
        downloadLog += str(self.avgDownloadSpeed) + ' Kbps  '
        downloadLog += 'Time remaining : '
        downloadLog += str(self.remainingTime) + 's )'
        return downloadLog

    def getUploadStatistics(self):
        uploadLog = 'uploaded : [upload speed = '
        uploadLog += str(self.uploadSpeed) + ' Kbps'
        uploadLog += ', average uploading speed = '
        uploadLog += str(self.avgUploadSpeed) + ' Kbps'
        uploadLog += ', max uploading speed = '
        uploadLog += str(self.maxuploadSpeed) + ' Kbps]'
        return uploadLog
