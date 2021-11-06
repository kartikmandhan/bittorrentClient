# dictionary model of tracker response is yet to implement
import sys
from torrentFile import *
from peerWireProtocol import *
from math import ceil
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
    rarestCount = min(map(len, allBitfields.values()))
    rarestPieces = []
    for pieceNumber in allBitfields.keys():
        if len(allBitfields[pieceNumber]) == rarestCount:
            rarestPieces.append(pieceNumber)
    return rarestPieces


def writePieceInFile(f, pieceNumber, piece):
    f.seek(pieceNumber*torrentFileData.pieceLength, 0)
    f.write(piece)


def writeNullToFile(f, filePath, fileSize):
    data = b"\x00" * fileSize
    f.write(data)


def downloadPiece(peer, pieceNumber):
    ###
    BLOCK_SIZE = 2**14
    numberOfBlocks = ceil(torrentFileData.pieceLength/(BLOCK_SIZE))
    ###
    piece = b''
    offset = 0
    f = open("temp", "wb+")
    writeNullToFile(f, "temp", torrentFileData.lengthOfFileToBeDownloaded)

    for i in range(numberOfBlocks):
        peer.sendMsg(6, (pieceNumber, offset, BLOCK_SIZE))
        response = peer.decodeMsg(peer.receiveMsg())
        print("response of piece : ", response)
        if 'piece' in response:
            offset += BLOCK_SIZE
            piece += response['piece'][2]
        else:
            i -= 1

    pieceHash = hashlib.sha1(piece).digest()
    print(pieceHash, torrentFileData.hashOfPieces[pieceNumber])
    if pieceHash == torrentFileData.hashOfPieces[pieceNumber]:
        print("Length of Piece", len(piece))
        writePieceInFile(f, pieceNumber, piece)


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
    else:
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
        workingPeers = []
        print("Piece Length : ", torrentFileData.pieceLength)

        for peer in peerAddresses:
            workingPeers.append(Peer(peer[0], peer[1], mainRequestMaker))

        # {
        #     0: [peerNo],
        #     1: [peerNo,peerNo,peerNo,peerNo],
        # }
        # len of each value will give the count of peers having a piece
        allBitfields = {}
        for peerNumber, peer in enumerate(workingPeers):
            print(peerNumber)
            if(peer.doHandshake()):
                print("HandShake Successful .. ")
                response = peer.decodeMsg(peer.receiveMsg())
                if 'unchoke' in response:
                    peer.peer_choking = False
                # function call for bitfield
                if 'bitfield' in response:
                    peer.extractBitField(response['bitfield'])
                    if peer.bitfield == None:
                        continue
                    for pieceNumber in peer.bitfield:
                        if pieceNumber in allBitfields:
                            allBitfields[pieceNumber].append(peerNumber)
                        else:
                            allBitfields[pieceNumber] = [peerNumber]
            if peerNumber >= 2:
                break
            # print(allBitfields)

        for peerNumber, peer in enumerate(workingPeers):
            try:
                if peer.isHandshakeDone == False:
                    continue
                print("Sending Interested ... ", peerNumber, flush='true')
                peer.sendMsg(2)
                response = peer.decodeMsg(peer.receiveMsg())
                if not peer.peer_choking or 'unchoke' in response:
                    peer.peer_choking = False
                if peerNumber >= 2:
                    break
            except:
                print("Exception Occured")
                continue

        rarestPieces = rarestPieceFirstSelection(allBitfields)
        for pieceNumber in rarestPieces:
            downloadingPeer = allBitfields[pieceNumber][0]
            print("Downloading .................",
                  pieceNumber, torrentFileData.numberOfPieces)
            downloadPiece(peer, pieceNumber)
            break

    else:
        print("All trackers are useless")

    # if(pwp.handshakeRequest() == False):
    #     # close connection
    #     pass
    # else:
    #     print("All trackers are useless")


makeRequest()

# pwp = PeerWireProtocol(torrentFileData)
