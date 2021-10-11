import bencodepy
import hashlib
import random
# import urllib.parse
import requests
# print(bencode.encode(3))
f = open("./files/ubuntu-21.04-desktop-amd64.iso.torrent", "rb")
# f1 = open("./files/scrape", "rb")
content = bencodepy.decode(f.read())
# fileKey = content["files".encode()]
announceURL = content["announce".encode()].decode()
# print(announceURL)
lengthOfFileToBeDownloaded = content["info".encode()]["length".encode()]
# print(lengthOfFileToBeDownloaded)
infoDictionary = content["info".encode()]

nameOfFile = content["info".encode()]["name".encode()].decode()
pieces = content["info".encode()]["pieces".encode()]

infoDictionaryBencode = bencodepy.encode(infoDictionary)
infoHash = hashlib.sha1(infoDictionaryBencode).digest()
# print(infoHash)

peerID = "KK"+"0001" + str(random.randint(10000000000000, 99999999999999))
portNo = 6885
hashOfPieces = []
previous = 0
for i in range(20, len(pieces) + 20, 20):
    hashOfPieces.append(pieces[previous:i])
    previous = i
# print(len(hashOfPieces), hashOfPieces[-1])
params = {"info_hash": infoHash, "peer_id": peerID, "port": portNo, "uploaded": 0,
          "downloaded": 0, "left": lengthOfFileToBeDownloaded, "compact": 1}
# finalURL = announceURL+"?"+params
# print(finalURL)
# announceFile = open("./files/announce", "rb")
announceResponse = requests.get(announceURL, params).content
trackerResponseDict = bencodepy.decode(announceResponse)
# print(announceResponse)
trackerComplete = trackerResponseDict[b"complete"]
trackerIncomplete = trackerResponseDict[b"incomplete"]
trackerInterval = trackerResponseDict[b"interval"]
trackerPeers = trackerResponseDict[b"peers"]
allPeers = []
previous = 0
for i in range(6, len(trackerPeers) + 6, 6):
    allPeers.append(trackerPeers[previous:i])
    previous = i
# print(allPeers)


def extractIPAdressandPort(peerID):
    port = int.from_bytes(peerID[-2:], "big")
    # print(port)
    ipAddress = ""
    ip = list(map(str, peerID[:4]))
    ipAddress = ".".join(ip)
    return (ipAddress, port)


peerAddresses = []
for i in allPeers:
    peerAddresses.append(extractIPAdressandPort(i))
# aIP = allPeers[-1]
# aIP = extractIPAdressandPort(aIP)
# aIP="."join(map(int,aIP))
# print(aIP)
print(peerAddresses)
# print(bencodepy.decode_from_file("./files/ubuntu-21.04-desktop-amd64.iso.torrent"))
# print(hex(pieces[:20]))
# print(content["info".encode()]["name".encode()].decode())
# print(content["info".encode()]["piece length".encode()])
# Piece Length : 262144
# print(b'\x00@\x95\x16\xf2N\x04T\xd9\xcc\xe2\xdc\xa8\x17wp\x7f\xc0(\xd7'.decode())
# print()
# print(bencode.decode("20:  Fx��x0�Wsz�����O�)"))
