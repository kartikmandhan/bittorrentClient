# dictionary model of tracker response is yet to implement
import sys
from torrentFile import *
from peerWireProtocol import *
from math import ceil
from threading import Thread
import hashlib
try:

    fileName = sys.argv[1]
except:
    print("usage python3 init.py <filename> ")
    exit(0)

torrentFileData = FileInfo(sys.argv[1])
torrentFileData.extractFileMetaData()
# print(torrentFileData)
# print(torrentFileData.infoDictionary[b"files"])


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


def rarestPieceFirstSelection(allBitfields):
    rarestPieces = []
    if len(allBitfields) == 0:
        return rarestPieces
    rarestCount = min(map(len, allBitfields.values()))
    for pieceNumber in allBitfields.keys():
        if len(allBitfields[pieceNumber]) == rarestCount:
            rarestPieces.append(pieceNumber)
    return rarestPieces


def writePieceInFile(pieceNumber, piece):
    f.seek(pieceNumber*torrentFileData.pieceLength, 0)
    f.write(piece)


f = open(torrentFileData.nameOfFile, "wb")


def writeNullToFile():
    data = b"\x00" * torrentFileData.lengthOfFileToBeDownloaded
    f.write(data)


def downloadPiece(pieceNumber):
    print("Downloading Piece ..", pieceNumber, flush='true')
    ###
    BLOCK_SIZE = 2**14
    numberOfBlocks = ceil(torrentFileData.pieceLength/(BLOCK_SIZE))
    currentPieceLength = torrentFileData.pieceLength
    if pieceNumber == torrentFileData.numberOfPieces-1:
        currentPieceLength = (torrentFileData.lengthOfFileToBeDownloaded -
                              (pieceNumber * torrentFileData.pieceLength))
        numberOfBlocks = ceil(currentPieceLength/BLOCK_SIZE)
        print("last piecelength", currentPieceLength, numberOfBlocks)
    ###
    piece = b''
    offset = 0
    blockNumber = 0
    currentBlockLength = 0
    while blockNumber < numberOfBlocks:
        if currentPieceLength-offset >= BLOCK_SIZE:
            currentBlockLength = BLOCK_SIZE
        else:
            currentBlockLength = currentPieceLength - offset
        print(currentBlockLength, currentPieceLength)
        block = downloadBlock(pieceNumber, offset, currentBlockLength)
        if block == None:
            print("Unable to Download block")
            return False
        piece += block
        offset += len(block)
        print("Donwloaded Block ...", blockNumber, pieceNumber)
        blockNumber += 1

    pieceHash = hashlib.sha1(piece).digest()
    print(pieceHash, torrentFileData.hashOfPieces[pieceNumber])
    if pieceHash == torrentFileData.hashOfPieces[pieceNumber]:
        print("pieceHash matched,writing in file", torrentFileData.nameOfFile)
        writePieceInFile(pieceNumber, piece)
        return True
    return False


def downloadBlock(pieceNumber, offset, blockLength):
    for peerNumber in allBitfields[pieceNumber]:
        peer = workingPeers[peerNumber]
        if peer.isHandshakeDone == False:
            print("hndshake not done .....")
            continue
        if peer.peer_choking == True:
            print("choking  .....")
            continue
        retries = 0
        while(retries < 3):
            if peer.isConnectionAlive == False:
                print("Connection Not Alive ..")
                break
            if(peer.sendMsg(6, (pieceNumber, offset, blockLength))):
                # peer.connectionSocket.settimeout(None)
                response = peer.decodeMsg(peer.receiveMsg())
                if response and 'piece' in response:
                    # print("response of piece : ", response, flush='true')
                    return response['piece'][2]
            retries += 1
            print("Retrying ......")
    return None


allBitfields = {}


def tryToUnchokePeer(peer):
    try:
        if peer.isHandshakeDone == False or peer.isConnectionAlive == False:
            return
        # sending interested
        print("Sending Intrested .. ")
        peer.sendMsg(2)
        if peer.peer_choking:
            response = peer.decodeMsg(peer.receiveMsg())
            print("response in unchoke peer", response)
    except:
        print("Exception Occured")


def getBitfield(peer, peerNumber):
    print("I am in getBitfield", flush="true")
    if(peer.doHandshake()):
        print("HandShake Successful .. ")
        response = peer.decodeMsg(peer.receiveMsg())
        # function call for bitfield
        if 'bitfield' in response:
            peer.extractBitField(response['bitfield'])
            for pieceNumber in peer.bitfield:
                if pieceNumber in allBitfields:
                    allBitfields[pieceNumber].append(peerNumber)
                else:
                    allBitfields[pieceNumber] = [peerNumber]
        tryToUnchokePeer(peer)
    print("at end of getbitfield")


workingPeers = []
downloadedPiecesBitfields = set()


def isDownloadRemaining():
    if torrentFileData.numberOfPieces != len(downloadedPiecesBitfields):
        return True
    return False


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

        for peer in peerAddresses:
            workingPeers.append(Peer(peer[0], peer[1], mainRequestMaker))
        # {
        #     0: [peerNo],
        #     1: [peerNo,peerNo,peerNo,peerNo],
        # }
        # len of each value will give the count of peers having a piece

        for peerNumber, peer in enumerate(workingPeers):
            if peerNumber > 10:
                break
            thread = Thread(
                target=getBitfield, args=(peer, peerNumber))
            thread.start()
        writeNullToFile()
        while isDownloadRemaining():
            rarestPieces = rarestPieceFirstSelection(allBitfields)
            print(rarestPieces)
            for pieceNumber in rarestPieces:
                if(downloadPiece(pieceNumber)):
                    allBitfields.pop(pieceNumber)
                    downloadedPiecesBitfields.add(pieceNumber)

    else:
        print("All trackers are useless")

    # if(pwp.handshakeRequest() == False):
    #     # close connection
    #     pass
    # else:
    #     print("All trackers are useless")


makeRequest()
# pwp = PeerWireProtocol(torrentFileData)
